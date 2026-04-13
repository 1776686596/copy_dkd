from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message


@pytest.mark.asyncio
async def test_wecomweb_adapter_extracts_service_desk_context():
    from langbot.pkg.platform.sources.wecomweb import WecomWebAdapter, WecomWebMessageEvent

    adapter = object.__new__(WecomWebAdapter)
    event = WecomWebMessageEvent(
        account_id='escort-account',
        external_user_id='external-customer-1',
        message_id='msg-1',
        conversation_id='conv-1',
        sender_name='客户A',
        content='你好',
        timestamp=1710000000,
    )

    assert adapter.extract_service_desk_context(event) == {
        'source_entry_id': 'escort-account',
        'external_user_id': 'external-customer-1',
        'last_message_id': 'msg-1',
    }


@pytest.mark.asyncio
async def test_wecomweb_adapter_reply_message_uses_browser_client():
    from langbot.pkg.platform.sources.wecomweb import WecomWebAdapter

    adapter = object.__new__(WecomWebAdapter)
    object.__setattr__(adapter, 'bot', Mock())
    adapter.bot.send_text = AsyncMock()

    event = SimpleNamespace(
        source_platform_object=SimpleNamespace(
            account_id='escort-account',
            external_user_id='external-customer-1',
            conversation_id='conv-1',
            message_id='msg-1',
        )
    )
    message = platform_message.MessageChain([platform_message.Plain(text='这里是 AI 回复')])

    await WecomWebAdapter.reply_message(adapter, event, message)

    adapter.bot.send_text.assert_awaited_once_with(
        conversation_id='conv-1',
        external_user_id='external-customer-1',
        text='这里是 AI 回复',
    )


@pytest.mark.asyncio
async def test_client_deduplicates_seen_messages():
    from langbot.libs.wecom_web_page_api.client import WecomWebPageClient

    client = WecomWebPageClient(
        account_label='escort-account',
        workbench_url='https://work.weixin.qq.com/kf/',
        storage_state_dir='./tmp/wecomweb',
    )

    payload = {
        'conversation_id': 'conv-1',
        'external_user_id': 'external-customer-1',
        'message_id': 'msg-1',
        'sender_name': '客户A',
        'content': '你好',
        'timestamp': 1710000000,
    }

    assert client._remember_message(payload) is True
    assert client._remember_message(payload) is False


@pytest.mark.asyncio
async def test_adapter_forwards_browser_events_to_registered_listener():
    from langbot.pkg.platform.sources.wecomweb import WecomWebAdapter

    adapter = object.__new__(WecomWebAdapter)
    object.__setattr__(adapter, 'listeners', {})
    object.__setattr__(adapter, 'bot', Mock())
    adapter.bot.set_message_callback = Mock()

    received = []

    async def on_friend_message(event, runtime_adapter):
        received.append((event.sender.id, str(event.message_chain), runtime_adapter))

    WecomWebAdapter.register_listener(adapter, platform_events.FriendMessage, on_friend_message)

    callback = adapter.bot.set_message_callback.call_args.args[0]
    await callback(
        {
            'account_id': 'escort-account',
            'external_user_id': 'external-customer-1',
            'conversation_id': 'conv-1',
            'message_id': 'msg-1',
            'sender_name': '客户A',
            'content': '你好',
            'timestamp': 1710000000,
        }
    )

    assert received[0][0] == 'uexternal-customer-1'
    assert received[0][1] == '你好'
    assert received[0][2] is adapter


def test_client_config_preserves_polling_and_headless_flags():
    from langbot.libs.wecom_web_page_api.client import WecomWebPageClient

    client = WecomWebPageClient(
        account_label='escort-account',
        workbench_url='https://work.weixin.qq.com/kf/',
        storage_state_dir='./tmp/wecomweb',
        poll_interval_seconds=2,
        headless=False,
    )

    assert client.poll_interval_seconds == 2
    assert client.headless is False


@pytest.mark.asyncio
async def test_wecomweb_adapter_run_async_calls_client_loop():
    from langbot.pkg.platform.sources.wecomweb import WecomWebAdapter

    adapter = object.__new__(WecomWebAdapter)
    object.__setattr__(adapter, 'bot', Mock())
    adapter.bot.run_forever = AsyncMock()

    await WecomWebAdapter.run_async(adapter)

    adapter.bot.run_forever.assert_awaited_once()

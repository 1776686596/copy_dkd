from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.platform.message as platform_message


@pytest.mark.asyncio
async def test_wecomprivate_adapter_extracts_service_desk_context():
    from langbot.pkg.platform.sources.wecomprivate import WecomPrivateAdapter, WecomPrivateMessageEvent

    adapter = object.__new__(WecomPrivateAdapter)
    event = WecomPrivateMessageEvent(
        entry_id='cfg-1',
        follow_user_id='follow-1',
        external_user_id='wo123',
        message_id='msg-1',
        conversation_id='conv-1',
        sender_name='客户A',
        content='你好',
        timestamp=1710000000,
        welcome_code='welcome-1',
    )

    assert adapter.extract_service_desk_context(event) == {
        'source_entry_id': 'cfg-1',
        'external_user_id': 'wo123',
        'last_message_id': 'msg-1',
    }
    assert adapter.get_launcher_id(event) == 'cfg-1:wo123'


@pytest.mark.asyncio
async def test_wecomprivate_adapter_reply_message_uses_page_client():
    from langbot.pkg.platform.sources.wecomprivate import WecomPrivateAdapter

    adapter = object.__new__(WecomPrivateAdapter)
    object.__setattr__(adapter, 'bot', Mock())
    adapter.bot.send_text = AsyncMock()

    event = SimpleNamespace(
        source_platform_object=SimpleNamespace(
            entry_id='cfg-1',
            external_user_id='wo123',
            conversation_id='conv-1',
            message_id='msg-1',
        )
    )
    message = platform_message.MessageChain([platform_message.Plain(text='这里是 AI 回复')])

    await WecomPrivateAdapter.reply_message(adapter, event, message)

    adapter.bot.send_text.assert_awaited_once_with(
        conversation_id='conv-1',
        external_user_id='wo123',
        text='这里是 AI 回复',
    )

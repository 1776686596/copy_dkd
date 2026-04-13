from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.asyncio
async def test_manual_session_skips_pipeline_enqueue():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskDecision
    from langbot.pkg.platform.botmgr import RuntimeBot

    bot = object.__new__(RuntimeBot)
    bot.bot_entity = Mock()
    bot.ap = Mock()
    bot.logger = Mock()
    bot.logger.info = AsyncMock()
    bot.ap.service_desk_service = Mock()
    bot.ap.service_desk_service.handle_incoming_message = AsyncMock(
        return_value=ServiceDeskDecision(action='skip_pipeline', reason='manual')
    )
    bot.ap.service_desk_service.send_structured_reply = AsyncMock()

    event = Mock()
    adapter = Mock()

    handled = await bot._handle_service_desk_before_pipeline(event, adapter)

    assert handled is True
    bot.ap.service_desk_service.handle_incoming_message.assert_awaited_once_with(
        bot_entity=bot.bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid=None,
    )
    bot.logger.info.assert_awaited_once()
    bot.ap.service_desk_service.send_structured_reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_ai_assist_mode_does_not_auto_send():
    from types import SimpleNamespace

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService
    from langbot.pkg.platform.botmgr import RuntimeBot

    bot = object.__new__(RuntimeBot)
    bot.bot_entity = SimpleNamespace(
        adapter='wecomcs',
        uuid='bot-1',
        use_pipeline_uuid='pipeline-1',
    )
    bot.ap = Mock()
    bot.logger = Mock()
    bot.logger.info = AsyncMock()

    service = ServiceDeskService(Mock())
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_user-1',
            'mode': 'ai_assist',
            'queue_status': 'manual',
            'manual_claimed_at': None,
            'silent_since': None,
        }
    )
    service.get_bot_config = AsyncMock(return_value={'enabled': True})
    service.list_materials = AsyncMock(return_value=[])
    service.send_structured_reply = AsyncMock()
    bot.ap.service_desk_service = service

    event = SimpleNamespace(
        message_chain='请帮我看下这个问题',
        source_platform_object=SimpleNamespace(),
        sender=SimpleNamespace(id='user-1', nickname='用户A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'kf-1',
        'external_user_id': 'external-1',
        'last_message_id': 'msg-1',
    }
    adapter.get_launcher_id.return_value = 'user-1'

    handled = await bot._handle_service_desk_before_pipeline(event, adapter)

    assert handled is True
    service.send_structured_reply.assert_not_awaited()


def test_wecomcs_adapter_extracts_service_desk_context():
    from langbot.libs.wecom_customer_service_api.wecomcsevent import WecomCSEvent
    from langbot.pkg.platform.sources.wecomcs import WecomCSAdapter

    adapter = object.__new__(WecomCSAdapter)
    event = WecomCSEvent(
        {
            'open_kfid': 'kf-001',
            'external_userid': 'user-001',
            'msgid': 'msg-001',
        }
    )

    context = adapter.extract_service_desk_context(event)

    assert context == {
        'source_entry_id': 'kf-001',
        'external_user_id': 'user-001',
        'last_message_id': 'msg-001',
    }


@pytest.mark.asyncio
async def test_wecomweb_message_enters_service_desk_flow():
    from types import SimpleNamespace

    from langbot.pkg.api.http.service.service_desk import ServiceDeskDecision
    from langbot.pkg.platform.botmgr import RuntimeBot

    bot = object.__new__(RuntimeBot)
    bot.bot_entity = SimpleNamespace(
        adapter='wecomweb',
        uuid='bot-1',
        use_pipeline_uuid='pipeline-1',
    )
    bot.ap = Mock()
    bot.logger = Mock()
    bot.logger.info = AsyncMock()
    bot.ap.service_desk_service = Mock()
    bot.ap.service_desk_service.handle_incoming_message = AsyncMock(
        return_value=ServiceDeskDecision(action='continue_ai')
    )
    bot.ap.service_desk_service.send_structured_reply = AsyncMock()

    event = SimpleNamespace(
        message_chain='我要下载链接',
        sender=SimpleNamespace(id='customer-1', nickname='客户A'),
    )
    adapter = Mock()
    adapter.get_launcher_id.return_value = 'escort-account:external-customer-1'
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'escort-account',
        'external_user_id': 'external-customer-1',
        'last_message_id': 'msg-1',
    }

    handled = await bot._handle_service_desk_before_pipeline(
        event,
        adapter,
        pipeline_uuid='pipeline-1',
    )

    assert handled is False
    bot.ap.service_desk_service.handle_incoming_message.assert_awaited_once_with(
        bot_entity=bot.bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipeline-1',
    )

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.asyncio
async def test_reply_to_session_uses_runtime_bot_and_records_assistant_message():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    desk_session = SimpleNamespace(
        session_id='session-1',
        bot_uuid='bot-1',
        pipeline_uuid='pipeline-1',
        source_entry_id='kf-1',
        external_user_id='external-user-1',
        last_message_id='msg-1',
    )
    runtime_bot = SimpleNamespace(
        adapter=SimpleNamespace(bot=SimpleNamespace(send_text_msg=AsyncMock())),
        bot_entity=SimpleNamespace(name='客服机器人', use_pipeline_name='默认流程'),
    )

    query_result = Mock()
    query_result.first.return_value = desk_session

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(return_value=query_result)
    ap.platform_mgr.get_bot_by_uuid = AsyncMock(return_value=runtime_bot)
    ap.monitoring_service.record_message = AsyncMock()
    service = ServiceDeskService(ap)

    await service.reply_to_session('session-1', '人工已接手')

    runtime_bot.adapter.bot.send_text_msg.assert_awaited_once_with(
        open_kfid='kf-1',
        external_userid='external-user-1',
        msgid='msg-1',
        content='人工已接手',
    )
    ap.monitoring_service.record_message.assert_awaited_once_with(
        bot_id='bot-1',
        bot_name='客服机器人',
        pipeline_id='pipeline-1',
        pipeline_name='默认流程',
        message_content='人工已接手',
        session_id='session-1',
        platform='wecomcs',
        user_id='external-user-1',
        role='assistant',
    )


@pytest.mark.asyncio
async def test_reply_to_session_uses_service_desk_sender_for_lark_runtime_bot():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    desk_session = SimpleNamespace(
        session_id='session-2',
        bot_uuid='bot-2',
        pipeline_uuid='pipeline-2',
        source_entry_id='tenant-key-1',
        external_user_id='ou_customer_1',
        last_message_id='om_dc1321',
    )
    runtime_bot = SimpleNamespace(
        adapter=SimpleNamespace(send_service_desk_text=AsyncMock()),
        bot_entity=SimpleNamespace(
            name='飞书客服机器人',
            use_pipeline_name='飞书流程',
            adapter='lark',
        ),
    )

    query_result = Mock()
    query_result.first.return_value = desk_session

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(return_value=query_result)
    ap.platform_mgr.get_bot_by_uuid = AsyncMock(return_value=runtime_bot)
    ap.monitoring_service.record_message = AsyncMock()
    service = ServiceDeskService(ap)

    await service.reply_to_session('session-2', '飞书人工接手')

    runtime_bot.adapter.send_service_desk_text.assert_awaited_once_with(
        {
            'source_entry_id': 'tenant-key-1',
            'external_user_id': 'ou_customer_1',
            'last_message_id': 'om_dc1321',
        },
        '飞书人工接手',
    )
    ap.monitoring_service.record_message.assert_awaited_once_with(
        bot_id='bot-2',
        bot_name='飞书客服机器人',
        pipeline_id='pipeline-2',
        pipeline_name='飞书流程',
        message_content='飞书人工接手',
        session_id='session-2',
        platform='lark',
        user_id='ou_customer_1',
        role='assistant',
    )

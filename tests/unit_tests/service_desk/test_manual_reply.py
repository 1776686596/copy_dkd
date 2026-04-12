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

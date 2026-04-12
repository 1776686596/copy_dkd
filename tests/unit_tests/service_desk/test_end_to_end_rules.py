from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


class _FakeSessionResult:
    def __init__(self, item):
        self._item = item

    def first(self):
        return dict(self._item)


@pytest.mark.asyncio
async def test_keyword_to_manual_then_timeout_to_silent_then_reopen_to_ai():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    service = ServiceDeskService(ap=None)

    session = {
      'mode': 'manual',
      'queue_status': 'manual',
      'manual_claimed_at': datetime.utcnow() - timedelta(seconds=901),
      'silent_since': None,
    }

    timed_out = service._should_mark_silent(session, timeout_seconds=900)
    reopened = service._reopen_mode_after_customer_message('silent')

    assert timed_out is True
    assert reopened == ('ai_hosted', 'ai')


@pytest.mark.asyncio
async def test_manual_timeout_uses_last_manual_reply_at_as_activity_anchor():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    service = ServiceDeskService(ap=None)

    session = {
      'mode': 'manual',
      'queue_status': 'manual',
      'manual_claimed_at': datetime.utcnow() - timedelta(seconds=901),
      'last_manual_reply_at': datetime.utcnow() - timedelta(seconds=120),
      'silent_since': None,
    }

    timed_out = service._should_mark_silent(session, timeout_seconds=900)

    assert timed_out is False


@pytest.mark.asyncio
async def test_handoff_keyword_moves_session_to_pending_manual():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskDecision
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value=SimpleNamespace(
            session_id='person_user-1',
            queue_status='ai',
            mode='ai_hosted',
            manual_claimed_at=None,
            silent_since=None,
        )
    )
    service._update_session_state = AsyncMock()
    service.list_materials = AsyncMock(return_value=[])
    service.get_bot_config = AsyncMock(
        return_value={
            'enabled': True,
            'handoff_keywords': ['人工', '客服'],
            'manual_timeout_seconds': 900,
        }
    )

    bot_entity = SimpleNamespace(
        adapter='wecomcs',
        uuid='bot-1',
        use_pipeline_uuid='pipeline-1',
    )
    event = SimpleNamespace(
        message_chain='我要转人工客服',
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

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipeline-1',
    )

    assert decision == ServiceDeskDecision(
        action='skip_pipeline',
        reason='pending_manual',
    )
    service._update_session_state.assert_awaited_once_with(
        'person_user-1',
        mode='manual',
        queue_status='pending_manual',
        handoff_reason='keyword',
    )


@pytest.mark.asyncio
async def test_return_session_to_ai_clears_manual_fields():
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    service = ServiceDeskService(Mock())
    service._get_session = AsyncMock(
        return_value={
            'session_id': 'person_return_ai_1',
            'mode': 'manual',
            'queue_status': 'manual',
            'manual_claimed_at': datetime.utcnow(),
            'claimed_by_user_uuid': 'user-1',
            'claimed_by_user_name': '客服A',
            'silent_since': datetime.utcnow(),
        }
    )
    service._update_session_state = AsyncMock()

    await service.return_session_to_ai('person_return_ai_1')

    service._update_session_state.assert_awaited_once_with(
        'person_return_ai_1',
        mode='ai_hosted',
        queue_status='ai',
        claimed_by_user_uuid=None,
        claimed_by_user_name=None,
        manual_claimed_at=None,
        silent_since=None,
        last_manual_reply_at=None,
    )


@pytest.mark.asyncio
async def test_release_then_reclaim_keeps_session_consistent():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    session = {
        'session_id': 'person_release_claim_1',
        'mode': 'ai_assist',
        'queue_status': 'manual',
        'claimed_by_user_uuid': 'user-1',
        'claimed_by_user_name': '客服A',
        'manual_claimed_at': datetime.utcnow(),
        'updated_at': datetime.utcnow(),
    }

    async def _execute_async(statement):
        if statement.is_select:
            return _FakeSessionResult(session)

        if statement.is_update:
            for column, value in statement._values.items():
                session[column.name] = value.value
            return None

        raise AssertionError(f'unexpected statement: {statement}')

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(side_effect=_execute_async)
    service = ServiceDeskService(ap)

    await service.release_session('person_release_claim_1')

    assert session['mode'] == 'manual'
    assert session['queue_status'] == 'pending_manual'
    assert session['claimed_by_user_uuid'] is None
    assert session['manual_claimed_at'] is None

    await service.claim_session('person_release_claim_1', 'user-2', '客服B')

    assert session['mode'] == 'manual'
    assert session['queue_status'] == 'manual'
    assert session['claimed_by_user_uuid'] == 'user-2'
    assert session['claimed_by_user_name'] == '客服B'
    assert session['manual_claimed_at'] is not None


@pytest.mark.asyncio
async def test_return_to_ai_clears_manual_overlay():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    session = {
        'session_id': 'person_return_ai_overlay_1',
        'mode': 'manual',
        'queue_status': 'manual',
        'claimed_by_user_uuid': 'user-1',
        'claimed_by_user_name': '客服A',
        'manual_claimed_at': datetime.utcnow(),
        'silent_since': datetime.utcnow(),
        'last_manual_reply_at': datetime.utcnow(),
        'updated_at': datetime.utcnow(),
    }

    async def _execute_async(statement):
        if statement.is_select:
            return _FakeSessionResult(session)

        if statement.is_update:
            for column, value in statement._values.items():
                session[column.name] = value.value
            return None

        raise AssertionError(f'unexpected statement: {statement}')

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(side_effect=_execute_async)
    service = ServiceDeskService(ap)

    await service.return_session_to_ai('person_return_ai_overlay_1')

    assert session['mode'] == 'ai_hosted'
    assert session['queue_status'] == 'ai'
    assert session['claimed_by_user_uuid'] is None
    assert session['claimed_by_user_name'] is None
    assert session['manual_claimed_at'] is None
    assert session['silent_since'] is None
    assert session['last_manual_reply_at'] is None

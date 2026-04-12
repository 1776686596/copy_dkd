from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.asyncio
async def test_enable_ai_assist_switches_manual_session_mode():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    service = ServiceDeskService(Mock())
    service._get_session = AsyncMock(
        return_value={
            'session_id': 'person_u1001',
            'mode': 'manual',
            'queue_status': 'manual',
        }
    )
    service._update_session_state = AsyncMock()

    await service.set_session_mode('person_u1001', mode='ai_assist')

    service._update_session_state.assert_awaited_once_with(
        'person_u1001',
        mode='ai_assist',
        queue_status='manual',
    )


@pytest.mark.asyncio
async def test_ai_assist_generates_draft_without_sending():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    service = ServiceDeskService(Mock())
    service._get_session = AsyncMock(
        return_value={
            'session_id': 'person_u1002',
            'mode': 'ai_assist',
            'queue_status': 'manual',
        }
    )

    draft = await service.generate_assist_draft(
        session_id='person_u1002',
        operator_user_id='u-1',
    )

    assert draft['session_id'] == 'person_u1002'
    assert draft['reply_text']
    assert draft['source'] == 'ai_assist'
    assert draft['sent'] is False
    assert draft['operator_user_id'] == 'u-1'

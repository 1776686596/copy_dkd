from unittest.mock import AsyncMock, Mock

import pytest


class _FakeListResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeScalarResult:
    def __init__(self, value: int):
        self._value = value

    def scalar(self):
        return self._value


class _FakeSessionScalarRows:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeSessionQueryResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row['session_id']

    def scalars(self):
        return _FakeSessionScalarRows(self._row)


@pytest.mark.asyncio
async def test_list_workbench_sessions_supports_keyword_search():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    source_items = [
        {
            'session_id': 'person_礼包_u1001',
            'bot_uuid': 'bot-1',
            'queue_status': 'manual',
            'claimed_by_user_uuid': 'user-1',
            'external_user_id': 'wx_u1001',
            'updated_at': None,
            'mode': 'manual',
        },
        {
            'session_id': 'person_normal_u1002',
            'bot_uuid': 'bot-1',
            'queue_status': 'manual',
            'claimed_by_user_uuid': 'user-2',
            'external_user_id': 'wx_u1002',
            'updated_at': None,
            'mode': 'manual',
        },
    ]

    def _filter_items(statement):
      params = set(statement.compile().params.values())
      filtered = list(source_items)
      if 'bot-1' in params:
          filtered = [item for item in filtered if item['bot_uuid'] == 'bot-1']
      if 'manual' in params:
          filtered = [item for item in filtered if item['queue_status'] == 'manual']
      if '礼包' in params:
          filtered = [
              item
              for item in filtered
              if '礼包' in item['session_id'] or '礼包' in item['external_user_id']
          ]
      return filtered

    async def _execute_async(statement):
        statement_text = str(statement).lower()
        filtered = _filter_items(statement)
        if 'count(' in statement_text:
            return _FakeScalarResult(len(filtered))
        return _FakeListResult(filtered)

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(side_effect=_execute_async)
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda _model, row: row)

    service = ServiceDeskService(ap)

    items, total = await service.list_workbench_sessions(
        bot_uuid='bot-1',
        queue_status='manual',
        keyword='礼包',
        claimed_by=None,
        limit=50,
        offset=0,
    )

    assert total == 1
    assert items[0]['external_user_id'] == 'wx_u1001'


@pytest.mark.asyncio
async def test_get_session_detail_returns_messages_and_overlay():
    from types import SimpleNamespace

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda _model, row: row)
    ap.monitoring_service.get_messages = AsyncMock(
        return_value=(
            [
                {
                    'id': 'msg-1',
                    'timestamp': '2026-04-12T10:00:00',
                    'message_content': '你好',
                    'session_id': 'person_u1001',
                    'role': 'user',
                    'status': 'success',
                    'level': 'info',
                }
            ],
            1,
        )
    )
    ap.platform_mgr.get_bot_by_uuid = AsyncMock(
        return_value=SimpleNamespace(bot_entity=SimpleNamespace(name='客服机器人'))
    )

    service = ServiceDeskService(ap)
    service._get_session = AsyncMock(
        return_value={
            'session_id': 'person_u1001',
            'bot_uuid': 'bot-1',
            'pipeline_uuid': 'pipeline-1',
            'handoff_reason': 'keyword',
        }
    )

    detail = await service.get_session_detail('person_u1001')

    assert detail['session']['session_id'] == 'person_u1001'
    assert detail['messages']
    assert 'handoff_reason' in detail['session']
    assert detail['bot']['uuid'] == 'bot-1'


@pytest.mark.asyncio
async def test_get_session_detail_uses_scalar_row_when_result_first_is_primary_key():
    from types import SimpleNamespace

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    session_row = {
        'session_id': 'person_ou_demo_1',
        'bot_uuid': 'bot-1',
        'pipeline_uuid': 'pipeline-1',
        'handoff_reason': None,
    }

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(
        return_value=_FakeSessionQueryResult(session_row)
    )
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda _model, row: row)
    ap.monitoring_service.get_messages = AsyncMock(return_value=([], 0))
    ap.platform_mgr.get_bot_by_uuid = AsyncMock(
        return_value=SimpleNamespace(bot_entity=SimpleNamespace(name='客服机器人'))
    )

    service = ServiceDeskService(ap)

    detail = await service.get_session_detail('person_ou_demo_1')

    assert detail['session']['session_id'] == 'person_ou_demo_1'
    assert detail['bot']['name'] == '客服机器人'

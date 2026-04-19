import datetime
from unittest.mock import AsyncMock, Mock

import pytest
import quart
from sqlalchemy.exc import ResourceClosedError


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
    def __init__(self, result):
        self._result = result

    def first(self):
        if self._result._closed:
            raise ResourceClosedError('This result object is closed.')
        self._result._closed = True
        return self._result._row


class _FakeRow:
    def __init__(self, data):
        self._data = data
        self._mapping = data

    def __getattr__(self, item):
        try:
            return self._data[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


class _FakeSessionQueryResult:
    def __init__(self, row):
        self._row = row
        self._closed = False

    def first(self):
        if self._closed:
            raise ResourceClosedError('This result object is closed.')
        self._closed = True
        return self._row

    def scalars(self):
        return _FakeSessionScalarRows(self)


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
        params = set()
        for value in statement.compile().params.values():
            if isinstance(value, (list, tuple, set)):
                params.update(value)
            else:
                params.add(value)

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
        if 'from monitoring_messages' in statement_text:
            return _FakeListResult([])
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
async def test_list_workbench_sessions_includes_last_message_preview():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    source_items = [
        {
            'session_id': 'person_u1001',
            'bot_uuid': 'bot-1',
            'queue_status': 'manual',
            'claimed_by_user_uuid': 'user-1',
            'external_user_id': 'wx_u1001',
            'updated_at': None,
            'mode': 'manual',
        },
        {
            'session_id': 'person_u1002',
            'bot_uuid': 'bot-1',
            'queue_status': 'pending_manual',
            'claimed_by_user_uuid': None,
            'external_user_id': 'wx_u1002',
            'updated_at': None,
            'mode': 'manual',
        },
    ]
    source_messages = [
        _FakeRow(
            {
                'session_id': 'person_u1001',
                'message_content': (
                    '[{"type":"Source"},{"type":"Plain","text":"我想了解礼包内容"}]'
                ),
                'role': 'user',
                'timestamp': datetime.datetime(2026, 4, 15, 10, 0, 0),
            }
        ),
        _FakeRow(
            {
                'session_id': 'person_u1002',
                'message_content': '人工已接手，请补充区服信息',
                'role': 'assistant',
                'timestamp': datetime.datetime(2026, 4, 15, 10, 5, 0),
            }
        ),
    ]

    async def _execute_async(statement):
        statement_text = str(statement).lower()
        if 'from monitoring_messages' in statement_text:
            return _FakeListResult(source_messages)
        if 'count(' in statement_text:
            return _FakeScalarResult(len(source_items))
        return _FakeListResult(source_items)

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(side_effect=_execute_async)
    ap.persistence_mgr.serialize_model = Mock(
        side_effect=lambda _model, row: dict(row._mapping) if hasattr(row, '_mapping') else dict(row)
    )

    service = ServiceDeskService(ap)

    items, total = await service.list_workbench_sessions(bot_uuid='bot-1')

    assert total == 2
    preview_map = {item['session_id']: item for item in items}
    assert preview_map['person_u1001']['last_message_preview'] == '我想了解礼包内容'
    assert preview_map['person_u1001']['last_message_role'] == 'user'
    assert preview_map['person_u1002']['last_message_preview'] == '人工已接手，请补充区服信息'
    assert preview_map['person_u1002']['last_message_role'] == 'assistant'


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
    ap.wecom_private_service.get_session_overlay = AsyncMock(
        return_value={
            'lead': {'id': 'lead-1', 'external_userid': 'wo123', 'profile_status': 'anonymous'},
            'routing_decisions': [{'decision': 'pending_manual', 'trigger_reason': 'keyword'}],
            'binding_task': {
                'session_id': 'person_u1001',
                'verify_status': 'pending',
                'provided_role_name': '战士阿明',
            },
            'closure_record': None,
        }
    )

    service = ServiceDeskService(ap)
    service._get_session = AsyncMock(
        return_value={
            'session_id': 'person_u1001',
            'bot_uuid': 'bot-1',
            'pipeline_uuid': 'pipeline-1',
            'handoff_reason': 'keyword',
            'external_user_id': 'wo123',
            'lead_id': 'lead-1',
        }
    )
    service._load_messages_by_external_user = AsyncMock(return_value=[])

    detail = await service.get_session_detail('person_u1001')

    assert detail['session']['session_id'] == 'person_u1001'
    assert detail['messages']
    assert 'handoff_reason' in detail['session']
    assert detail['bot']['uuid'] == 'bot-1'
    assert detail['lead']['id'] == 'lead-1'
    assert detail['routing_decisions'][0]['decision'] == 'pending_manual'
    assert detail['binding_task']['verify_status'] == 'pending'
    assert detail['binding_task']['provided_role_name'] == '战士阿明'


@pytest.mark.asyncio
async def test_get_session_detail_falls_back_to_external_user_messages_when_session_has_no_direct_logs():
    from types import SimpleNamespace

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    fallback_rows = [
        _FakeRow(
            {
                'id': 'msg-fallback-1',
                'timestamp': datetime.datetime(2026, 4, 15, 9, 30, 0),
                'bot_id': 'bot-lark-1',
                'bot_name': '飞书客服机器人',
                'pipeline_id': 'pipeline-1',
                'pipeline_name': '客服流程',
                'message_content': '您好，我想咨询订单状态',
                'session_id': 'person_ou_customer_1',
                'status': 'success',
                'level': 'info',
                'platform': 'lark',
                'user_id': 'ou_customer_1',
                'user_name': '客户A',
                'runner_name': None,
                'variables': None,
                'role': 'user',
            }
        ),
        _FakeRow(
            {
                'id': 'msg-fallback-2',
                'timestamp': datetime.datetime(2026, 4, 15, 9, 31, 0),
                'bot_id': 'bot-lark-1',
                'bot_name': '飞书客服机器人',
                'pipeline_id': 'pipeline-1',
                'pipeline_name': '客服流程',
                'message_content': '已经为您转人工处理',
                'session_id': 'person_ou_customer_1',
                'status': 'success',
                'level': 'info',
                'platform': 'lark',
                'user_id': 'ou_customer_1',
                'user_name': '客户A',
                'runner_name': None,
                'variables': None,
                'role': 'assistant',
            }
        ),
    ]

    async def _execute_async(statement):
        statement_text = str(statement).lower()
        if 'from monitoring_messages' in statement_text:
            return _FakeListResult(fallback_rows)
        raise AssertionError(f'unexpected statement: {statement_text}')

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(side_effect=_execute_async)
    ap.persistence_mgr.serialize_model = Mock(
        side_effect=lambda _model, row: dict(row._mapping) if hasattr(row, '_mapping') else row
    )
    ap.monitoring_service.get_messages = AsyncMock(return_value=([], 0))
    ap.platform_mgr.get_bot_by_uuid = AsyncMock(
        return_value=SimpleNamespace(bot_entity=SimpleNamespace(name='飞书客服机器人'))
    )

    service = ServiceDeskService(ap)
    service._get_session = AsyncMock(
        return_value={
            'session_id': 'person_tenant-key-1:ou_customer_1',
            'bot_uuid': 'bot-lark-1',
            'pipeline_uuid': 'pipeline-1',
            'external_user_id': 'ou_customer_1',
            'handoff_reason': 'manual',
        }
    )

    detail = await service.get_session_detail('person_tenant-key-1:ou_customer_1')

    assert [item['id'] for item in detail['messages']] == [
        'msg-fallback-1',
        'msg-fallback-2',
    ]
    assert detail['messages'][0]['session_id'] == 'person_ou_customer_1'
    ap.monitoring_service.get_messages.assert_awaited_once_with(
        session_ids=['person_tenant-key-1:ou_customer_1'],
        limit=1000,
        offset=0,
    )


@pytest.mark.asyncio
async def test_get_session_detail_merges_direct_logs_with_external_user_history():
    from types import SimpleNamespace

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    direct_messages = [
        {
            'id': 'msg-direct-1',
            'timestamp': '2026-04-15T09:32:00',
            'message_content': '您好，这里是人工客服',
            'session_id': 'person_tenant-key-1:ou_customer_1',
            'role': 'assistant',
            'status': 'success',
            'level': 'info',
        }
    ]
    fallback_rows = [
        _FakeRow(
            {
                'id': 'msg-fallback-1',
                'timestamp': datetime.datetime(2026, 4, 15, 9, 30, 0),
                'bot_id': 'bot-lark-1',
                'bot_name': '飞书客服机器人',
                'pipeline_id': 'pipeline-1',
                'pipeline_name': '客服流程',
                'message_content': '您好，我想咨询订单状态',
                'session_id': 'person_ou_customer_1',
                'status': 'success',
                'level': 'info',
                'platform': 'lark',
                'user_id': 'ou_customer_1',
                'user_name': '客户A',
                'runner_name': None,
                'variables': None,
                'role': 'user',
            }
        )
    ]

    async def _execute_async(statement):
        statement_text = str(statement).lower()
        if 'from monitoring_messages' in statement_text:
            return _FakeListResult(fallback_rows)
        raise AssertionError(f'unexpected statement: {statement_text}')

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(side_effect=_execute_async)
    ap.persistence_mgr.serialize_model = Mock(
        side_effect=lambda _model, row: dict(row._mapping) if hasattr(row, '_mapping') else row
    )
    ap.monitoring_service.get_messages = AsyncMock(return_value=(direct_messages, 1))
    ap.platform_mgr.get_bot_by_uuid = AsyncMock(
        return_value=SimpleNamespace(bot_entity=SimpleNamespace(name='飞书客服机器人'))
    )

    service = ServiceDeskService(ap)
    service._get_session = AsyncMock(
        return_value={
            'session_id': 'person_tenant-key-1:ou_customer_1',
            'bot_uuid': 'bot-lark-1',
            'pipeline_uuid': 'pipeline-1',
            'external_user_id': 'ou_customer_1',
            'handoff_reason': 'manual',
        }
    )

    detail = await service.get_session_detail('person_tenant-key-1:ou_customer_1')

    assert [item['id'] for item in detail['messages']] == [
        'msg-fallback-1',
        'msg-direct-1',
    ]


@pytest.mark.asyncio
async def test_get_session_detail_uses_first_row_without_consuming_result_twice():
    from types import SimpleNamespace

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    session_row = _FakeRow({
        'session_id': 'person_ou_demo_1',
        'bot_uuid': 'bot-1',
        'pipeline_uuid': 'pipeline-1',
        'handoff_reason': None,
    })

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(
        return_value=_FakeSessionQueryResult(session_row)
    )
    ap.persistence_mgr.serialize_model = Mock(
        side_effect=lambda _model, row: dict(row._mapping) if hasattr(row, '_mapping') else row
    )
    ap.monitoring_service.get_messages = AsyncMock(return_value=([], 0))
    ap.platform_mgr.get_bot_by_uuid = AsyncMock(
        return_value=SimpleNamespace(bot_entity=SimpleNamespace(name='客服机器人'))
    )

    service = ServiceDeskService(ap)

    detail = await service.get_session_detail('person_ou_demo_1')

    assert detail['session']['session_id'] == 'person_ou_demo_1'
    assert detail['bot']['name'] == '客服机器人'


@pytest.mark.asyncio
async def test_upsert_binding_task_endpoint_delegates_to_wecom_private_service():
    from types import SimpleNamespace

    from langbot.pkg.api.http.controller.groups.service_desk import ServiceDeskRouterGroup

    quart_app = quart.Quart(__name__)
    ap = SimpleNamespace(
        service_desk_service=SimpleNamespace(),
        wecom_private_service=SimpleNamespace(
            upsert_binding_task=AsyncMock(
                return_value={
                    'session_id': 'person_cfg-1:wo123',
                    'verify_status': 'pending',
                }
            )
        ),
        user_service=SimpleNamespace(
            verify_jwt_token=AsyncMock(return_value='staff@example.com'),
            get_user_by_email=AsyncMock(return_value=SimpleNamespace(id='u-1', user='客服A')),
        ),
    )
    group = ServiceDeskRouterGroup(ap, quart_app)
    await group.initialize()

    response = await quart_app.test_client().post(
        '/api/v1/service-desk/sessions/person_cfg-1:wo123/binding-task',
        json={
            'requested_fields': ['uid', 'server'],
            'provided_uid': '10001',
            'provided_role_name': '战士阿明',
        },
        headers={'Authorization': 'Bearer fake'},
    )
    payload = await response.get_json()

    assert response.status_code == 200
    assert payload['data']['binding_task']['verify_status'] == 'pending'
    ap.wecom_private_service.upsert_binding_task.assert_awaited_once_with(
        session_id='person_cfg-1:wo123',
        data={
            'requested_fields': ['uid', 'server'],
            'provided_uid': '10001',
            'provided_role_name': '战士阿明',
        },
    )


@pytest.mark.asyncio
async def test_wecom_private_reception_config_endpoints_delegate_to_service():
    from types import SimpleNamespace

    from langbot.pkg.api.http.controller.groups.wecom_private import WecomPrivateRouterGroup

    quart_app = quart.Quart(__name__)
    ap = SimpleNamespace(
        wecom_private_service=SimpleNamespace(
            get_reception_config=AsyncMock(
                return_value={
                    'bot_uuid': 'bot-1',
                    'reception_enabled': True,
                    'welcome_enabled': True,
                    'fallback_reply_text': '',
                    'binding_required_fields': ['uid', 'server'],
                    'binding_trigger_keywords': [],
                    'binding_prompt_text': '',
                    'human_handoff_direct_enabled': True,
                }
            ),
            upsert_reception_config=AsyncMock(
                return_value={
                    'bot_uuid': 'bot-1',
                    'reception_enabled': False,
                    'welcome_enabled': False,
                    'fallback_reply_text': '请稍后再试',
                    'binding_required_fields': ['uid', 'server'],
                    'binding_trigger_keywords': ['绑定'],
                    'binding_prompt_text': '请提供角色名',
                    'human_handoff_direct_enabled': False,
                }
            ),
        ),
        user_service=SimpleNamespace(
            verify_jwt_token=AsyncMock(return_value='staff@example.com'),
            get_user_by_email=AsyncMock(return_value=SimpleNamespace(id='u-1', user='客服A')),
        ),
    )
    group = WecomPrivateRouterGroup(ap, quart_app)
    await group.initialize()

    client = quart_app.test_client()
    headers = {'Authorization': 'Bearer fake'}

    get_response = await client.get(
        '/api/v1/wecom-private/reception-config/bot-1',
        headers=headers,
    )
    get_payload = await get_response.get_json()

    assert get_response.status_code == 200
    assert get_payload['data']['config']['bot_uuid'] == 'bot-1'
    ap.wecom_private_service.get_reception_config.assert_awaited_once_with('bot-1')

    put_response = await client.put(
        '/api/v1/wecom-private/reception-config/bot-1',
        json={
            'reception_enabled': False,
            'binding_trigger_keywords': ['绑定'],
        },
        headers=headers,
    )
    put_payload = await put_response.get_json()

    assert put_response.status_code == 200
    assert put_payload['data']['config']['reception_enabled'] is False
    ap.wecom_private_service.upsert_reception_config.assert_awaited_once_with(
        'bot-1',
        {
            'reception_enabled': False,
            'binding_trigger_keywords': ['绑定'],
        },
    )


@pytest.mark.asyncio
async def test_close_session_endpoint_delegates_to_wecom_private_service():
    from types import SimpleNamespace

    from langbot.pkg.api.http.controller.groups.service_desk import ServiceDeskRouterGroup

    quart_app = quart.Quart(__name__)
    ap = SimpleNamespace(
        service_desk_service=SimpleNamespace(),
        wecom_private_service=SimpleNamespace(
            close_private_session=AsyncMock(
                return_value={'session_id': 'person_cfg-1:wo123', 'resolution_type': 'answered'}
            )
        ),
        user_service=SimpleNamespace(
            verify_jwt_token=AsyncMock(return_value='staff@example.com'),
            get_user_by_email=AsyncMock(return_value=SimpleNamespace(id='u-1', user='客服A')),
        ),
    )
    group = ServiceDeskRouterGroup(ap, quart_app)
    await group.initialize()

    response = await quart_app.test_client().post(
        '/api/v1/service-desk/sessions/person_cfg-1:wo123/close',
        json={
            'resolution_type': 'answered',
            'tag_updates': {'add': ['tag-a'], 'remove': []},
            'remark_text': '玩家 UID: 10001',
        },
        headers={'Authorization': 'Bearer fake'},
    )
    payload = await response.get_json()

    assert response.status_code == 200
    assert payload['data']['closure_record']['resolution_type'] == 'answered'
    ap.wecom_private_service.close_private_session.assert_awaited_once_with(
        session_id='person_cfg-1:wo123',
        operator_name='客服A',
        data={
            'resolution_type': 'answered',
            'tag_updates': {'add': ['tag-a'], 'remove': []},
            'remark_text': '玩家 UID: 10001',
        },
    )

import datetime
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.asyncio
async def test_sync_primary_contact_config_creates_remote_qr_and_persists_payload():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock()
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda _model, row: row)

    service = WecomPrivateService(ap)
    service._get_primary_contact_config = AsyncMock(return_value=None)
    service._build_external_contact_client = AsyncMock()
    service._build_external_contact_client.return_value.create_contact_way = AsyncMock(
        return_value={
            'errcode': 0,
            'config_id': 'cfg-1',
            'qr_code': 'https://qrcode.example/cfg-1',
        }
    )
    service._upsert_contact_config = AsyncMock()

    result = await service.sync_primary_contact_config(
        bot_uuid='bot-1',
        follow_user_id='zhangsan',
        state='dkd_phase1_entry',
        remark='DKD 私域固定二维码',
    )

    assert result['config_id'] == 'cfg-1'
    assert result['follow_user_ids'] == ['zhangsan']
    service._upsert_contact_config.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_primary_contact_config_updates_existing_remote_qr_before_refreshing_payload():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock()
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda _model, row: row)

    service = WecomPrivateService(ap)
    service._get_primary_contact_config = AsyncMock(
        return_value={
            'id': 'local-1',
            'bot_uuid': 'bot-1',
            'config_id': 'cfg-1',
            'qr_code_url': 'https://qrcode.example/old',
        }
    )
    service._build_external_contact_client = AsyncMock()
    client = service._build_external_contact_client.return_value
    client.update_contact_way = AsyncMock(return_value={'errcode': 0, 'errmsg': 'ok'})
    client.get_contact_way = AsyncMock(
        return_value={
            'contact_way': {
                'config_id': 'cfg-1',
                'qr_code': 'https://qrcode.example/cfg-1-new',
                'state': 'dkd_phase2_entry',
                'user': ['lisi'],
            }
        }
    )
    service._upsert_contact_config = AsyncMock()

    result = await service.sync_primary_contact_config(
        bot_uuid='bot-1',
        follow_user_id='lisi',
        state='dkd_phase2_entry',
        remark='DKD 私域固定二维码新版',
    )

    assert result['id'] == 'local-1'
    assert result['qr_code_url'] == 'https://qrcode.example/cfg-1-new'
    assert result['state'] == 'dkd_phase2_entry'
    assert result['follow_user_ids'] == ['lisi']
    assert result['remark'] == 'DKD 私域固定二维码新版'
    client.update_contact_way.assert_awaited_once_with(
        config_id='cfg-1',
        follow_user_id='lisi',
        state='dkd_phase2_entry',
        remark='DKD 私域固定二维码新版',
    )
    client.get_contact_way.assert_awaited_once_with(config_id='cfg-1')
    service._upsert_contact_config.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_contact_configs_returns_primary_first():
    from types import SimpleNamespace

    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    rows = [
        SimpleNamespace(id='cfg-1', is_primary=True, updated_at=1),
        SimpleNamespace(id='cfg-2', is_primary=False, updated_at=0),
    ]
    result = Mock()
    result.all.return_value = rows

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(return_value=result)
    ap.persistence_mgr.serialize_model = Mock(
        side_effect=lambda _model, row: {'id': row.id, 'is_primary': row.is_primary}
    )

    service = WecomPrivateService(ap)

    items = await service.list_contact_configs(bot_uuid='bot-1')

    assert items == [
        {'id': 'cfg-1', 'is_primary': True},
        {'id': 'cfg-2', 'is_primary': False},
    ]


@pytest.mark.asyncio
async def test_send_welcome_message_calls_external_contact_client():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    service = WecomPrivateService(ap)
    service._build_external_contact_client = AsyncMock()
    service._build_external_contact_client.return_value.send_welcome_message = AsyncMock(
        return_value={'errcode': 0, 'errmsg': 'ok'}
    )

    result = await service.send_welcome_message(
        bot_uuid='bot-1',
        welcome_code=' welcome-1 ',
        text=' 欢迎加入专属企微服务 ',
    )

    assert result['errcode'] == 0
    service._build_external_contact_client.return_value.send_welcome_message.assert_awaited_once_with(
        welcome_code='welcome-1',
        text='欢迎加入专属企微服务',
    )


@pytest.mark.asyncio
async def test_get_reception_config_returns_default_when_missing():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    service = WecomPrivateService(ap)
    service._get_reception_config = AsyncMock(return_value=None)

    config = await service.get_reception_config('bot-1')

    assert config == {
        'bot_uuid': 'bot-1',
        'reception_enabled': True,
        'welcome_enabled': True,
        'fallback_reply_text': '',
        'binding_required_fields': ['uid', 'server'],
        'binding_trigger_keywords': [],
        'binding_prompt_text': '',
        'human_handoff_direct_enabled': True,
    }


@pytest.mark.asyncio
async def test_upsert_reception_config_normalizes_text_and_list_fields():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    service = WecomPrivateService(ap)
    service._get_reception_config = AsyncMock(return_value=None)
    service._upsert_reception_config_row = AsyncMock(side_effect=lambda payload: payload)

    config = await service.upsert_reception_config(
        'bot-1',
        {
            'reception_enabled': False,
            'welcome_enabled': False,
            'fallback_reply_text': '  请稍后再试  ',
            'binding_required_fields': [' uid ', '', 'server '],
            'binding_trigger_keywords': [' 绑定 ', ' ', '', '人工'],
            'binding_prompt_text': '  请提供角色名  ',
            'human_handoff_direct_enabled': False,
        },
    )

    assert config == {
        'bot_uuid': 'bot-1',
        'reception_enabled': False,
        'welcome_enabled': False,
        'fallback_reply_text': '请稍后再试',
        'binding_required_fields': ['uid', 'server'],
        'binding_trigger_keywords': ['绑定', '人工'],
        'binding_prompt_text': '请提供角色名',
        'human_handoff_direct_enabled': False,
    }
    service._upsert_reception_config_row.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_reception_config_falls_back_to_default_required_fields_when_empty():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    service = WecomPrivateService(ap)
    service._get_reception_config = AsyncMock(return_value=None)
    service._upsert_reception_config_row = AsyncMock(side_effect=lambda payload: payload)

    config = await service.upsert_reception_config(
        'bot-1',
        {
            'binding_required_fields': [],
            'binding_trigger_keywords': ['  ', '触发'],
        },
    )

    assert config['binding_required_fields'] == ['uid', 'server']
    assert config['binding_trigger_keywords'] == ['触发']


@pytest.mark.asyncio
async def test_upsert_reception_config_preserves_existing_fields_on_partial_update():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    service = WecomPrivateService(ap)
    service._get_reception_config = AsyncMock(
        return_value={
            'bot_uuid': 'bot-1',
            'reception_enabled': False,
            'welcome_enabled': False,
            'fallback_reply_text': '旧兜底',
            'binding_required_fields': ['uid'],
            'binding_trigger_keywords': ['旧词'],
            'binding_prompt_text': '旧提示',
            'human_handoff_direct_enabled': False,
        }
    )
    service._upsert_reception_config_row = AsyncMock(side_effect=lambda payload: payload)

    config = await service.upsert_reception_config(
        'bot-1',
        {
            'binding_trigger_keywords': [' 新词 ', ' '],
        },
    )

    assert config == {
        'bot_uuid': 'bot-1',
        'reception_enabled': False,
        'welcome_enabled': False,
        'fallback_reply_text': '旧兜底',
        'binding_required_fields': ['uid'],
        'binding_trigger_keywords': ['新词'],
        'binding_prompt_text': '旧提示',
        'human_handoff_direct_enabled': False,
    }


@pytest.mark.asyncio
async def test_upsert_binding_task_preserves_existing_values_when_verify_status_omitted():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    service = WecomPrivateService(ap)
    completed_at = datetime.datetime(2026, 4, 19, 9, 0, 0)
    service._get_binding_task = AsyncMock(
        return_value={
            'id': 'binding-task-1',
            'session_id': 'person_cfg-1:wo123',
            'requested_fields': ['uid', 'server'],
            'provided_uid': '10001',
            'provided_server': 'S1',
            'provided_role_name': '旧角色名',
            'verify_status': 'completed',
            'completed_at': completed_at,
        }
    )
    service._assert_wecom_private_session = AsyncMock(
        return_value={'session_id': 'person_cfg-1:wo123'}
    )
    service._upsert_binding_task_row = AsyncMock(side_effect=lambda payload: payload)

    task = await service.upsert_binding_task(
        session_id='person_cfg-1:wo123',
        data={
            'provided_role_name': '战士阿明',
        },
    )

    assert task['id'] == 'binding-task-1'
    assert task['requested_fields'] == ['uid', 'server']
    assert task['provided_uid'] == '10001'
    assert task['provided_server'] == 'S1'
    assert task['provided_role_name'] == '战士阿明'
    assert task['verify_status'] == 'completed'
    assert task['completed_at'] == completed_at
    service._upsert_binding_task_row.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_binding_task_clears_completed_at_when_verify_status_changes():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    service = WecomPrivateService(ap)
    service._get_binding_task = AsyncMock(
        return_value={
            'id': 'binding-task-1',
            'session_id': 'person_cfg-1:wo123',
            'requested_fields': ['uid', 'server'],
            'provided_uid': '10001',
            'provided_server': 'S1',
            'verify_status': 'completed',
            'completed_at': datetime.datetime(2026, 4, 19, 9, 0, 0),
        }
    )
    service._assert_wecom_private_session = AsyncMock(
        return_value={'session_id': 'person_cfg-1:wo123'}
    )
    service._upsert_binding_task_row = AsyncMock(side_effect=lambda payload: payload)

    task = await service.upsert_binding_task(
        session_id='person_cfg-1:wo123',
        data={
            'verify_status': 'pending',
        },
    )

    assert task['id'] == 'binding-task-1'
    assert task['verify_status'] == 'pending'
    assert task['completed_at'] is None


@pytest.mark.asyncio
async def test_upsert_closure_record_does_not_overwrite_existing_id():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    existing_row = {
        'id': 'closure-1',
        'session_id': 'person_cfg-1:wo123',
        'resolution_type': 'answered',
    }
    update_values = {}

    class _Result:
        def __init__(self, row):
            self._row = row

        def first(self):
            return self._row

    async def _execute_async(statement):
        nonlocal update_values
        statement_text = str(statement).lower()
        if 'select' in statement_text and 'wecom_private_closure_records' in statement_text:
            params = statement.compile().params
            row_id = params.get('id_1')
            if row_id == 'closure-1':
                return _Result(existing_row)
            return _Result(existing_row)
        if 'update wecom_private_closure_records' in statement_text:
            update_values = statement.compile().params
            return Mock()
        raise AssertionError(f'unexpected statement: {statement_text}')

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(side_effect=_execute_async)
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda _model, row: row)

    service = WecomPrivateService(ap)

    record = await service._upsert_closure_record(
        {
            'id': 'closure-new',
            'session_id': 'person_cfg-1:wo123',
            'resolution_type': 'escalated',
            'tag_updates': {'add': [], 'remove': []},
            'followup_needed': False,
            'knowledge_feedback': 'retry',
            'closed_by': '客服A',
        }
    )

    assert record['id'] == 'closure-1'
    assert 'id' not in update_values


@pytest.mark.asyncio
async def test_close_private_session_writes_tags_remark_and_sets_closed_state():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock()
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda _model, row: row)

    service = WecomPrivateService(ap)
    service._get_session = AsyncMock(
        return_value={
            'session_id': 'person_cfg-1:wo123',
            'bot_uuid': 'bot-1',
            'lead_id': 'lead-1',
            'queue_status': 'manual',
        }
    )
    service._get_lead = AsyncMock(
        return_value={
            'id': 'lead-1',
            'external_userid': 'wo123',
            'follow_user_id': 'zhangsan',
        }
    )
    service._build_external_contact_client = AsyncMock()
    client = service._build_external_contact_client.return_value
    client.mark_tags = AsyncMock(return_value={'errcode': 0, 'errmsg': 'ok'})
    client.update_remark = AsyncMock(return_value={'errcode': 0, 'errmsg': 'ok'})
    service._upsert_closure_record = AsyncMock(return_value={'session_id': 'person_cfg-1:wo123'})
    service._mark_session_closed = AsyncMock()

    record = await service.close_private_session(
        session_id='person_cfg-1:wo123',
        operator_name='客服A',
        data={
            'resolution_type': 'answered',
            'tag_updates': {'add': ['tag-a'], 'remove': []},
            'remark_text': '玩家 UID: 10001 / 区服: S1',
            'followup_needed': False,
            'knowledge_feedback': '补充充值 FAQ',
        },
    )

    assert record['session_id'] == 'person_cfg-1:wo123'
    client.mark_tags.assert_awaited_once()
    client.update_remark.assert_awaited_once()
    service._mark_session_closed.assert_awaited_once_with('person_cfg-1:wo123')


@pytest.mark.asyncio
async def test_get_session_overlay_returns_lead_routing_binding_and_closure():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock()
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda _model, row: row)

    service = WecomPrivateService(ap)
    service._get_session = AsyncMock(
        return_value={'session_id': 'person_cfg-1:wo123', 'lead_id': 'lead-1'}
    )
    service._get_lead = AsyncMock(
        return_value={'id': 'lead-1', 'external_userid': 'wo123'}
    )
    service._list_routing_decisions = AsyncMock(
        return_value=[{'decision': 'pending_manual'}]
    )
    service._get_binding_task = AsyncMock(
        return_value={'session_id': 'person_cfg-1:wo123', 'verify_status': 'pending'}
    )
    service._get_closure_record = AsyncMock(return_value=None)

    overlay = await service.get_session_overlay('person_cfg-1:wo123')

    assert overlay['lead']['id'] == 'lead-1'
    assert overlay['routing_decisions'][0]['decision'] == 'pending_manual'
    assert overlay['binding_task']['verify_status'] == 'pending'
    assert overlay['closure_record'] is None

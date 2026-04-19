import json

import pytest


@pytest.mark.asyncio
async def test_claim_session_sets_manual_owner():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    service = ServiceDeskService(ap=None)

    with pytest.raises(AttributeError):
        await service.claim_session('session-1', 'user-1', '客服A')


@pytest.mark.asyncio
async def test_release_manual_session_clears_owner_and_returns_to_pending_manual():
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    service = ServiceDeskService(Mock())
    service._get_session = AsyncMock(
        return_value={
            'session_id': 'person_release_1',
            'mode': 'manual',
            'queue_status': 'manual',
            'claimed_by_user_uuid': 'user-1',
        }
    )
    service._update_session_state = AsyncMock()

    await service.release_session('person_release_1')

    service._update_session_state.assert_awaited_once_with(
        'person_release_1',
        mode='manual',
        queue_status='pending_manual',
        claimed_by_user_uuid=None,
        claimed_by_user_name=None,
        manual_claimed_at=None,
    )


@pytest.mark.asyncio
async def test_list_quick_replies_returns_enabled_materials():
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    service = ServiceDeskService(Mock())
    service.list_materials = AsyncMock(
        return_value=[
            {
                'uuid': 'm1',
                'material_type': 'quick_reply',
                'title': '问候',
                'reply_text': '您好，有什么可以帮您？',
                'enabled': True,
            },
            {
                'uuid': 'm2',
                'material_type': 'gift_pack',
                'title': '礼包',
                'reply_text': '这是礼包链接',
                'enabled': True,
            },
            {
                'uuid': 'm3',
                'material_type': 'quick_reply',
                'title': '停用',
                'reply_text': '不应返回',
                'enabled': False,
            },
            {
                'uuid': 'm4',
                'material_type': 'knowledge',
                'title': '非快捷回复',
                'reply_text': '不应返回',
                'enabled': True,
            },
        ]
    )

    items = await service.list_quick_replies(bot_uuid='bot-1')

    assert [item['uuid'] for item in items] == ['m1', 'm2']
    assert all(item['enabled'] is True for item in items)


def test_match_material_returns_highest_priority_hit():
    from langbot.pkg.api.http.service.service_desk import match_material

    materials = [
        {'title': '礼包', 'priority': 20, 'trigger_keywords': ['礼包'], 'reply_text': '礼包A'},
        {'title': '下载', 'priority': 10, 'trigger_keywords': ['下载'], 'reply_text': '下载A'},
    ]

    matched = match_material('我要下载链接', materials)

    assert matched['title'] == '下载'


def test_match_material_skips_disabled_material():
    from langbot.pkg.api.http.service.service_desk import match_material

    materials = [
        {
            'title': '下载-停用',
            'priority': 5,
            'trigger_keywords': ['下载'],
            'reply_text': '停用素材',
            'enabled': False,
        },
        {
            'title': '下载-启用',
            'priority': 10,
            'trigger_keywords': ['下载'],
            'reply_text': '启用素材',
            'enabled': True,
        },
    ]

    matched = match_material('我要下载链接', materials)

    assert matched['title'] == '下载-启用'


@pytest.mark.asyncio
async def test_handle_incoming_message_accepts_any_adapter_with_service_desk_context():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    service = ServiceDeskService(Mock())
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_customer-1',
            'mode': 'ai_hosted',
            'queue_status': 'ai',
            'manual_claimed_at': None,
            'silent_since': None,
        }
    )
    service.get_bot_config = AsyncMock(return_value={'enabled': True})
    service.list_materials = AsyncMock(return_value=[])

    bot_entity = SimpleNamespace(
        adapter='wecomweb',
        uuid='bot-1',
        use_pipeline_uuid='pipeline-1',
    )
    event = SimpleNamespace(
        message_chain='你好',
        source_platform_object=SimpleNamespace(),
        sender=SimpleNamespace(id='customer-1', nickname='客户A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'escort-account',
        'external_user_id': 'external-customer-1',
        'last_message_id': 'msg-1',
    }
    adapter.get_launcher_id.return_value = 'escort-account:external-customer-1'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipeline-1',
    )

    assert decision.action == 'continue_ai'
    service._touch_session.assert_awaited_once()
    service.list_materials.assert_awaited_once_with('bot-1')


@pytest.mark.asyncio
async def test_handle_incoming_message_bootstraps_private_lead_before_pipeline():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.wecom_private_service.bootstrap_private_lead = AsyncMock(
        return_value={'id': 'lead-1', 'profile_status': 'anonymous'}
    )
    ap.wecom_private_service.record_routing_decision = AsyncMock()

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_cfg-1:wo123',
            'mode': 'ai_hosted',
            'queue_status': 'ai',
            'manual_claimed_at': None,
            'silent_since': None,
        }
    )
    service.get_bot_config = AsyncMock(return_value={'enabled': True, 'handoff_keywords': []})
    service.list_materials = AsyncMock(return_value=[])
    service._update_session_state = AsyncMock()

    bot_entity = SimpleNamespace(adapter='wecomprivate', uuid='bot-1', use_pipeline_uuid='pipe-1')
    event = SimpleNamespace(
        message_chain='你好',
        source_platform_object=SimpleNamespace(
            entry_id='cfg-1',
            follow_user_id='zhangsan',
            external_user_id='wo123',
            message_id='msg-1',
            welcome_code=None,
        ),
        sender=SimpleNamespace(id='wo123', nickname='玩家A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'cfg-1',
        'external_user_id': 'wo123',
        'last_message_id': 'msg-1',
    }
    adapter.get_launcher_id.return_value = 'cfg-1:wo123'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipe-1',
    )

    assert decision.action == 'continue_ai'
    ap.wecom_private_service.bootstrap_private_lead.assert_awaited_once_with(
        bot_uuid='bot-1',
        external_user_id='wo123',
        follow_user_id='zhangsan',
        source_entry_id='cfg-1',
    )
    service._touch_session.assert_awaited_once_with(
        session_id='person_cfg-1:wo123',
        bot_uuid='bot-1',
        pipeline_uuid='pipe-1',
        context={
            'source_entry_id': 'cfg-1',
            'external_user_id': 'wo123',
            'last_message_id': 'msg-1',
        },
        sender_name='玩家A',
        lead_id='lead-1',
    )


@pytest.mark.asyncio
async def test_handle_incoming_message_sends_wecom_private_welcome_message_when_welcome_code_present():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.wecom_private_service.bootstrap_private_lead = AsyncMock(
        return_value={'id': 'lead-1', 'profile_status': 'anonymous'}
    )
    ap.wecom_private_service.send_welcome_message = AsyncMock(
        return_value={'errcode': 0, 'errmsg': 'ok'}
    )
    ap.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(
        return_value=SimpleNamespace(
            pipeline_entity=SimpleNamespace(
                config={
                    'ai': {
                        'local-agent': {
                            'opening-intro': '老板你好，欢迎来到专属企微服务。',
                        }
                    }
                }
            )
        )
    )

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_cfg-1:wo123',
            'mode': 'ai_hosted',
            'queue_status': 'ai',
            'manual_claimed_at': None,
            'silent_since': None,
        }
    )
    service.get_bot_config = AsyncMock(return_value={'enabled': True, 'handoff_keywords': []})
    service.list_materials = AsyncMock(return_value=[])
    service._update_session_state = AsyncMock()

    bot_entity = SimpleNamespace(adapter='wecomprivate', uuid='bot-1', use_pipeline_uuid='pipe-1')
    event = SimpleNamespace(
        message_chain='',
        source_platform_object=SimpleNamespace(
            entry_id='cfg-1',
            follow_user_id='zhangsan',
            external_user_id='wo123',
            message_id='msg-1',
            welcome_code='welcome-1',
        ),
        sender=SimpleNamespace(id='wo123', nickname='玩家A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'cfg-1',
        'external_user_id': 'wo123',
        'last_message_id': 'msg-1',
    }
    adapter.get_launcher_id.return_value = 'cfg-1:wo123'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipe-1',
    )

    assert decision.action == 'continue_ai'
    ap.wecom_private_service.send_welcome_message.assert_awaited_once_with(
        bot_uuid='bot-1',
        welcome_code='welcome-1',
        text='老板你好，欢迎来到专属企微服务。',
    )


@pytest.mark.asyncio
async def test_handle_incoming_message_skips_wecom_private_welcome_message_without_welcome_code():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.wecom_private_service.bootstrap_private_lead = AsyncMock(
        return_value={'id': 'lead-1', 'profile_status': 'anonymous'}
    )
    ap.wecom_private_service.send_welcome_message = AsyncMock()
    ap.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(
        return_value=SimpleNamespace(
            pipeline_entity=SimpleNamespace(
                config={
                    'ai': {
                        'local-agent': {
                            'opening-intro': '老板你好，欢迎来到专属企微服务。',
                        }
                    }
                }
            )
        )
    )

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_cfg-1:wo123',
            'mode': 'ai_hosted',
            'queue_status': 'ai',
            'manual_claimed_at': None,
            'silent_since': None,
        }
    )
    service.get_bot_config = AsyncMock(return_value={'enabled': True, 'handoff_keywords': []})
    service.list_materials = AsyncMock(return_value=[])
    service._update_session_state = AsyncMock()

    bot_entity = SimpleNamespace(adapter='wecomprivate', uuid='bot-1', use_pipeline_uuid='pipe-1')
    event = SimpleNamespace(
        message_chain='你好',
        source_platform_object=SimpleNamespace(
            entry_id='cfg-1',
            follow_user_id='zhangsan',
            external_user_id='wo123',
            message_id='msg-2',
            welcome_code=None,
        ),
        sender=SimpleNamespace(id='wo123', nickname='玩家A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'cfg-1',
        'external_user_id': 'wo123',
        'last_message_id': 'msg-2',
    }
    adapter.get_launcher_id.return_value = 'cfg-1:wo123'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipe-1',
    )

    assert decision.action == 'continue_ai'
    ap.wecom_private_service.send_welcome_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_incoming_message_skips_wecom_private_welcome_message_when_intro_blank():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.wecom_private_service.bootstrap_private_lead = AsyncMock(
        return_value={'id': 'lead-1', 'profile_status': 'anonymous'}
    )
    ap.wecom_private_service.send_welcome_message = AsyncMock()
    ap.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(
        return_value=SimpleNamespace(
            pipeline_entity=SimpleNamespace(
                config={
                    'ai': {
                        'local-agent': {
                            'opening-intro': '   ',
                        }
                    }
                }
            )
        )
    )

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_cfg-1:wo123',
            'mode': 'ai_hosted',
            'queue_status': 'ai',
            'manual_claimed_at': None,
            'silent_since': None,
        }
    )
    service.get_bot_config = AsyncMock(return_value={'enabled': True, 'handoff_keywords': []})
    service.list_materials = AsyncMock(return_value=[])
    service._update_session_state = AsyncMock()

    bot_entity = SimpleNamespace(adapter='wecomprivate', uuid='bot-1', use_pipeline_uuid='pipe-1')
    event = SimpleNamespace(
        message_chain='',
        source_platform_object=SimpleNamespace(
            entry_id='cfg-1',
            follow_user_id='zhangsan',
            external_user_id='wo123',
            message_id='msg-1',
            welcome_code='welcome-1',
        ),
        sender=SimpleNamespace(id='wo123', nickname='玩家A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'cfg-1',
        'external_user_id': 'wo123',
        'last_message_id': 'msg-1',
    }
    adapter.get_launcher_id.return_value = 'cfg-1:wo123'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipe-1',
    )

    assert decision.action == 'continue_ai'
    ap.wecom_private_service.send_welcome_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_incoming_message_skips_wecom_private_welcome_message_when_reception_disabled():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.wecom_private_service.bootstrap_private_lead = AsyncMock(
        return_value={'id': 'lead-1', 'profile_status': 'anonymous'}
    )
    ap.wecom_private_service.get_reception_config = AsyncMock(
        return_value={'reception_enabled': False, 'welcome_enabled': True}
    )
    ap.wecom_private_service.send_welcome_message = AsyncMock()
    ap.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(
        return_value=SimpleNamespace(
            pipeline_entity=SimpleNamespace(
                config={
                    'ai': {
                        'local-agent': {
                            'opening-intro': '老板你好，欢迎来到专属企微服务。',
                        }
                    }
                }
            )
        )
    )

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_cfg-1:wo123',
            'mode': 'ai_hosted',
            'queue_status': 'ai',
            'manual_claimed_at': None,
            'silent_since': None,
        }
    )
    service.get_bot_config = AsyncMock(return_value={'enabled': True, 'handoff_keywords': []})
    service.list_materials = AsyncMock(return_value=[])
    service._update_session_state = AsyncMock()

    bot_entity = SimpleNamespace(adapter='wecomprivate', uuid='bot-1', use_pipeline_uuid='pipe-1')
    event = SimpleNamespace(
        message_chain='你好',
        source_platform_object=SimpleNamespace(
            entry_id='cfg-1',
            follow_user_id='zhangsan',
            external_user_id='wo123',
            message_id='msg-2',
            welcome_code='welcome-1',
        ),
        sender=SimpleNamespace(id='wo123', nickname='玩家A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'cfg-1',
        'external_user_id': 'wo123',
        'last_message_id': 'msg-2',
    }
    adapter.get_launcher_id.return_value = 'cfg-1:wo123'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipe-1',
    )

    assert decision.action == 'continue_ai'
    ap.wecom_private_service.send_welcome_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_incoming_message_skips_wecom_private_welcome_message_when_welcome_disabled():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.wecom_private_service.bootstrap_private_lead = AsyncMock(
        return_value={'id': 'lead-1', 'profile_status': 'anonymous'}
    )
    ap.wecom_private_service.get_reception_config = AsyncMock(
        return_value={'reception_enabled': True, 'welcome_enabled': False}
    )
    ap.wecom_private_service.send_welcome_message = AsyncMock()
    ap.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(
        return_value=SimpleNamespace(
            pipeline_entity=SimpleNamespace(
                config={
                    'ai': {
                        'local-agent': {
                            'opening-intro': '老板你好，欢迎来到专属企微服务。',
                        }
                    }
                }
            )
        )
    )

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_cfg-1:wo123',
            'mode': 'ai_hosted',
            'queue_status': 'ai',
            'manual_claimed_at': None,
            'silent_since': None,
        }
    )
    service.get_bot_config = AsyncMock(return_value={'enabled': True, 'handoff_keywords': []})
    service.list_materials = AsyncMock(return_value=[])
    service._update_session_state = AsyncMock()

    bot_entity = SimpleNamespace(adapter='wecomprivate', uuid='bot-1', use_pipeline_uuid='pipe-1')
    event = SimpleNamespace(
        message_chain='你好',
        source_platform_object=SimpleNamespace(
            entry_id='cfg-1',
            follow_user_id='zhangsan',
            external_user_id='wo123',
            message_id='msg-2',
            welcome_code='welcome-1',
        ),
        sender=SimpleNamespace(id='wo123', nickname='玩家A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'cfg-1',
        'external_user_id': 'wo123',
        'last_message_id': 'msg-2',
    }
    adapter.get_launcher_id.return_value = 'cfg-1:wo123'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipe-1',
    )

    assert decision.action == 'continue_ai'
    ap.wecom_private_service.send_welcome_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_structured_reply_uses_service_desk_sender_and_runtime_adapter_platform():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.monitoring_service.record_message = AsyncMock()
    service = ServiceDeskService(ap)

    runtime_bot = SimpleNamespace(
        adapter=SimpleNamespace(send_service_desk_text=AsyncMock()),
        bot_entity=SimpleNamespace(
            uuid='bot-1',
            name='飞书客服机器人',
            use_pipeline_uuid='pipeline-1',
            use_pipeline_name='飞书流程',
            adapter='lark',
        ),
    )
    event = SimpleNamespace(
        source_platform_object=SimpleNamespace(),
        sender=SimpleNamespace(id='ou_customer_1', nickname='客户A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'tenant-key-1',
        'external_user_id': 'ou_customer_1',
        'last_message_id': 'om_dc1321',
    }
    adapter.get_launcher_id.return_value = 'tenant-key-1:ou_customer_1'

    await service.send_structured_reply(
        runtime_bot=runtime_bot,
        event=event,
        adapter=adapter,
        material={'reply_text': '您好，这里是飞书客服'},
    )

    runtime_bot.adapter.send_service_desk_text.assert_awaited_once_with(
        {
            'source_entry_id': 'tenant-key-1',
            'external_user_id': 'ou_customer_1',
            'last_message_id': 'om_dc1321',
        },
        '您好，这里是飞书客服',
    )
    ap.monitoring_service.record_message.assert_awaited_once_with(
        bot_id='bot-1',
        bot_name='飞书客服机器人',
        pipeline_id='pipeline-1',
        pipeline_name='飞书流程',
        message_content='您好，这里是飞书客服',
        session_id='person_tenant-key-1:ou_customer_1',
        status='success',
        level='info',
        platform='lark',
        user_id='ou_customer_1',
        user_name='客户A',
        role='assistant',
    )


class _FakeMessageChain:
    def __init__(self, text: str):
        self._text = text

    def __str__(self) -> str:
        return self._text

    def model_dump(self):
        return [
            {'type': 'Source'},
            {'type': 'Plain', 'text': self._text},
        ]


@pytest.mark.asyncio
async def test_touch_session_initializes_unclaimed_session_without_customer_name_as_claimed_owner():
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock()

    service = ServiceDeskService(ap)
    service._get_session = AsyncMock(
        side_effect=[
            None,
            {'session_id': 'person_cfg-1:wo123', 'claimed_by_user_name': None},
        ]
    )

    await service._touch_session(
        session_id='person_cfg-1:wo123',
        bot_uuid='bot-1',
        pipeline_uuid='pipe-1',
        context={
            'source_entry_id': 'cfg-1',
            'external_user_id': 'wo123',
            'last_message_id': 'msg-1',
        },
        sender_name='客户A',
    )

    insert_stmt = ap.persistence_mgr.execute_async.await_args.args[0]
    assert insert_stmt.compile().params['claimed_by_user_name'] is None
    assert insert_stmt.compile().params['claimed_by_user_uuid'] is None


@pytest.mark.asyncio
async def test_handle_incoming_message_records_user_message_when_manual_session_skips_pipeline():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.monitoring_service.record_message = AsyncMock()
    ap.monitoring_service.update_session_activity = AsyncMock(return_value=True)

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_escort-account:external-customer-1',
            'mode': 'manual',
            'queue_status': 'manual',
            'manual_claimed_at': None,
            'silent_since': None,
        }
    )
    service.get_bot_config = AsyncMock(return_value={'enabled': True})
    service.list_materials = AsyncMock(return_value=[])

    bot_entity = SimpleNamespace(
        adapter='wecomweb',
        uuid='bot-1',
        name='客服机器人',
        use_pipeline_uuid='pipeline-1',
        use_pipeline_name='默认流程',
    )
    event = SimpleNamespace(
        message_chain=_FakeMessageChain('我补充一下订单号'),
        source_platform_object=SimpleNamespace(),
        sender=SimpleNamespace(id='customer-1', nickname='客户A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'escort-account',
        'external_user_id': 'external-customer-1',
        'last_message_id': 'msg-1',
    }
    adapter.get_launcher_id.return_value = 'escort-account:external-customer-1'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipeline-1',
    )

    assert decision.action == 'skip_pipeline'
    ap.monitoring_service.record_message.assert_awaited_once_with(
        bot_id='bot-1',
        bot_name='客服机器人',
        pipeline_id='pipeline-1',
        pipeline_name='默认流程',
        message_content=json.dumps(
            [
                {'type': 'Source'},
                {'type': 'Plain', 'text': '我补充一下订单号'},
            ],
            ensure_ascii=False,
        ),
        session_id='person_escort-account:external-customer-1',
        status='success',
        level='info',
        platform='wecomweb',
        user_id='external-customer-1',
        user_name='客户A',
        role='user',
    )


@pytest.mark.asyncio
async def test_handle_incoming_message_records_user_message_when_pending_manual_session_skips_pipeline():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.monitoring_service.record_message = AsyncMock()
    ap.monitoring_service.update_session_activity = AsyncMock(return_value=True)

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_escort-account:external-customer-pending',
            'mode': 'manual',
            'queue_status': 'pending_manual',
            'manual_claimed_at': None,
            'silent_since': None,
        }
    )
    service.get_bot_config = AsyncMock(return_value={'enabled': True})
    service.list_materials = AsyncMock(return_value=[])

    bot_entity = SimpleNamespace(
        adapter='wecomweb',
        uuid='bot-1',
        name='客服机器人',
        use_pipeline_uuid='pipeline-1',
        use_pipeline_name='默认流程',
    )
    event = SimpleNamespace(
        message_chain=_FakeMessageChain('人工那边看到了吗'),
        source_platform_object=SimpleNamespace(),
        sender=SimpleNamespace(id='customer-pending', nickname='客户P'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'escort-account',
        'external_user_id': 'external-customer-pending',
        'last_message_id': 'msg-pending-1',
    }
    adapter.get_launcher_id.return_value = 'escort-account:external-customer-pending'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipeline-1',
    )

    assert decision.action == 'skip_pipeline'
    assert decision.reason == 'pending_manual'
    ap.monitoring_service.record_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_incoming_message_records_user_message_when_keyword_handoff_triggers_pending_manual():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.monitoring_service.record_message = AsyncMock()
    ap.monitoring_service.update_session_activity = AsyncMock(return_value=True)

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_escort-account:external-customer-2',
            'mode': 'ai_hosted',
            'queue_status': 'ai',
            'manual_claimed_at': None,
            'silent_since': None,
        }
    )
    service.get_bot_config = AsyncMock(
        return_value={'enabled': True, 'handoff_keywords': ['人工']}
    )
    service.list_materials = AsyncMock(return_value=[])
    service._update_session_state = AsyncMock()

    bot_entity = SimpleNamespace(
        adapter='wecomweb',
        uuid='bot-1',
        name='客服机器人',
        use_pipeline_uuid='pipeline-1',
        use_pipeline_name='默认流程',
    )
    event = SimpleNamespace(
        message_chain=_FakeMessageChain('我要人工处理'),
        source_platform_object=SimpleNamespace(),
        sender=SimpleNamespace(id='customer-2', nickname='客户B'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'escort-account',
        'external_user_id': 'external-customer-2',
        'last_message_id': 'msg-2',
    }
    adapter.get_launcher_id.return_value = 'escort-account:external-customer-2'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipeline-1',
    )

    assert decision.action == 'skip_pipeline'
    assert decision.reason == 'pending_manual'
    service._update_session_state.assert_awaited_once_with(
        'person_escort-account:external-customer-2',
        mode='manual',
        queue_status='pending_manual',
        handoff_reason='keyword',
    )
    ap.monitoring_service.record_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_incoming_message_records_private_routing_decision_when_keyword_handoff_triggers():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.monitoring_service.record_message = AsyncMock()
    ap.monitoring_service.update_session_activity = AsyncMock(return_value=True)
    ap.wecom_private_service.bootstrap_private_lead = AsyncMock(return_value={'id': 'lead-1'})
    ap.wecom_private_service.record_routing_decision = AsyncMock()

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_cfg-1:wo123',
            'mode': 'ai_hosted',
            'queue_status': 'ai',
            'manual_claimed_at': None,
            'silent_since': None,
        }
    )
    service.get_bot_config = AsyncMock(
        return_value={'enabled': True, 'handoff_keywords': ['人工', '投诉']}
    )
    service.list_materials = AsyncMock(return_value=[])
    service._update_session_state = AsyncMock()

    bot_entity = SimpleNamespace(
        adapter='wecomprivate',
        uuid='bot-1',
        name='私域客服机器人',
        use_pipeline_uuid='pipeline-1',
        use_pipeline_name='默认流程',
    )
    event = SimpleNamespace(
        message_chain=_FakeMessageChain('我要人工处理'),
        source_platform_object=SimpleNamespace(
            follow_user_id='zhangsan',
        ),
        sender=SimpleNamespace(id='wo123', nickname='客户A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'cfg-1',
        'external_user_id': 'wo123',
        'last_message_id': 'msg-2',
    }
    adapter.get_launcher_id.return_value = 'cfg-1:wo123'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipeline-1',
    )

    assert decision.action == 'skip_pipeline'
    assert decision.reason == 'pending_manual'
    ap.wecom_private_service.record_routing_decision.assert_awaited_once_with(
        session_id='person_cfg-1:wo123',
        trigger_type='rule',
        trigger_reason='keyword',
        decision='pending_manual',
        matched_rule='人工',
        confidence=1.0,
    )


@pytest.mark.asyncio
async def test_handle_incoming_message_returns_binding_prompt_and_skips_pipeline_when_required_fields_missing():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.monitoring_service.record_message = AsyncMock()
    ap.monitoring_service.update_session_activity = AsyncMock(return_value=True)
    ap.wecom_private_service.bootstrap_private_lead = AsyncMock(return_value={'id': 'lead-1'})
    ap.wecom_private_service.get_reception_config = AsyncMock(
        return_value={
            'reception_enabled': True,
            'welcome_enabled': True,
            'binding_required_fields': ['uid', 'server', 'role_name'],
            'binding_trigger_keywords': ['绑定'],
            'binding_prompt_text': '请补充 UID / 区服 / 角色名',
            'fallback_reply_text': '',
        }
    )
    ap.wecom_private_service.get_session_overlay = AsyncMock(
        return_value={'binding_task': None}
    )
    ap.wecom_private_service.upsert_binding_task = AsyncMock(
        return_value={'id': 'binding-1'}
    )
    ap.wecom_private_service.record_routing_decision = AsyncMock()

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_cfg-1:wo123',
            'mode': 'ai_hosted',
            'queue_status': 'ai',
            'manual_claimed_at': None,
            'silent_since': None,
            'unresolved_count': 0,
        }
    )
    service.get_bot_config = AsyncMock(
        return_value={'enabled': True, 'handoff_keywords': [], 'fallback_unresolved_count': 2}
    )
    service.list_materials = AsyncMock(return_value=[])
    service._update_session_state = AsyncMock()

    bot_entity = SimpleNamespace(
        adapter='wecomprivate',
        uuid='bot-1',
        name='私域客服机器人',
        use_pipeline_uuid='pipeline-1',
        use_pipeline_name='默认流程',
    )
    event = SimpleNamespace(
        message_chain=_FakeMessageChain('我要绑定 UID:12345 角色名：战士阿明'),
        source_platform_object=SimpleNamespace(
            follow_user_id='zhangsan',
            welcome_code=None,
        ),
        sender=SimpleNamespace(id='wo123', nickname='客户A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'cfg-1',
        'external_user_id': 'wo123',
        'last_message_id': 'msg-2',
    }
    adapter.get_launcher_id.return_value = 'cfg-1:wo123'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipeline-1',
    )

    assert decision.action == 'send_material_and_skip'
    assert decision.reason == 'binding_required'
    assert decision.material['reply_text'] == '请补充 UID / 区服 / 角色名'
    ap.wecom_private_service.upsert_binding_task.assert_awaited_once_with(
        session_id='person_cfg-1:wo123',
        data={
            'requested_fields': ['uid', 'server', 'role_name'],
            'provided_uid': '12345',
            'provided_server': None,
            'provided_role_name': '战士阿明',
            'verify_status': 'pending',
        },
    )
    service._update_session_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_incoming_message_updates_pending_binding_task_on_followup_without_trigger_keyword():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.monitoring_service.record_message = AsyncMock()
    ap.monitoring_service.update_session_activity = AsyncMock(return_value=True)
    ap.wecom_private_service.bootstrap_private_lead = AsyncMock(return_value={'id': 'lead-1'})
    ap.wecom_private_service.get_reception_config = AsyncMock(
        return_value={
            'reception_enabled': True,
            'welcome_enabled': True,
            'binding_required_fields': ['uid', 'server', 'role_name'],
            'binding_trigger_keywords': ['绑定'],
            'binding_prompt_text': '请补充 UID / 区服 / 角色名',
            'fallback_reply_text': '',
        }
    )
    ap.wecom_private_service.get_session_overlay = AsyncMock(
        return_value={
            'binding_task': {
                'session_id': 'person_cfg-1:wo123',
                'requested_fields': ['uid', 'server', 'role_name'],
                'provided_uid': '12345',
                'provided_server': None,
                'provided_role_name': None,
                'verify_status': 'pending',
            }
        }
    )
    ap.wecom_private_service.upsert_binding_task = AsyncMock(
        return_value={'id': 'binding-1', 'verify_status': 'completed'}
    )
    ap.wecom_private_service.record_routing_decision = AsyncMock()

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_cfg-1:wo123',
            'mode': 'ai_hosted',
            'queue_status': 'ai',
            'manual_claimed_at': None,
            'silent_since': None,
            'unresolved_count': 0,
        }
    )
    service.get_bot_config = AsyncMock(
        return_value={'enabled': True, 'handoff_keywords': [], 'fallback_unresolved_count': 2}
    )
    service.list_materials = AsyncMock(return_value=[])
    service._update_session_state = AsyncMock()

    bot_entity = SimpleNamespace(
        adapter='wecomprivate',
        uuid='bot-1',
        name='私域客服机器人',
        use_pipeline_uuid='pipeline-1',
        use_pipeline_name='默认流程',
    )
    event = SimpleNamespace(
        message_chain=_FakeMessageChain('区服：S1 角色名：战士阿明'),
        source_platform_object=SimpleNamespace(
            follow_user_id='zhangsan',
            welcome_code=None,
        ),
        sender=SimpleNamespace(id='wo123', nickname='客户A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'cfg-1',
        'external_user_id': 'wo123',
        'last_message_id': 'msg-5',
    }
    adapter.get_launcher_id.return_value = 'cfg-1:wo123'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipeline-1',
    )

    assert decision.action == 'continue_ai'
    ap.wecom_private_service.upsert_binding_task.assert_awaited_once_with(
        session_id='person_cfg-1:wo123',
        data={
            'requested_fields': ['uid', 'server', 'role_name'],
            'provided_uid': '12345',
            'provided_server': 'S1',
            'provided_role_name': '战士阿明',
            'verify_status': 'completed',
        },
    )
    service._update_session_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_incoming_message_fallbacks_to_pending_manual_when_unresolved_threshold_reached():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.monitoring_service.record_message = AsyncMock()
    ap.monitoring_service.update_session_activity = AsyncMock(return_value=True)
    ap.wecom_private_service.bootstrap_private_lead = AsyncMock(return_value={'id': 'lead-1'})
    ap.wecom_private_service.get_reception_config = AsyncMock(
        return_value={
            'reception_enabled': True,
            'welcome_enabled': True,
            'binding_required_fields': ['uid', 'server'],
            'binding_trigger_keywords': ['绑定'],
            'binding_prompt_text': '请补充 UID / 区服',
            'fallback_reply_text': '已为你转人工，请稍候。',
        }
    )
    ap.wecom_private_service.get_session_overlay = AsyncMock(
        return_value={'binding_task': None}
    )
    ap.wecom_private_service.record_routing_decision = AsyncMock()

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_cfg-1:wo123',
            'mode': 'ai_hosted',
            'queue_status': 'ai',
            'manual_claimed_at': None,
            'silent_since': None,
            'unresolved_count': 1,
        }
    )
    service.get_bot_config = AsyncMock(
        return_value={'enabled': True, 'handoff_keywords': [], 'fallback_unresolved_count': 2}
    )
    service.list_materials = AsyncMock(return_value=[])
    service._update_session_state = AsyncMock()

    bot_entity = SimpleNamespace(
        adapter='wecomprivate',
        uuid='bot-1',
        name='私域客服机器人',
        use_pipeline_uuid='pipeline-1',
        use_pipeline_name='默认流程',
    )
    event = SimpleNamespace(
        message_chain=_FakeMessageChain('这个问题还是没解决'),
        source_platform_object=SimpleNamespace(
            follow_user_id='zhangsan',
            welcome_code=None,
        ),
        sender=SimpleNamespace(id='wo123', nickname='客户A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'cfg-1',
        'external_user_id': 'wo123',
        'last_message_id': 'msg-3',
    }
    adapter.get_launcher_id.return_value = 'cfg-1:wo123'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipeline-1',
    )

    assert decision.action == 'send_material_and_skip'
    assert decision.reason == 'fallback_route'
    assert decision.material['reply_text'] == '已为你转人工，请稍候。'
    service._update_session_state.assert_awaited_once_with(
        'person_cfg-1:wo123',
        unresolved_count=2,
        mode='manual',
        queue_status='pending_manual',
        handoff_reason='fallback_unresolved',
    )
    ap.wecom_private_service.record_routing_decision.assert_awaited_once_with(
        session_id='person_cfg-1:wo123',
        trigger_type='fallback',
        trigger_reason='unresolved_threshold',
        decision='pending_manual',
        matched_rule=None,
        confidence=1.0,
    )


@pytest.mark.asyncio
async def test_handle_incoming_message_does_not_fallback_on_normal_message_when_unresolved_count_is_near_threshold():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.monitoring_service.record_message = AsyncMock()
    ap.monitoring_service.update_session_activity = AsyncMock(return_value=True)
    ap.wecom_private_service.bootstrap_private_lead = AsyncMock(return_value={'id': 'lead-1'})
    ap.wecom_private_service.get_reception_config = AsyncMock(
        return_value={
            'reception_enabled': True,
            'welcome_enabled': True,
            'binding_required_fields': ['uid', 'server'],
            'binding_trigger_keywords': ['绑定'],
            'binding_prompt_text': '请补充 UID / 区服',
            'fallback_reply_text': '已为你转人工，请稍候。',
        }
    )
    ap.wecom_private_service.get_session_overlay = AsyncMock(
        return_value={'binding_task': None}
    )
    ap.wecom_private_service.record_routing_decision = AsyncMock()

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_cfg-1:wo123',
            'mode': 'ai_hosted',
            'queue_status': 'ai',
            'manual_claimed_at': None,
            'silent_since': None,
            'unresolved_count': 1,
        }
    )
    service.get_bot_config = AsyncMock(
        return_value={'enabled': True, 'handoff_keywords': [], 'fallback_unresolved_count': 2}
    )
    service.list_materials = AsyncMock(return_value=[])
    service._update_session_state = AsyncMock()

    bot_entity = SimpleNamespace(
        adapter='wecomprivate',
        uuid='bot-1',
        name='私域客服机器人',
        use_pipeline_uuid='pipeline-1',
        use_pipeline_name='默认流程',
    )
    event = SimpleNamespace(
        message_chain=_FakeMessageChain('我想问一下充值活动什么时候开始'),
        source_platform_object=SimpleNamespace(
            follow_user_id='zhangsan',
            welcome_code=None,
        ),
        sender=SimpleNamespace(id='wo123', nickname='客户A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'cfg-1',
        'external_user_id': 'wo123',
        'last_message_id': 'msg-4',
    }
    adapter.get_launcher_id.return_value = 'cfg-1:wo123'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipeline-1',
    )

    assert decision.action == 'continue_ai'
    service._update_session_state.assert_not_awaited()
    ap.wecom_private_service.record_routing_decision.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_incoming_message_records_user_message_when_material_reply_matches():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.monitoring_service.record_message = AsyncMock()
    ap.monitoring_service.update_session_activity = AsyncMock(return_value=True)

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={
            'session_id': 'person_escort-account:external-customer-3',
            'mode': 'ai_hosted',
            'queue_status': 'ai',
            'manual_claimed_at': None,
            'silent_since': None,
        }
    )
    service.get_bot_config = AsyncMock(return_value={'enabled': True})
    service.list_materials = AsyncMock(
        return_value=[
            {
                'title': '下载链接',
                'priority': 1,
                'trigger_keywords': ['下载'],
                'reply_text': '点击这里下载',
                'enabled': True,
            }
        ]
    )

    bot_entity = SimpleNamespace(
        adapter='wecomweb',
        uuid='bot-1',
        name='客服机器人',
        use_pipeline_uuid='pipeline-1',
        use_pipeline_name='默认流程',
    )
    event = SimpleNamespace(
        message_chain=_FakeMessageChain('我要下载地址'),
        source_platform_object=SimpleNamespace(),
        sender=SimpleNamespace(id='customer-3', nickname='客户C'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'escort-account',
        'external_user_id': 'external-customer-3',
        'last_message_id': 'msg-3',
    }
    adapter.get_launcher_id.return_value = 'escort-account:external-customer-3'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipeline-1',
    )

    assert decision.action == 'send_material'
    assert decision.reason == 'material'
    assert decision.material['reply_text'] == '点击这里下载'
    ap.monitoring_service.record_message.assert_awaited_once()

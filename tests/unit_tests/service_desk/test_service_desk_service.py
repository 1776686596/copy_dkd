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

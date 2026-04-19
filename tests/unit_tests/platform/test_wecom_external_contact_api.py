from unittest.mock import AsyncMock, call

import pytest


@pytest.mark.asyncio
async def test_create_contact_way_uses_fixed_qr_payload():
    from langbot.libs.wecom_external_contact_api.api import WecomExternalContactClient

    access_token_getter = AsyncMock(return_value='token-1')
    request_json = AsyncMock(
        return_value={
            'errcode': 0,
            'errmsg': 'ok',
            'config_id': 'cfg-1',
            'qr_code': 'https://qrcode.example/cfg-1',
        }
    )

    client = WecomExternalContactClient(
        access_token_getter=access_token_getter,
        request_json=request_json,
    )

    result = await client.create_contact_way(
        follow_user_id='zhangsan',
        state='dkd_phase1_entry',
        remark='DKD 私域固定二维码',
    )

    assert result['config_id'] == 'cfg-1'
    request_json.assert_awaited_once_with(
        'https://qyapi.weixin.qq.com/cgi-bin/externalcontact/add_contact_way',
        method='POST',
        params={'access_token': 'token-1'},
        json={
            'type': 1,
            'scene': 2,
            'style': 1,
            'remark': 'DKD 私域固定二维码',
            'skip_verify': True,
            'state': 'dkd_phase1_entry',
            'user': ['zhangsan'],
        },
    )


@pytest.mark.asyncio
async def test_mark_tags_and_update_remark_use_follow_user_scope():
    from langbot.libs.wecom_external_contact_api.api import WecomExternalContactClient

    access_token_getter = AsyncMock(return_value='token-2')
    request_json = AsyncMock(return_value={'errcode': 0, 'errmsg': 'ok'})

    client = WecomExternalContactClient(
        access_token_getter=access_token_getter,
        request_json=request_json,
    )

    await client.mark_tags(
        follow_user_id='zhangsan',
        external_user_id='wo123',
        add_tags=['tag-a'],
        remove_tags=['tag-b'],
    )
    await client.update_remark(
        follow_user_id='zhangsan',
        external_user_id='wo123',
        remark='玩家 UID: 10001 / 区服: S1',
    )

    assert request_json.await_args_list[0].args[0].endswith('/externalcontact/mark_tag')
    assert request_json.await_args_list[0].kwargs['method'] == 'POST'
    assert request_json.await_args_list[0].kwargs['json'] == {
        'userid': 'zhangsan',
        'external_userid': 'wo123',
        'add_tag': ['tag-a'],
        'remove_tag': ['tag-b'],
    }
    assert request_json.await_args_list[1].args[0].endswith('/externalcontact/get')
    assert request_json.await_args_list[1].kwargs['method'] == 'POST'
    assert request_json.await_args_list[1].kwargs['json'] == {
        'userid': 'zhangsan',
        'external_userid': 'wo123',
        'remark': '玩家 UID: 10001 / 区服: S1',
    }


@pytest.mark.asyncio
async def test_get_list_welcome_and_detail_use_official_paths():
    from langbot.libs.wecom_external_contact_api.api import WecomExternalContactClient

    access_token_getter = AsyncMock(
        side_effect=['token-3', 'token-4', 'token-5', 'token-6']
    )
    request_json = AsyncMock(
        side_effect=[
            {'errcode': 0, 'errmsg': 'ok', 'contact_way': {'config_id': 'cfg-2'}},
            {'errcode': 0, 'errmsg': 'ok', 'contact_way': [], 'next_cursor': 'next-1'},
            {'errcode': 0, 'errmsg': 'ok'},
            {'errcode': 0, 'errmsg': 'ok', 'external_contact': {'external_userid': 'wo123'}},
        ]
    )

    client = WecomExternalContactClient(
        access_token_getter=access_token_getter,
        request_json=request_json,
    )

    detail = await client.get_contact_way(config_id='cfg-2')
    listing = await client.list_contact_ways(limit=50, cursor='cursor-1')
    welcome = await client.send_welcome_message(welcome_code='wcode-1', text='欢迎加入')
    contact = await client.get_external_contact(external_user_id='wo123')

    assert detail['contact_way']['config_id'] == 'cfg-2'
    assert listing['next_cursor'] == 'next-1'
    assert welcome['errcode'] == 0
    assert contact['external_contact']['external_userid'] == 'wo123'

    expected_calls = [
        call(
            'https://qyapi.weixin.qq.com/cgi-bin/externalcontact/get_contact_way',
            method='POST',
            params={'access_token': 'token-3'},
            json={'config_id': 'cfg-2'},
        ),
        call(
            'https://qyapi.weixin.qq.com/cgi-bin/externalcontact/list_contact_way',
            method='POST',
            params={'access_token': 'token-4'},
            json={'limit': 50, 'cursor': 'cursor-1'},
        ),
        call(
            'https://qyapi.weixin.qq.com/cgi-bin/externalcontact/send_welcome_msg',
            method='POST',
            params={'access_token': 'token-5'},
            json={'welcome_code': 'wcode-1', 'text': {'content': '欢迎加入'}},
        ),
        call(
            'https://qyapi.weixin.qq.com/cgi-bin/externalcontact/get',
            method='GET',
            params={'access_token': 'token-6', 'external_userid': 'wo123'},
            json=None,
        ),
    ]
    assert request_json.await_args_list == expected_calls

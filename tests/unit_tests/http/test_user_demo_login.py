from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart

from langbot.pkg.api.http.controller.main import HTTPController
from langbot.pkg.api.http.controller.groups.user import UserRouterGroup
from langbot.pkg.api.http.service.user import UserService
from langbot.pkg.entity.persistence.user import User


@pytest.mark.asyncio
async def test_authenticate_with_demo_key_returns_jwt_for_first_user():
    ap = SimpleNamespace(instance_config=SimpleNamespace(data={'system': {'demo_login_key': 'demo-key'}}))
    service = UserService(ap)
    service.get_first_user = AsyncMock(return_value=SimpleNamespace(user='demo@example.com'))
    service.generate_jwt_token = AsyncMock(return_value='jwt-token')

    token = await service.authenticate_with_demo_key('demo-key')

    assert token == 'jwt-token'
    service.generate_jwt_token.assert_awaited_once_with('demo@example.com')


@pytest.mark.asyncio
async def test_get_first_user_builds_deterministic_query_by_earliest_user_id():
    execute_async = AsyncMock(return_value=SimpleNamespace(all=lambda: []))
    ap = SimpleNamespace(persistence_mgr=SimpleNamespace(execute_async=execute_async))
    service = UserService(ap)

    await service.get_first_user()

    query = execute_async.await_args.args[0]

    assert query._limit_clause is not None
    assert query._limit_clause.value == 1

    order_by_clauses = list(query._order_by_clauses)
    assert len(order_by_clauses) == 1
    assert str(order_by_clauses[0].compile(compile_kwargs={'literal_binds': True})) == str(User.id.asc())


@pytest.mark.asyncio
async def test_authenticate_with_demo_key_raises_when_key_is_invalid():
    ap = SimpleNamespace(instance_config=SimpleNamespace(data={'system': {'demo_login_key': 'demo-key'}}))
    service = UserService(ap)
    service.get_first_user = AsyncMock()
    service.generate_jwt_token = AsyncMock()

    with pytest.raises(ValueError, match='Invalid demo login key'):
        await service.authenticate_with_demo_key('wrong-key')

    service.get_first_user.assert_not_awaited()
    service.generate_jwt_token.assert_not_awaited()


@pytest.mark.asyncio
async def test_authenticate_with_demo_key_raises_when_key_not_configured():
    ap = SimpleNamespace(instance_config=SimpleNamespace(data={'system': {}}))
    service = UserService(ap)
    service.get_first_user = AsyncMock()
    service.generate_jwt_token = AsyncMock()

    with pytest.raises(ValueError, match='Demo login key is not configured'):
        await service.authenticate_with_demo_key('demo-key')

    service.get_first_user.assert_not_awaited()
    service.generate_jwt_token.assert_not_awaited()


@pytest.mark.asyncio
async def test_authenticate_with_demo_key_raises_when_key_is_blank_config():
    ap = SimpleNamespace(instance_config=SimpleNamespace(data={'system': {'demo_login_key': '   '}}))
    service = UserService(ap)
    service.get_first_user = AsyncMock()
    service.generate_jwt_token = AsyncMock()

    with pytest.raises(ValueError, match='Demo login key is not configured'):
        await service.authenticate_with_demo_key('   ')

    service.get_first_user.assert_not_awaited()
    service.generate_jwt_token.assert_not_awaited()


@pytest.mark.asyncio
async def test_auth_key_returns_jwt_when_demo_key_matches():
    user_service = SimpleNamespace(
        authenticate_with_demo_key=AsyncMock(return_value='jwt-token'),
        is_initialized=AsyncMock(return_value=True),
        get_first_user=AsyncMock(
            return_value=SimpleNamespace(account_type='space', password='')
        ),
    )
    ap = SimpleNamespace(
        user_service=user_service,
        instance_config=SimpleNamespace(data={'system': {'demo_login_key': 'demo-key'}}),
    )
    quart_app = quart.Quart(__name__)
    router_group = UserRouterGroup(ap, quart_app)
    await router_group.initialize()

    response = await quart_app.test_client().post(
        '/api/v1/user/auth-key',
        json={'key': 'demo-key'},
    )
    payload = await response.get_json()

    assert response.status_code == 200
    assert payload['code'] == 0
    assert payload['data']['token'] == 'jwt-token'
    user_service.authenticate_with_demo_key.assert_awaited_once_with('demo-key')


@pytest.mark.asyncio
async def test_auth_key_fails_when_key_is_empty():
    user_service = SimpleNamespace(
        authenticate_with_demo_key=AsyncMock(),
        is_initialized=AsyncMock(return_value=True),
        get_first_user=AsyncMock(
            return_value=SimpleNamespace(account_type='space', password='')
        ),
    )
    ap = SimpleNamespace(
        user_service=user_service,
        instance_config=SimpleNamespace(data={'system': {'demo_login_key': 'demo-key'}}),
    )
    quart_app = quart.Quart(__name__)
    router_group = UserRouterGroup(ap, quart_app)
    await router_group.initialize()

    response = await quart_app.test_client().post(
        '/api/v1/user/auth-key',
        json={'key': ''},
    )
    payload = await response.get_json()

    assert response.status_code == 200
    assert payload['code'] == 1
    assert payload['msg'] == 'Login key is required'
    user_service.authenticate_with_demo_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_auth_key_fails_when_request_json_is_null():
    user_service = SimpleNamespace(
        authenticate_with_demo_key=AsyncMock(),
        is_initialized=AsyncMock(return_value=True),
        get_first_user=AsyncMock(
            return_value=SimpleNamespace(account_type='space', password='')
        ),
    )
    ap = SimpleNamespace(
        user_service=user_service,
        instance_config=SimpleNamespace(data={'system': {'demo_login_key': 'demo-key'}}),
    )
    quart_app = quart.Quart(__name__)
    router_group = UserRouterGroup(ap, quart_app)
    await router_group.initialize()

    response = await quart_app.test_client().post(
        '/api/v1/user/auth-key',
        data='null',
        headers={'Content-Type': 'application/json'},
    )
    payload = await response.get_json()

    assert response.status_code == 200
    assert payload['code'] == 1
    assert payload['msg'] == 'Login key is required'
    user_service.authenticate_with_demo_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_auth_key_fails_when_demo_key_validation_fails():
    user_service = SimpleNamespace(
        authenticate_with_demo_key=AsyncMock(side_effect=ValueError('Invalid demo login key')),
        is_initialized=AsyncMock(return_value=True),
        get_first_user=AsyncMock(
            return_value=SimpleNamespace(account_type='space', password='')
        ),
    )
    ap = SimpleNamespace(
        user_service=user_service,
        instance_config=SimpleNamespace(data={'system': {'demo_login_key': 'demo-key'}}),
    )
    quart_app = quart.Quart(__name__)
    router_group = UserRouterGroup(ap, quart_app)
    await router_group.initialize()

    response = await quart_app.test_client().post(
        '/api/v1/user/auth-key',
        json={'key': 'wrong-key'},
    )
    payload = await response.get_json()

    assert response.status_code == 200
    assert payload['code'] == 1
    assert payload['msg'] == 'Invalid demo login key'
    user_service.authenticate_with_demo_key.assert_awaited_once_with('wrong-key')


@pytest.mark.asyncio
async def test_account_info_exposes_demo_login_key_enabled():
    user_service = SimpleNamespace(
        is_initialized=AsyncMock(return_value=True),
        get_first_user=AsyncMock(
            return_value=SimpleNamespace(account_type='space', password='')
        ),
    )
    ap = SimpleNamespace(
        user_service=user_service,
        instance_config=SimpleNamespace(data={'system': {'demo_login_key': 'demo-key'}}),
    )
    quart_app = quart.Quart(__name__)
    router_group = UserRouterGroup(ap, quart_app)
    await router_group.initialize()

    response = await quart_app.test_client().get('/api/v1/user/account-info')
    payload = await response.get_json()

    assert response.status_code == 200
    assert payload['data']['initialized'] is True
    assert payload['data']['account_type'] == 'space'
    assert payload['data']['has_password'] is False
    assert payload['data']['demo_login_key_enabled'] is True


@pytest.mark.asyncio
@pytest.mark.parametrize('demo_login_key', ['', '   '])
async def test_account_info_exposes_demo_login_key_disabled_when_not_configured(
    demo_login_key: str,
):
    user_service = SimpleNamespace(
        is_initialized=AsyncMock(return_value=True),
        get_first_user=AsyncMock(
            return_value=SimpleNamespace(account_type='space', password='')
        ),
    )
    ap = SimpleNamespace(
        user_service=user_service,
        instance_config=SimpleNamespace(data={'system': {'demo_login_key': demo_login_key}}),
    )
    quart_app = quart.Quart(__name__)
    router_group = UserRouterGroup(ap, quart_app)
    await router_group.initialize()

    response = await quart_app.test_client().get('/api/v1/user/account-info')
    payload = await response.get_json()

    assert response.status_code == 200
    assert payload['data']['initialized'] is True
    assert payload['data']['account_type'] == 'space'
    assert payload['data']['has_password'] is False
    assert payload['data']['demo_login_key_enabled'] is False

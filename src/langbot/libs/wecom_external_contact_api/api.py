from typing import Any, Awaitable, Callable


class WecomExternalContactClient:
    def __init__(
        self,
        access_token_getter: Callable[[], Awaitable[str]],
        request_json: Callable[..., Awaitable[dict[str, Any]]],
        api_base_url: str = 'https://qyapi.weixin.qq.com/cgi-bin',
    ) -> None:
        self._access_token_getter = access_token_getter
        self._request_json = request_json
        self._api_base_url = api_base_url.rstrip('/')

    async def _request(
        self,
        path: str,
        *,
        method: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        access_token = await self._access_token_getter()
        request_params = {'access_token': access_token}
        if params:
            request_params.update(params)
        return await self._request_json(
            f'{self._api_base_url}{path}',
            method=method,
            params=request_params,
            json=json,
        )

    async def create_contact_way(
        self,
        follow_user_id: str,
        state: str,
        remark: str,
    ) -> dict[str, Any]:
        return await self._request(
            '/externalcontact/add_contact_way',
            method='POST',
            json={
                'type': 1,
                'scene': 2,
                'style': 1,
                'remark': remark,
                'skip_verify': True,
                'state': state,
                'user': [follow_user_id],
            },
        )

    async def get_contact_way(self, config_id: str) -> dict[str, Any]:
        return await self._request(
            '/externalcontact/get_contact_way',
            method='POST',
            json={'config_id': config_id},
        )

    async def list_contact_ways(
        self,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {'limit': limit}
        if cursor is not None:
            payload['cursor'] = cursor
        return await self._request(
            '/externalcontact/list_contact_way',
            method='POST',
            json=payload,
        )

    async def send_welcome_message(
        self,
        welcome_code: str,
        text: str,
    ) -> dict[str, Any]:
        return await self._request(
            '/externalcontact/send_welcome_msg',
            method='POST',
            json={
                'welcome_code': welcome_code,
                'text': {'content': text},
            },
        )

    async def get_external_contact(self, external_user_id: str) -> dict[str, Any]:
        return await self._request(
            '/externalcontact/get',
            method='GET',
            params={'external_userid': external_user_id},
            json=None,
        )

    async def update_remark(
        self,
        follow_user_id: str,
        external_user_id: str,
        remark: str,
    ) -> dict[str, Any]:
        return await self._request(
            '/externalcontact/get',
            method='POST',
            json={
                'userid': follow_user_id,
                'external_userid': external_user_id,
                'remark': remark,
            },
        )

    async def mark_tags(
        self,
        follow_user_id: str,
        external_user_id: str,
        add_tags: list[str],
        remove_tags: list[str],
    ) -> dict[str, Any]:
        return await self._request(
            '/externalcontact/mark_tag',
            method='POST',
            json={
                'userid': follow_user_id,
                'external_userid': external_user_id,
                'add_tag': add_tags,
                'remove_tag': remove_tags,
            },
        )

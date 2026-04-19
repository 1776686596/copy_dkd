import quart

from .. import group


@group.group_class('wecom_private', '/api/v1/wecom-private')
class WecomPrivateRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '/reception-config/<bot_uuid>',
            methods=['GET', 'PUT'],
            auth_type=group.AuthType.USER_TOKEN,
        )
        async def reception_config(bot_uuid: str) -> str:
            if quart.request.method == 'GET':
                config = await self.ap.wecom_private_service.get_reception_config(bot_uuid)
                return self.success(data={'config': config})

            payload = await quart.request.json
            config = await self.ap.wecom_private_service.upsert_reception_config(bot_uuid, payload or {})
            return self.success(data={'config': config})

        @self.route('/contact-configs', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def list_contact_configs() -> str:
            bot_uuid = str(quart.request.args.get('botUuid') or '').strip()
            if not bot_uuid:
                return self.http_status(400, -1, 'botUuid is required')

            items = await self.ap.wecom_private_service.list_contact_configs(bot_uuid=bot_uuid)
            return self.success(data={'items': items})

        @self.route('/contact-configs/sync-primary', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def sync_primary_contact_config() -> str:
            payload = await quart.request.json
            item = await self.ap.wecom_private_service.sync_primary_contact_config(
                bot_uuid=payload['bot_uuid'],
                follow_user_id=payload['follow_user_id'],
                state=payload['state'],
                remark=payload['remark'],
            )
            return self.success(data={'item': item})

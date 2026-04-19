import quart

from .. import group


@group.group_class('service_desk', '/api/v1/service-desk')
class ServiceDeskRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/bot-configs', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def list_bot_configs() -> str:
            return self.success(data={'items': await self.ap.service_desk_service.list_bot_configs()})

        @self.route('/bot-configs/<bot_uuid>', methods=['PUT'], auth_type=group.AuthType.USER_TOKEN)
        async def update_bot_config(bot_uuid: str) -> str:
            payload = await quart.request.json
            await self.ap.service_desk_service.upsert_bot_config(bot_uuid, payload)
            return self.success()

        @self.route('/bots/<bot_uuid>/materials', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN)
        async def materials(bot_uuid: str) -> str:
            if quart.request.method == 'GET':
                items = await self.ap.service_desk_service.list_materials(bot_uuid)
                return self.success(data={'items': items})

            payload = await quart.request.json
            material_id = await self.ap.service_desk_service.create_material(bot_uuid, payload)
            return self.success(data={'uuid': material_id})

        @self.route('/bots/<bot_uuid>/quick-replies', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def quick_replies(bot_uuid: str) -> str:
            items = await self.ap.service_desk_service.list_quick_replies(bot_uuid)
            return self.success(data={'items': items})

        @self.route('/sessions', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def list_sessions() -> str:
            params = quart.request.args
            items, total = await self.ap.service_desk_service.list_workbench_sessions(
                bot_uuid=params.get('botUuid'),
                queue_status=params.get('queueStatus'),
                claimed_by=params.get('claimedBy'),
                keyword=params.get('keyword'),
                limit=int(params.get('limit', 50)),
                offset=int(params.get('offset', 0)),
            )
            return self.success(data={'sessions': items, 'total': total})

        @self.route('/sessions/<session_id>', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def get_session_detail(session_id: str) -> str:
            detail = await self.ap.service_desk_service.get_session_detail(session_id)
            return self.success(data=detail)

        @self.route('/sessions/<session_id>/claim', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def claim_session(session_id: str, user_email: str) -> str:
            user = await self.ap.user_service.get_user_by_email(user_email)
            await self.ap.service_desk_service.claim_session(session_id, str(user.id), user.user)
            return self.success()

        @self.route('/sessions/<session_id>/mode', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def set_session_mode(session_id: str) -> str:
            payload = await quart.request.json
            await self.ap.service_desk_service.set_session_mode(session_id, payload['mode'])
            return self.success()

        @self.route('/sessions/<session_id>/assist-draft', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def generate_assist_draft(session_id: str, user_email: str) -> str:
            user = await self.ap.user_service.get_user_by_email(user_email)
            draft = await self.ap.service_desk_service.generate_assist_draft(
                session_id,
                str(user.id),
            )
            return self.success(data={'draft': draft})

        @self.route('/sessions/<session_id>/release', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def release_session(session_id: str) -> str:
            await self.ap.service_desk_service.release_session(session_id)
            return self.success()

        @self.route('/sessions/<session_id>/return-ai', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def return_session_to_ai(session_id: str) -> str:
            await self.ap.service_desk_service.return_session_to_ai(session_id)
            return self.success()

        @self.route('/sessions/<session_id>/reply', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def reply_session(session_id: str, user_email: str) -> str:
            payload = await quart.request.json
            await self.ap.service_desk_service.reply_to_session(session_id, payload['reply_text'])
            return self.success()

        @self.route('/sessions/<session_id>/binding-task', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def upsert_binding_task(session_id: str, user_email: str) -> str:
            payload = await quart.request.json
            try:
                task = await self.ap.wecom_private_service.upsert_binding_task(
                    session_id=session_id,
                    data=payload or {},
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={'binding_task': task})

        @self.route('/sessions/<session_id>/close', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def close_session(session_id: str, user_email: str) -> str:
            payload = await quart.request.json
            user = await self.ap.user_service.get_user_by_email(user_email)
            try:
                record = await self.ap.wecom_private_service.close_private_session(
                    session_id=session_id,
                    operator_name=getattr(user, 'user', user_email),
                    data=payload or {},
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={'closure_record': record})

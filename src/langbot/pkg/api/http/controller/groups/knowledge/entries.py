import quart

from ... import group


@group.group_class('knowledge_entries', '/api/v1/knowledge/bases/<knowledge_base_uuid>/entries')
class KnowledgeEntriesRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def handle_local_faq_entries(knowledge_base_uuid: str) -> quart.Response:
            if quart.request.method == 'GET':
                entries = await self.ap.knowledge_service.get_local_faq_entries(knowledge_base_uuid)
                return self.success(data={'entries': entries})

            json_data = await quart.request.json
            entry = await self.ap.knowledge_service.create_local_faq_entry(knowledge_base_uuid, json_data or {})
            return self.success(data={'entry': entry})

        @self.route('/<entry_uuid>', methods=['PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def handle_specific_local_faq_entry(knowledge_base_uuid: str, entry_uuid: str) -> quart.Response:
            if quart.request.method == 'PUT':
                json_data = await quart.request.json
                entry = await self.ap.knowledge_service.update_local_faq_entry(
                    knowledge_base_uuid, entry_uuid, json_data or {}
                )
                return self.success(data={'entry': entry})

            await self.ap.knowledge_service.delete_local_faq_entry(knowledge_base_uuid, entry_uuid)
            return self.success({})

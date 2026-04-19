from __future__ import annotations

import datetime
import uuid
from typing import Any

import httpx
import sqlalchemy

from ....core import app
from ....entity.persistence import bot as persistence_bot
from ....entity.persistence import service_desk as persistence_service_desk
from langbot.libs.wecom_external_contact_api import WecomExternalContactClient


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class WecomPrivateService:
    """WeCom private domain service"""

    ap: app.Application
    _DEFAULT_BINDING_REQUIRED_FIELDS = ['uid', 'server']

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        self._access_token_cache: dict[str, str] = {}

    @staticmethod
    def _get_value(value: Any, key: str, default=None):
        if value is None:
            return default
        if isinstance(value, dict):
            return value.get(key, default)
        return getattr(value, key, default)

    def _serialize(self, model, row):
        if row is None:
            return None
        return self.ap.persistence_mgr.serialize_model(model, row)

    async def list_contact_configs(self, *, bot_uuid: str) -> list[dict[str, Any]]:
        if not bot_uuid:
            raise ValueError('bot_uuid is required')

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateContactConfig)
            .where(persistence_service_desk.WecomPrivateContactConfig.bot_uuid == bot_uuid)
            .order_by(
                persistence_service_desk.WecomPrivateContactConfig.is_primary.desc(),
                persistence_service_desk.WecomPrivateContactConfig.updated_at.desc(),
                persistence_service_desk.WecomPrivateContactConfig.created_at.desc(),
            )
        )
        return [
            item
            for item in (
                self._serialize(persistence_service_desk.WecomPrivateContactConfig, row)
                for row in result.all()
            )
            if item is not None
        ]

    async def sync_primary_contact_config(
        self,
        *,
        bot_uuid: str,
        follow_user_id: str,
        state: str,
        remark: str,
    ) -> dict[str, Any]:
        client = await self._build_external_contact_client(bot_uuid)
        stored = await self._get_primary_contact_config(bot_uuid)
        if stored is None:
            remote = await client.create_contact_way(
                follow_user_id=follow_user_id,
                state=state,
                remark=remark,
            )
            payload = {
                'id': str(uuid.uuid4()),
                'bot_uuid': bot_uuid,
                'config_id': remote['config_id'],
                'qr_code_url': remote['qr_code'],
                'remark': remark,
                'state': state,
                'follow_user_ids': [follow_user_id],
                'enabled': True,
                'is_primary': True,
            }
        else:
            config_id = self._get_value(stored, 'config_id')
            await client.update_contact_way(
                config_id=config_id,
                follow_user_id=follow_user_id,
                state=state,
                remark=remark,
            )
            remote = await client.get_contact_way(config_id=config_id)
            contact_way = remote.get('contact_way', {})
            payload = {
                'id': self._get_value(stored, 'id'),
                'bot_uuid': self._get_value(stored, 'bot_uuid', bot_uuid),
                'config_id': contact_way.get('config_id', self._get_value(stored, 'config_id')),
                'qr_code_url': contact_way.get('qr_code', self._get_value(stored, 'qr_code_url')),
                'remark': remark,
                'state': contact_way.get('state', state),
                'follow_user_ids': contact_way.get('user', [follow_user_id]),
                'enabled': True,
                'is_primary': True,
            }

        await self._upsert_contact_config(payload)
        return payload

    async def bootstrap_private_lead(
        self,
        *,
        bot_uuid: str,
        external_user_id: str,
        follow_user_id: str,
        source_entry_id: str,
    ) -> dict[str, Any]:
        existing = await self._get_lead_by_external_userid(external_user_id)
        if existing is not None:
            return existing

        client = await self._build_external_contact_client(bot_uuid)
        remote = await client.get_external_contact(external_user_id=external_user_id)
        payload = {
            'id': str(uuid.uuid4()),
            'bot_uuid': bot_uuid,
            'external_userid': external_user_id,
            'follow_user_id': follow_user_id,
            'source_state': self._extract_source_state(remote, follow_user_id, source_entry_id),
            'first_add_time': self._extract_first_add_time(remote, follow_user_id),
            'current_tags': self._extract_current_tags(remote, follow_user_id),
            'profile_status': 'anonymous',
            'bound_game_identity': {},
            'remark_snapshot': self._extract_remark_snapshot(remote, follow_user_id),
        }
        return await self._insert_lead(payload)

    async def send_welcome_message(
        self,
        *,
        bot_uuid: str,
        welcome_code: str,
        text: str,
    ) -> dict[str, Any]:
        normalized_welcome_code = str(welcome_code or '').strip()
        normalized_text = str(text or '').strip()
        if not normalized_welcome_code or not normalized_text:
            return {}

        client = await self._build_external_contact_client(bot_uuid)
        return await client.send_welcome_message(
            welcome_code=normalized_welcome_code,
            text=normalized_text,
        )

    def _default_reception_config(self, bot_uuid: str) -> dict[str, Any]:
        return {
            'bot_uuid': bot_uuid,
            'reception_enabled': True,
            'welcome_enabled': True,
            'fallback_reply_text': '',
            'binding_required_fields': list(self._DEFAULT_BINDING_REQUIRED_FIELDS),
            'binding_trigger_keywords': [],
            'binding_prompt_text': '',
            'human_handoff_direct_enabled': True,
        }

    async def get_reception_config(self, bot_uuid: str) -> dict[str, Any]:
        if not bot_uuid:
            raise ValueError('bot_uuid is required')

        row = await self._get_reception_config(bot_uuid)
        if row is None:
            return self._default_reception_config(bot_uuid)

        config = self._default_reception_config(bot_uuid)
        config.update(row)
        config['fallback_reply_text'] = self._normalize_text(config.get('fallback_reply_text'))
        config['binding_prompt_text'] = self._normalize_text(config.get('binding_prompt_text'))
        config['binding_required_fields'] = self._normalize_binding_required_fields(
            config.get('binding_required_fields')
        )
        config['binding_trigger_keywords'] = self._normalize_binding_trigger_keywords(
            config.get('binding_trigger_keywords')
        )
        return config

    async def upsert_reception_config(self, bot_uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        if not bot_uuid:
            raise ValueError('bot_uuid is required')

        payload = self._default_reception_config(bot_uuid)
        existing = await self._get_reception_config(bot_uuid)
        if existing is not None:
            payload.update(existing)

        if 'reception_enabled' in data:
            payload['reception_enabled'] = self._normalize_bool(
                self._get_value(data, 'reception_enabled'),
                default=payload['reception_enabled'],
            )
        if 'welcome_enabled' in data:
            payload['welcome_enabled'] = self._normalize_bool(
                self._get_value(data, 'welcome_enabled'),
                default=payload['welcome_enabled'],
            )
        if 'fallback_reply_text' in data:
            payload['fallback_reply_text'] = self._normalize_text(
                self._get_value(data, 'fallback_reply_text')
            )
        if 'binding_required_fields' in data:
            payload['binding_required_fields'] = self._normalize_binding_required_fields(
                self._get_value(data, 'binding_required_fields')
            )
        if 'binding_trigger_keywords' in data:
            payload['binding_trigger_keywords'] = self._normalize_binding_trigger_keywords(
                self._get_value(data, 'binding_trigger_keywords')
            )
        if 'binding_prompt_text' in data:
            payload['binding_prompt_text'] = self._normalize_text(
                self._get_value(data, 'binding_prompt_text')
            )
        if 'human_handoff_direct_enabled' in data:
            payload['human_handoff_direct_enabled'] = self._normalize_bool(
                self._get_value(data, 'human_handoff_direct_enabled'),
                default=payload['human_handoff_direct_enabled'],
            )

        return await self._upsert_reception_config_row(payload)

    async def record_routing_decision(
        self,
        *,
        session_id: str,
        trigger_type: str,
        trigger_reason: str,
        decision: str,
        matched_rule: str | None,
        confidence: float,
    ) -> dict[str, Any]:
        payload = {
            'id': str(uuid.uuid4()),
            'session_id': session_id,
            'trigger_type': trigger_type,
            'trigger_reason': trigger_reason,
            'decision': decision,
            'matched_rule': matched_rule,
            'confidence': confidence,
        }
        return await self._insert_routing_decision(payload)

    async def upsert_binding_task(self, *, session_id: str, data: dict[str, Any]) -> dict[str, Any]:
        await self._assert_wecom_private_session(session_id)
        existing = await self._get_binding_task(session_id)
        payload = dict(existing or {})
        payload['id'] = self._get_value(existing, 'id') or data.get('id') or str(uuid.uuid4())
        payload['session_id'] = session_id

        if existing is None:
            payload.setdefault('requested_fields', ['uid', 'server'])
            payload.setdefault('verify_status', 'pending')
            payload.setdefault('completed_at', None)

        if 'requested_fields' in data:
            payload['requested_fields'] = data.get('requested_fields', ['uid', 'server'])
        if 'provided_uid' in data:
            payload['provided_uid'] = data.get('provided_uid')
        if 'provided_server' in data:
            payload['provided_server'] = data.get('provided_server')
        if 'provided_role_name' in data:
            payload['provided_role_name'] = data.get('provided_role_name')
        if 'verify_status' in data:
            verify_status = str(data.get('verify_status') or 'pending')
            payload['verify_status'] = verify_status
            if verify_status == 'completed':
                payload['completed_at'] = self._get_value(existing, 'completed_at') or _utcnow()
            else:
                payload['completed_at'] = None

        return await self._upsert_binding_task_row(payload)

    async def close_private_session(
        self,
        *,
        session_id: str,
        operator_name: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        await self._assert_wecom_private_session(session_id)
        session = await self._get_session(session_id)
        if session is None:
            raise ValueError('service desk session not found')

        lead_id = self._get_value(session, 'lead_id')
        lead = await self._get_lead(lead_id)
        if lead is None:
            raise ValueError('wecom private lead not found')

        client = await self._build_external_contact_client(self._get_value(session, 'bot_uuid'))
        tag_updates = data.get('tag_updates', {})
        await client.mark_tags(
            follow_user_id=self._get_value(lead, 'follow_user_id'),
            external_user_id=self._get_value(lead, 'external_userid'),
            add_tags=list(tag_updates.get('add', [])),
            remove_tags=list(tag_updates.get('remove', [])),
        )

        remark_text = str(data.get('remark_text') or '').strip()
        if remark_text:
            await client.update_remark(
                follow_user_id=self._get_value(lead, 'follow_user_id'),
                external_user_id=self._get_value(lead, 'external_userid'),
                remark=remark_text,
            )

        payload = {
            'id': str(uuid.uuid4()),
            'session_id': session_id,
            'resolution_type': data['resolution_type'],
            'tag_updates': tag_updates,
            'followup_needed': bool(data.get('followup_needed', False)),
            'knowledge_feedback': data.get('knowledge_feedback'),
            'closed_by': operator_name,
        }
        record = await self._upsert_closure_record(payload)
        await self._mark_session_closed(session_id)
        return record

    async def get_session_overlay(self, session_id: str) -> dict[str, Any]:
        overlay = {
            'lead': None,
            'routing_decisions': [],
            'binding_task': None,
            'closure_record': None,
        }
        if not session_id:
            return overlay

        session = await self._get_session(session_id)
        if session is None:
            return overlay

        lead = await self._get_lead(self._get_value(session, 'lead_id'))
        return {
            'lead': lead,
            'routing_decisions': await self._list_routing_decisions(session_id),
            'binding_task': await self._get_binding_task(session_id),
            'closure_record': await self._get_closure_record(session_id),
        }

    async def _get_bot(self, bot_uuid: str):
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_bot.Bot).where(persistence_bot.Bot.uuid == bot_uuid)
        )
        return result.first()

    async def _get_access_token(self, bot_uuid: str) -> str:
        cached = self._access_token_cache.get(bot_uuid)
        if cached:
            return cached

        bot = await self._get_bot(bot_uuid)
        if bot is None:
            raise ValueError(f'bot not found: {bot_uuid}')

        config = self._get_value(bot, 'adapter_config', {}) or {}
        corpid = config.get('corpid') or config.get('CorpID')
        corpsecret = config.get('contacts_secret') or config.get('secret') or config.get('corpsecret')
        if not corpid or not corpsecret:
            raise ValueError('wecom private adapter config missing corpid or contact secret')

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                'https://qyapi.weixin.qq.com/cgi-bin/gettoken',
                params={'corpid': corpid, 'corpsecret': corpsecret},
            )
            response.raise_for_status()
            payload = response.json()

        token = str(payload.get('access_token') or '')
        if not token:
            raise RuntimeError(f'failed to fetch wecom access token: {payload}')

        self._access_token_cache[bot_uuid] = token
        return token

    async def _build_external_contact_client(self, bot_uuid: str) -> WecomExternalContactClient:
        async def access_token_getter() -> str:
            return await self._get_access_token(bot_uuid)

        async def request_json(
            url: str,
            *,
            method: str,
            params: dict[str, Any] | None = None,
            json: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.request(method, url, params=params, json=json)
                response.raise_for_status()
                return response.json()

        return WecomExternalContactClient(
            access_token_getter=access_token_getter,
            request_json=request_json,
        )

    async def _get_primary_contact_config(self, bot_uuid: str):
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateContactConfig)
            .where(persistence_service_desk.WecomPrivateContactConfig.bot_uuid == bot_uuid)
            .where(persistence_service_desk.WecomPrivateContactConfig.is_primary == sqlalchemy.true())
        )
        return result.first()

    async def _upsert_contact_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        existing = await self._get_primary_contact_config(payload['bot_uuid'])
        if existing is None:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.insert(persistence_service_desk.WecomPrivateContactConfig).values(payload)
            )
            row_id = payload['id']
        else:
            row_id = self._get_value(existing, 'id')
            update_payload = dict(payload)
            update_payload['updated_at'] = sqlalchemy.func.now()
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_service_desk.WecomPrivateContactConfig)
                .where(persistence_service_desk.WecomPrivateContactConfig.id == row_id)
                .values(update_payload)
            )

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateContactConfig)
            .where(persistence_service_desk.WecomPrivateContactConfig.id == row_id)
        )
        return self._serialize(persistence_service_desk.WecomPrivateContactConfig, result.first())

    async def _get_reception_config(self, bot_uuid: str):
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateReceptionConfig).where(
                persistence_service_desk.WecomPrivateReceptionConfig.bot_uuid == bot_uuid
            )
        )
        return self._serialize(
            persistence_service_desk.WecomPrivateReceptionConfig,
            result.first(),
        )

    async def _upsert_reception_config_row(self, payload: dict[str, Any]) -> dict[str, Any]:
        existing = await self._get_reception_config(payload['bot_uuid'])
        if existing is None:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.insert(persistence_service_desk.WecomPrivateReceptionConfig).values(payload)
            )
        else:
            update_payload = dict(payload)
            update_payload['updated_at'] = sqlalchemy.func.now()
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_service_desk.WecomPrivateReceptionConfig)
                .where(
                    persistence_service_desk.WecomPrivateReceptionConfig.bot_uuid == payload['bot_uuid']
                )
                .values(update_payload)
            )

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateReceptionConfig).where(
                persistence_service_desk.WecomPrivateReceptionConfig.bot_uuid == payload['bot_uuid']
            )
        )
        return self._serialize(
            persistence_service_desk.WecomPrivateReceptionConfig,
            result.first(),
        )

    async def _get_lead_by_external_userid(self, external_user_id: str):
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateLead).where(
                persistence_service_desk.WecomPrivateLead.external_userid == external_user_id
            )
        )
        lead = result.first()
        if lead is None:
            return None
        return self._serialize(persistence_service_desk.WecomPrivateLead, lead)

    async def _insert_lead(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_service_desk.WecomPrivateLead).values(payload)
        )
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateLead).where(
                persistence_service_desk.WecomPrivateLead.id == payload['id']
            )
        )
        return self._serialize(persistence_service_desk.WecomPrivateLead, result.first())

    async def _insert_routing_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_service_desk.WecomPrivateRoutingDecision).values(payload)
        )
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateRoutingDecision).where(
                persistence_service_desk.WecomPrivateRoutingDecision.id == payload['id']
            )
        )
        return self._serialize(persistence_service_desk.WecomPrivateRoutingDecision, result.first())

    async def _upsert_binding_task_row(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateBindingTask).where(
                persistence_service_desk.WecomPrivateBindingTask.session_id == payload['session_id']
            )
        )
        existing = result.first()
        if existing is None:
            insert_payload = dict(payload)
            insert_payload.setdefault('requested_at', _utcnow())
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.insert(persistence_service_desk.WecomPrivateBindingTask).values(insert_payload)
            )
            row_id = payload['id']
        else:
            row_id = self._get_value(existing, 'id')
            update_payload = dict(payload)
            update_payload.pop('id', None)
            update_payload['updated_at'] = sqlalchemy.func.now()
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_service_desk.WecomPrivateBindingTask)
                .where(persistence_service_desk.WecomPrivateBindingTask.id == row_id)
                .values(update_payload)
            )

        row = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateBindingTask).where(
                persistence_service_desk.WecomPrivateBindingTask.id == row_id
            )
        )
        return self._serialize(persistence_service_desk.WecomPrivateBindingTask, row.first())

    async def _get_session(self, session_id: str):
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.ServiceDeskSession).where(
                persistence_service_desk.ServiceDeskSession.session_id == session_id
            )
        )
        row = result.first()
        if row is None:
            return None
        return self._serialize(persistence_service_desk.ServiceDeskSession, row)

    async def _get_bot_adapter(self, bot_uuid: str | None) -> str | None:
        if not bot_uuid:
            return None
        platform_mgr = getattr(self.ap, 'platform_mgr', None)
        if platform_mgr is None or not hasattr(platform_mgr, 'get_bot_by_uuid'):
            return None
        get_bot_by_uuid = getattr(platform_mgr, 'get_bot_by_uuid', None)
        if get_bot_by_uuid is None or not callable(get_bot_by_uuid):
            return None
        runtime_bot = get_bot_by_uuid(bot_uuid)
        if hasattr(runtime_bot, '__await__'):
            runtime_bot = await runtime_bot
        if runtime_bot is None:
            return None
        adapter_name = getattr(getattr(runtime_bot, 'bot_entity', None), 'adapter', None)
        if not isinstance(adapter_name, str) or not adapter_name.strip():
            return None
        return adapter_name.strip()

    async def _assert_wecom_private_session(self, session_id: str) -> dict[str, Any]:
        session = await self._get_session(session_id)
        if session is None:
            raise ValueError('service desk session not found')

        adapter_name = await self._get_bot_adapter(self._get_value(session, 'bot_uuid'))
        if adapter_name is not None and adapter_name != 'wecomprivate':
            raise ValueError('only wecomprivate sessions support private-domain actions')

        return session

    async def _get_lead(self, lead_id: str | None):
        if not lead_id:
            return None
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateLead).where(
                persistence_service_desk.WecomPrivateLead.id == lead_id
            )
        )
        row = result.first()
        if row is None:
            return None
        return self._serialize(persistence_service_desk.WecomPrivateLead, row)

    async def _list_routing_decisions(self, session_id: str) -> list[dict[str, Any]]:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateRoutingDecision)
            .where(persistence_service_desk.WecomPrivateRoutingDecision.session_id == session_id)
            .order_by(
                persistence_service_desk.WecomPrivateRoutingDecision.created_at.asc(),
                persistence_service_desk.WecomPrivateRoutingDecision.id.asc(),
            )
        )
        return [
            item
            for item in (
                self._serialize(persistence_service_desk.WecomPrivateRoutingDecision, row)
                for row in result.all()
            )
            if item is not None
        ]

    async def _get_binding_task(self, session_id: str):
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateBindingTask).where(
                persistence_service_desk.WecomPrivateBindingTask.session_id == session_id
            )
        )
        return self._serialize(
            persistence_service_desk.WecomPrivateBindingTask,
            result.first(),
        )

    async def _upsert_closure_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateClosureRecord).where(
                persistence_service_desk.WecomPrivateClosureRecord.session_id == payload['session_id']
            )
        )
        existing = result.first()
        if existing is None:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.insert(persistence_service_desk.WecomPrivateClosureRecord).values(payload)
            )
            row_id = payload['id']
        else:
            row_id = self._get_value(existing, 'id')
            update_payload = dict(payload)
            update_payload.pop('id', None)
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_service_desk.WecomPrivateClosureRecord)
                .where(persistence_service_desk.WecomPrivateClosureRecord.id == row_id)
                .values(update_payload)
            )

        row = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateClosureRecord).where(
                persistence_service_desk.WecomPrivateClosureRecord.id == row_id
            )
        )
        return self._serialize(persistence_service_desk.WecomPrivateClosureRecord, row.first())

    async def _get_closure_record(self, session_id: str):
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.WecomPrivateClosureRecord).where(
                persistence_service_desk.WecomPrivateClosureRecord.session_id == session_id
            )
        )
        return self._serialize(
            persistence_service_desk.WecomPrivateClosureRecord,
            result.first(),
        )

    async def _mark_session_closed(self, session_id: str) -> None:
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_service_desk.ServiceDeskSession)
            .where(persistence_service_desk.ServiceDeskSession.session_id == session_id)
            .values(
                closed_at=_utcnow(),
                queue_status='closed',
                updated_at=sqlalchemy.func.now(),
            )
        )

    @staticmethod
    def _get_follow_user_record(remote: dict[str, Any], follow_user_id: str) -> dict[str, Any]:
        follow_users = remote.get('follow_user', [])
        for item in follow_users:
            if item.get('userid') == follow_user_id:
                return item
        return follow_users[0] if follow_users else {}

    @classmethod
    def _extract_source_state(cls, remote: dict[str, Any], follow_user_id: str, fallback: str) -> str:
        follow_user = cls._get_follow_user_record(remote, follow_user_id)
        return str(follow_user.get('state') or fallback)

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or '').strip()

    @classmethod
    def _normalize_binding_required_fields(cls, value: Any) -> list[str]:
        items = cls._normalize_string_list(value)
        return items or list(cls._DEFAULT_BINDING_REQUIRED_FIELDS)

    @classmethod
    def _normalize_binding_trigger_keywords(cls, value: Any) -> list[str]:
        return cls._normalize_string_list(value)

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            source = [value]
        elif isinstance(value, (list, tuple, set)):
            source = list(value)
        else:
            source = [value]

        normalized: list[str] = []
        for item in source:
            text = str(item or '').strip()
            if text:
                normalized.append(text)
        return normalized

    @staticmethod
    def _normalize_bool(value: Any, *, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {'true', '1', 'yes', 'on'}:
                return True
            if lowered in {'false', '0', 'no', 'off'}:
                return False
        return bool(value)

    @classmethod
    def _extract_first_add_time(
        cls,
        remote: dict[str, Any],
        follow_user_id: str,
    ) -> datetime.datetime | None:
        follow_user = cls._get_follow_user_record(remote, follow_user_id)
        created_at = follow_user.get('createtime')
        if created_at is None:
            return None
        return datetime.datetime.utcfromtimestamp(int(created_at))

    @classmethod
    def _extract_current_tags(cls, remote: dict[str, Any], follow_user_id: str) -> list[str]:
        follow_user = cls._get_follow_user_record(remote, follow_user_id)
        tag_items = follow_user.get('tags', [])
        tags = []
        for item in tag_items:
            if isinstance(item, dict):
                tag_name = item.get('tag_name') or item.get('name') or item.get('tag_id')
                if tag_name:
                    tags.append(str(tag_name))
            elif item:
                tags.append(str(item))
        return tags

    @classmethod
    def _extract_remark_snapshot(cls, remote: dict[str, Any], follow_user_id: str) -> dict[str, Any]:
        follow_user = cls._get_follow_user_record(remote, follow_user_id)
        return {
            'remark': follow_user.get('remark'),
            'description': follow_user.get('description'),
            'remark_company': follow_user.get('remark_company'),
            'remark_mobiles': follow_user.get('remark_mobiles') or [],
        }

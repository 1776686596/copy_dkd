from __future__ import annotations

import datetime
import json
import re
import uuid
from dataclasses import dataclass

import sqlalchemy

from ....core import app
from ....entity.persistence import monitoring as persistence_monitoring
from ....entity.persistence import service_desk as persistence_service_desk


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


@dataclass
class ServiceDeskDecision:
    action: str
    reason: str | None = None
    material: dict | None = None


def match_material(message_text: str, materials: list[dict]) -> dict | None:
    normalized = message_text.strip().lower()
    for material in sorted(materials, key=lambda item: item['priority']):
        if not material.get('enabled', True):
            continue
        keywords = material.get('trigger_keywords', [])
        if any(keyword.lower() in normalized for keyword in keywords):
            return material
    return None


QUICK_REPLY_TYPES = {'quick_reply', 'download_link', 'gift_pack'}


class ServiceDeskService:
    """Service desk service"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    @staticmethod
    def _unwrap_model(row):
        if row is None:
            return None
        if hasattr(row, '_mapping'):
            mapping = row._mapping
            if len(mapping) == 1:
                value = next(iter(mapping.values()))
                if hasattr(value, '__table__') or hasattr(value, '__mapper__'):
                    return value
            return row
        if isinstance(row, tuple):
            if len(row) == 1:
                value = row[0]
                if hasattr(value, '__table__') or hasattr(value, '__mapper__'):
                    return value
            return row
        return row

    @staticmethod
    def _get_value(session, key: str, default=None):
        if session is None:
            return default
        if isinstance(session, dict):
            return session.get(key, default)
        return getattr(session, key, default)

    @staticmethod
    def _get_row_value(row, key: str, default=None):
        if row is None:
            return default
        mapping = getattr(row, '_mapping', None)
        if mapping is not None:
            return mapping.get(key, default)
        return ServiceDeskService._get_value(row, key, default)

    @staticmethod
    def _get_sender_name(event) -> str | None:
        sender = getattr(event, 'sender', None)
        if sender is None:
            return None
        if hasattr(sender, 'nickname'):
            return sender.nickname
        if hasattr(sender, 'member_name'):
            return sender.member_name
        return None

    @staticmethod
    def _get_session_id(event, adapter) -> str:
        if hasattr(adapter, 'get_launcher_id'):
            launcher_id = adapter.get_launcher_id(event)
            if launcher_id:
                return f'person_{launcher_id}'

        sender = getattr(event, 'sender', None)
        sender_id = getattr(sender, 'id', None)
        return f'person_{sender_id}'

    @staticmethod
    def _should_mark_silent(
        session,
        timeout_seconds: int,
        now: datetime.datetime | None = None,
    ) -> bool:
        if ServiceDeskService._get_value(session, 'queue_status') != 'manual':
            return False

        if ServiceDeskService._get_value(session, 'silent_since') is not None:
            return False

        activity_anchor = ServiceDeskService._get_value(
            session,
            'last_manual_reply_at',
        ) or ServiceDeskService._get_value(
            session,
            'manual_claimed_at',
        )
        if activity_anchor is None:
            return False

        now = now or datetime.datetime.utcnow()
        return (now - activity_anchor).total_seconds() > timeout_seconds

    @staticmethod
    def _reopen_mode_after_customer_message(
        queue_status: str | None,
    ) -> tuple[str, str] | None:
        if queue_status == 'silent':
            return ('ai_hosted', 'ai')
        return None

    @staticmethod
    def _contains_keyword(message_text: str, keywords: list[str]) -> bool:
        normalized = message_text.strip().lower()
        return any(keyword.strip().lower() in normalized for keyword in keywords)

    @staticmethod
    def _build_reply_context(source) -> dict[str, str]:
        return {
            'source_entry_id': str(ServiceDeskService._get_value(source, 'source_entry_id', '') or ''),
            'external_user_id': str(ServiceDeskService._get_value(source, 'external_user_id', '') or ''),
            'last_message_id': str(ServiceDeskService._get_value(source, 'last_message_id', '') or ''),
        }

    @staticmethod
    def _compact_preview_text(value: str, limit: int = 120) -> str:
        normalized = re.sub(r'\s+', ' ', value).strip()
        if len(normalized) <= limit:
            return normalized
        return f'{normalized[: limit - 3].rstrip()}...'

    @classmethod
    def _extract_preview_component_text(cls, component: dict) -> str:
        component_type = str(component.get('type') or '')

        if component_type == 'Plain':
            return str(component.get('text') or '')
        if component_type == 'At':
            display = component.get('display') or component.get('target') or ''
            return f'@{display}' if display else '@'
        if component_type == 'AtAll':
            return '@全体成员'
        if component_type == 'Image':
            return '[图片]'
        if component_type == 'Voice':
            length = component.get('length')
            return f'[语音 {length}s]' if length else '[语音]'
        if component_type == 'File':
            name = component.get('name')
            return f'[文件 {name}]' if name else '[文件]'
        if component_type == 'Quote':
            return '[引用]'
        if component_type == 'Forward':
            return '[转发消息]'
        if component_type == 'Source':
            return ''
        if component_type:
            return f'[{component_type}]'
        return ''

    @classmethod
    def _build_message_preview(cls, message_content: str | None) -> str | None:
        if not message_content:
            return None

        preview_text = message_content
        try:
            parsed = json.loads(message_content)
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed = None

        if isinstance(parsed, list):
            parts = []
            for item in parsed:
                if isinstance(item, dict):
                    component_text = cls._extract_preview_component_text(item)
                    if component_text:
                        parts.append(component_text)
            preview_text = ''.join(parts)
        elif isinstance(parsed, dict):
            preview_text = cls._extract_preview_component_text(parsed)
        elif isinstance(parsed, str):
            preview_text = parsed

        compacted = cls._compact_preview_text(str(preview_text))
        return compacted or None

    async def _load_last_message_previews(
        self,
        session_ids: list[str],
    ) -> dict[str, dict]:
        if not session_ids:
            return {}

        latest_timestamp_subquery = (
            sqlalchemy.select(
                persistence_monitoring.MonitoringMessage.session_id.label('session_id'),
                sqlalchemy.func.max(
                    persistence_monitoring.MonitoringMessage.timestamp
                ).label('latest_timestamp'),
            )
            .where(persistence_monitoring.MonitoringMessage.session_id.in_(session_ids))
            .group_by(persistence_monitoring.MonitoringMessage.session_id)
            .subquery()
        )

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(
                persistence_monitoring.MonitoringMessage.session_id,
                persistence_monitoring.MonitoringMessage.message_content,
                persistence_monitoring.MonitoringMessage.role,
                persistence_monitoring.MonitoringMessage.timestamp,
            )
            .join(
                latest_timestamp_subquery,
                sqlalchemy.and_(
                    persistence_monitoring.MonitoringMessage.session_id
                    == latest_timestamp_subquery.c.session_id,
                    persistence_monitoring.MonitoringMessage.timestamp
                    == latest_timestamp_subquery.c.latest_timestamp,
                ),
            )
            .order_by(
                persistence_monitoring.MonitoringMessage.timestamp.desc(),
                persistence_monitoring.MonitoringMessage.id.desc(),
            )
        )

        preview_map: dict[str, dict] = {}
        for row in result.all():
            session_id = str(self._get_row_value(row, 'session_id', '') or '')
            if not session_id or session_id in preview_map:
                continue

            preview_map[session_id] = {
                'last_message_preview': self._build_message_preview(
                    self._get_row_value(row, 'message_content')
                ),
                'last_message_role': self._get_row_value(row, 'role'),
                'last_message_at': (
                    self._get_row_value(row, 'timestamp').isoformat()
                    if hasattr(self._get_row_value(row, 'timestamp'), 'isoformat')
                    else self._get_row_value(row, 'timestamp')
                ),
            }

        return preview_map

    async def _send_service_desk_text(
        self,
        *,
        runtime_bot,
        context: dict[str, str],
        reply_text: str,
    ) -> None:
        adapter = runtime_bot.adapter
        if hasattr(adapter, 'send_service_desk_text'):
            await adapter.send_service_desk_text(context, reply_text)
            return

        bot_client = getattr(adapter, 'bot', None)
        if bot_client is not None and hasattr(bot_client, 'send_text_msg'):
            await bot_client.send_text_msg(
                open_kfid=context['source_entry_id'],
                external_userid=context['external_user_id'],
                msgid=context['last_message_id'],
                content=reply_text,
            )
            return

        adapter_name = getattr(getattr(runtime_bot, 'bot_entity', None), 'adapter', 'unknown')
        raise ValueError(f'service desk reply is not supported for adapter: {adapter_name}')

    async def _get_session(self, session_id: str):
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.ServiceDeskSession).where(
                persistence_service_desk.ServiceDeskSession.session_id == session_id
            )
        )
        return self._unwrap_model(result.first())

    async def _update_session_state(self, session_id: str, **values) -> None:
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_service_desk.ServiceDeskSession)
            .where(persistence_service_desk.ServiceDeskSession.session_id == session_id)
            .values({**values, 'updated_at': _utcnow()})
        )

    async def get_bot_config(self, bot_uuid: str) -> dict | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.ServiceDeskBotConfig).where(
                persistence_service_desk.ServiceDeskBotConfig.bot_uuid == bot_uuid
            )
        )
        row = self._unwrap_model(result.first())
        if row is None:
            return None

        return self.ap.persistence_mgr.serialize_model(
            persistence_service_desk.ServiceDeskBotConfig,
            row,
        )

    async def _touch_session(
        self,
        *,
        session_id: str,
        bot_uuid: str,
        pipeline_uuid: str,
        context: dict[str, str],
        sender_name: str | None,
        queue_status: str | None = None,
    ) -> persistence_service_desk.ServiceDeskSession:
        session = await self._get_session(session_id)
        now = _utcnow()
        update_values = {
            'bot_uuid': bot_uuid,
            'pipeline_uuid': pipeline_uuid,
            'source_entry_id': context['source_entry_id'],
            'external_user_id': context['external_user_id'],
            'last_message_id': context['last_message_id'],
            'last_customer_message_at': now,
            'updated_at': now,
        }
        if queue_status is not None:
            update_values['queue_status'] = queue_status

        if session is None:
            payload = {
                'session_id': session_id,
                'bot_uuid': bot_uuid,
                'pipeline_uuid': pipeline_uuid,
                'mode': 'ai_hosted',
                'queue_status': queue_status or 'ai',
                'source_entry_id': context['source_entry_id'],
                'external_user_id': context['external_user_id'],
                'last_message_id': context['last_message_id'],
                'claimed_by_user_uuid': None,
                'claimed_by_user_name': sender_name,
                'manual_claimed_at': None,
                'silent_since': None,
                'last_customer_message_at': now,
                'last_manual_reply_at': None,
                'unresolved_count': 0,
            }
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.insert(persistence_service_desk.ServiceDeskSession).values(payload)
            )
            return await self._get_session(session_id)

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_service_desk.ServiceDeskSession)
            .where(persistence_service_desk.ServiceDeskSession.session_id == session_id)
            .values(update_values)
        )
        return await self._get_session(session_id)

    async def handle_incoming_message(
        self,
        *,
        bot_entity,
        event,
        adapter,
        pipeline_uuid: str | None = None,
    ) -> ServiceDeskDecision:
        if not hasattr(adapter, 'extract_service_desk_context'):
            return ServiceDeskDecision(action='continue_ai')

        source_event = getattr(event, 'source_platform_object', event)
        context = adapter.extract_service_desk_context(source_event)
        if not context.get('source_entry_id') or not context.get('external_user_id'):
            return ServiceDeskDecision(action='continue_ai')

        session_id = self._get_session_id(event, adapter)
        session = await self._touch_session(
            session_id=session_id,
            bot_uuid=bot_entity.uuid,
            pipeline_uuid=pipeline_uuid or getattr(bot_entity, 'use_pipeline_uuid', '') or '',
            context=context,
            sender_name=self._get_sender_name(event),
        )
        config = await self.get_bot_config(bot_entity.uuid)

        if self._should_mark_silent(
            session,
            timeout_seconds=int(
                (config or {}).get('manual_timeout_seconds', 900)
            ),
        ):
            await self._update_session_state(
                session_id,
                queue_status='silent',
                silent_since=_utcnow(),
            )
            session = await self._get_session(session_id)

        reopened = self._reopen_mode_after_customer_message(
            self._get_value(session, 'queue_status')
        )
        if reopened is not None:
            mode, queue_status = reopened
            await self._update_session_state(
                session_id,
                mode=mode,
                queue_status=queue_status,
                claimed_by_user_uuid=None,
                claimed_by_user_name=None,
                manual_claimed_at=None,
                silent_since=None,
            )
            session = await self._get_session(session_id)

        if self._get_value(session, 'queue_status') == 'manual':
            return ServiceDeskDecision(action='skip_pipeline', reason='manual')

        materials = await self.list_materials(bot_entity.uuid)
        matched_material = match_material(str(getattr(event, 'message_chain', '')), materials)
        if matched_material is not None:
            return ServiceDeskDecision(action='send_material', reason='material', material=matched_material)

        if (
            config is not None
            and config.get('enabled', True)
            and self._contains_keyword(
                str(getattr(event, 'message_chain', '')),
                config.get('handoff_keywords', []),
            )
        ):
            await self._update_session_state(
                session_id,
                mode='manual',
                queue_status='pending_manual',
                handoff_reason='keyword',
            )
            return ServiceDeskDecision(
                action='skip_pipeline',
                reason='pending_manual',
            )

        return ServiceDeskDecision(action='continue_ai')

    async def send_structured_reply(self, *, runtime_bot, event, adapter, material: dict) -> None:
        source_event = getattr(event, 'source_platform_object', event)
        context = adapter.extract_service_desk_context(source_event)
        reply_text = material.get('reply_text', '').strip()
        if not reply_text:
            return

        await self._send_service_desk_text(
            runtime_bot=runtime_bot,
            context=context,
            reply_text=reply_text,
        )

        await self.ap.monitoring_service.record_message(
            bot_id=runtime_bot.bot_entity.uuid,
            bot_name=runtime_bot.bot_entity.name,
            pipeline_id=runtime_bot.bot_entity.use_pipeline_uuid or '',
            pipeline_name=runtime_bot.bot_entity.use_pipeline_name or '',
            message_content=reply_text,
            session_id=self._get_session_id(event, adapter),
            status='success',
            level='info',
            platform=getattr(runtime_bot.bot_entity, 'adapter', 'wecomcs'),
            user_id=context['external_user_id'],
            user_name=self._get_sender_name(event),
            role='assistant',
        )

    async def reply_to_session(self, session_id: str, reply_text: str) -> None:
        desk_session = await self._get_session(session_id)
        if desk_session is None:
            raise ValueError('service desk session not found')

        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(desk_session.bot_uuid)
        if runtime_bot is None:
            raise ValueError('runtime bot not found')

        await self._send_service_desk_text(
            runtime_bot=runtime_bot,
            context=self._build_reply_context(desk_session),
            reply_text=reply_text,
        )

        await self.ap.monitoring_service.record_message(
            bot_id=desk_session.bot_uuid,
            bot_name=runtime_bot.bot_entity.name,
            pipeline_id=desk_session.pipeline_uuid,
            pipeline_name=runtime_bot.bot_entity.use_pipeline_name,
            message_content=reply_text,
            session_id=session_id,
            platform=getattr(runtime_bot.bot_entity, 'adapter', 'wecomcs'),
            user_id=desk_session.external_user_id,
            role='assistant',
        )

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_service_desk.ServiceDeskSession)
            .where(persistence_service_desk.ServiceDeskSession.session_id == session_id)
            .values(
                mode='manual',
                queue_status='manual',
                last_manual_reply_at=_utcnow(),
                silent_since=None,
                updated_at=_utcnow(),
            )
        )

    async def set_session_mode(self, session_id: str, mode: str) -> None:
        if mode not in {'ai_hosted', 'manual', 'ai_assist'}:
            raise ValueError(f'unsupported mode: {mode}')

        session = await self._get_session(session_id)
        if session is None:
            raise ValueError(f'session not found: {session_id}')

        queue_status = 'manual' if mode in {'manual', 'ai_assist'} else 'ai'
        await self._update_session_state(
            session_id,
            mode=mode,
            queue_status=queue_status,
        )

    async def generate_assist_draft(self, session_id: str, operator_user_id: str) -> dict:
        session = await self._get_session(session_id)
        if session is None:
            raise ValueError(f'session not found: {session_id}')

        return {
            'session_id': session_id,
            'reply_text': 'AI assist draft placeholder',
            'source': 'ai_assist',
            'sent': False,
            'operator_user_id': operator_user_id,
        }

    async def get_session_detail(self, session_id: str) -> dict:
        session = await self._get_session(session_id)
        if session is None:
            raise ValueError(f'session not found: {session_id}')

        serialized_session = (
            self.ap.persistence_mgr.serialize_model(
                persistence_service_desk.ServiceDeskSession,
                session,
            )
            if hasattr(self.ap, 'persistence_mgr')
            else session
        )

        messages: list[dict] = []
        monitoring_service = getattr(self.ap, 'monitoring_service', None)
        if monitoring_service is not None and hasattr(monitoring_service, 'get_messages'):
            messages, _ = await monitoring_service.get_messages(
                session_ids=[session_id],
                limit=200,
                offset=0,
            )

        bot_payload = {'uuid': self._get_value(session, 'bot_uuid')}
        platform_mgr = getattr(self.ap, 'platform_mgr', None)
        if platform_mgr is not None and hasattr(platform_mgr, 'get_bot_by_uuid'):
            runtime_bot = await platform_mgr.get_bot_by_uuid(self._get_value(session, 'bot_uuid'))
            if runtime_bot is not None:
                bot_payload['name'] = getattr(getattr(runtime_bot, 'bot_entity', None), 'name', None)

        return {
            'session': serialized_session,
            'messages': messages,
            'bot': bot_payload,
            'assist_draft': None,
        }

    async def release_session(self, session_id: str) -> None:
        session = await self._get_session(session_id)
        if session is None:
            raise ValueError(f'session not found: {session_id}')

        await self._update_session_state(
            session_id,
            mode='manual',
            queue_status='pending_manual',
            claimed_by_user_uuid=None,
            claimed_by_user_name=None,
            manual_claimed_at=None,
        )

    async def return_session_to_ai(self, session_id: str) -> None:
        session = await self._get_session(session_id)
        if session is None:
            raise ValueError(f'session not found: {session_id}')

        await self._update_session_state(
            session_id,
            mode='ai_hosted',
            queue_status='ai',
            claimed_by_user_uuid=None,
            claimed_by_user_name=None,
            manual_claimed_at=None,
            silent_since=None,
            last_manual_reply_at=None,
        )

    async def list_bot_configs(self) -> list[dict]:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.ServiceDeskBotConfig)
        )

        return [
            self.ap.persistence_mgr.serialize_model(persistence_service_desk.ServiceDeskBotConfig, row)
            for row in result.all()
        ]

    async def upsert_bot_config(self, bot_uuid: str, data: dict) -> None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.ServiceDeskBotConfig).where(
                persistence_service_desk.ServiceDeskBotConfig.bot_uuid == bot_uuid
            )
        )
        exists = result.first()
        payload = {'bot_uuid': bot_uuid, **data}

        if exists is None:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.insert(persistence_service_desk.ServiceDeskBotConfig).values(payload)
            )
            return

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_service_desk.ServiceDeskBotConfig)
            .where(persistence_service_desk.ServiceDeskBotConfig.bot_uuid == bot_uuid)
            .values({**data, 'updated_at': _utcnow()})
        )

    async def list_materials(self, bot_uuid: str) -> list[dict]:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.ServiceDeskMaterial)
            .where(persistence_service_desk.ServiceDeskMaterial.bot_uuid == bot_uuid)
            .order_by(persistence_service_desk.ServiceDeskMaterial.priority.asc())
        )

        return [
            self.ap.persistence_mgr.serialize_model(persistence_service_desk.ServiceDeskMaterial, row)
            for row in result.all()
        ]

    async def create_material(self, bot_uuid: str, data: dict) -> str:
        material_uuid = str(uuid.uuid4())
        payload = {
            'uuid': material_uuid,
            'bot_uuid': bot_uuid,
            'material_type': data['material_type'],
            'title': data['title'],
            'trigger_keywords': data.get('trigger_keywords', []),
            'reply_text': data['reply_text'],
            'payload': data.get('payload', {}),
            'priority': data.get('priority', 100),
            'enabled': data.get('enabled', True),
        }
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_service_desk.ServiceDeskMaterial).values(payload)
        )
        return material_uuid

    async def list_quick_replies(self, bot_uuid: str) -> list[dict]:
        items = await self.list_materials(bot_uuid)
        return [
            item
            for item in items
            if item.get('enabled', True)
            and item.get('material_type') in QUICK_REPLY_TYPES
        ]

    async def list_workbench_sessions(
        self,
        bot_uuid: str | None = None,
        queue_status: str | None = None,
        claimed_by: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        filters: list[sqlalchemy.ColumnElement[bool]] = []

        if bot_uuid:
            filters.append(persistence_service_desk.ServiceDeskSession.bot_uuid == bot_uuid)
        if queue_status:
            filters.append(persistence_service_desk.ServiceDeskSession.queue_status == queue_status)
        if claimed_by:
            if claimed_by == 'claimed':
                filters.append(
                    persistence_service_desk.ServiceDeskSession.claimed_by_user_uuid.is_not(None)
                )
            elif claimed_by == 'unclaimed':
                filters.append(
                    persistence_service_desk.ServiceDeskSession.claimed_by_user_uuid.is_(None)
                )
            else:
                filters.append(
                    persistence_service_desk.ServiceDeskSession.claimed_by_user_uuid == claimed_by
                )
        if keyword:
            filters.append(
                sqlalchemy.or_(
                    persistence_service_desk.ServiceDeskSession.external_user_id.contains(keyword),
                    persistence_service_desk.ServiceDeskSession.session_id.contains(keyword),
                    persistence_service_desk.ServiceDeskSession.claimed_by_user_name.contains(keyword),
                )
            )

        base_query = sqlalchemy.select(persistence_service_desk.ServiceDeskSession)
        count_query = sqlalchemy.select(sqlalchemy.func.count()).select_from(persistence_service_desk.ServiceDeskSession)

        if filters:
            base_query = base_query.where(*filters)
            count_query = count_query.where(*filters)

        result = await self.ap.persistence_mgr.execute_async(
            base_query.order_by(persistence_service_desk.ServiceDeskSession.updated_at.desc()).limit(limit).offset(offset)
        )
        total_result = await self.ap.persistence_mgr.execute_async(count_query)
        total = int(total_result.scalar() or 0)

        items = [
            self.ap.persistence_mgr.serialize_model(persistence_service_desk.ServiceDeskSession, row)
            for row in result.all()
        ]

        preview_map = await self._load_last_message_previews(
            [
                str(item.get('session_id', '') or '')
                for item in items
                if item.get('session_id')
            ]
        )
        for item in items:
            item.update(preview_map.get(str(item.get('session_id', '') or ''), {}))

        return items, total

    async def claim_session(self, session_id: str, user_uuid: str, user_name: str) -> None:
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_service_desk.ServiceDeskSession)
            .where(persistence_service_desk.ServiceDeskSession.session_id == session_id)
            .values(
                mode='manual',
                queue_status='manual',
                claimed_by_user_uuid=user_uuid,
                claimed_by_user_name=user_name,
                manual_claimed_at=_utcnow(),
                updated_at=_utcnow(),
            )
        )

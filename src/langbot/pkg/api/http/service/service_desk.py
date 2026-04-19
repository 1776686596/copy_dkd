from __future__ import annotations

import datetime
import inspect
import json
import re
import uuid
from dataclasses import dataclass

import sqlalchemy

from ....core import app
from ....entity.persistence import monitoring as persistence_monitoring
from ....entity.persistence import service_desk as persistence_service_desk
from ....entity.persistence import pipeline as persistence_pipeline


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
SERVICE_DESK_TIMELINE_LIMIT = 1000


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
    def _is_unresolved_followup(message_text: str) -> bool:
        normalized = str(message_text or '').strip().lower()
        unresolved_markers = [
            '没解决',
            '没有解决',
            '未解决',
            '还是不行',
            '还是不可以',
            '还是失败',
            '仍然不行',
            '依然不行',
            '还是有问题',
        ]
        return any(marker in normalized for marker in unresolved_markers)

    @staticmethod
    def _match_handoff_keyword(message_text: str, keywords: list[str]) -> str | None:
        normalized = message_text.strip().lower()
        for keyword in keywords:
            candidate = keyword.strip()
            if candidate and candidate.lower() in normalized:
                return candidate
        return None

    @staticmethod
    def _build_reply_context(source) -> dict[str, str]:
        return {
            'source_entry_id': str(ServiceDeskService._get_value(source, 'source_entry_id', '') or ''),
            'external_user_id': str(ServiceDeskService._get_value(source, 'external_user_id', '') or ''),
            'last_message_id': str(ServiceDeskService._get_value(source, 'last_message_id', '') or ''),
        }

    @staticmethod
    def _serialize_message_content(message_chain) -> str:
        if hasattr(message_chain, 'model_dump'):
            return json.dumps(message_chain.model_dump(), ensure_ascii=False)
        return str(message_chain or '')

    @staticmethod
    def _compact_preview_text(value: str, limit: int = 120) -> str:
        normalized = re.sub(r'\s+', ' ', value).strip()
        if len(normalized) <= limit:
            return normalized
        return f'{normalized[: limit - 3].rstrip()}...'

    @staticmethod
    async def _call_async_method(target, method_name: str, *args, **kwargs):
        method = getattr(target, method_name, None)
        if method is None or not inspect.iscoroutinefunction(method):
            return None
        return await method(*args, **kwargs)

    async def _load_pipeline_config(self, pipeline_uuid: str) -> dict:
        if not pipeline_uuid:
            return {}

        runtime_pipeline = await self._call_async_method(
            getattr(self.ap, 'pipeline_mgr', None),
            'get_pipeline_by_uuid',
            pipeline_uuid,
        )
        runtime_entity = getattr(runtime_pipeline, 'pipeline_entity', None)
        runtime_config = getattr(runtime_entity, 'config', None)
        if isinstance(runtime_config, dict):
            return runtime_config

        result = await self._call_async_method(
            getattr(self.ap, 'persistence_mgr', None),
            'execute_async',
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid
            ),
        )
        if result is None:
            return {}

        row = self._unwrap_model(result.first())
        config = self._get_value(row, 'config', {})
        return config if isinstance(config, dict) else {}

    async def _get_wecom_private_welcome_text(self, pipeline_uuid: str) -> str:
        config = await self._load_pipeline_config(pipeline_uuid)
        ai_config = config.get('ai', {}) if isinstance(config, dict) else {}
        if not isinstance(ai_config, dict):
            return ''

        local_agent_config = ai_config.get('local-agent', {})
        if not isinstance(local_agent_config, dict):
            return ''

        opening_intro = local_agent_config.get('opening-intro')
        if not isinstance(opening_intro, str):
            return ''

        return opening_intro.strip()

    async def _get_wecom_private_reception_config(self, bot_uuid: str) -> dict:
        config = await self._call_async_method(
            getattr(self.ap, 'wecom_private_service', None),
            'get_reception_config',
            bot_uuid,
        )
        default_config = {
            'bot_uuid': bot_uuid,
            'reception_enabled': True,
            'welcome_enabled': True,
            'fallback_reply_text': '',
            'binding_required_fields': ['uid', 'server'],
            'binding_trigger_keywords': [],
            'binding_prompt_text': '',
        }
        if isinstance(config, dict):
            default_config.update(config)
        return default_config

    @staticmethod
    def _build_reply_material(reply_text: str) -> dict:
        return {
            'material_type': 'quick_reply',
            'title': 'AI Reception',
            'reply_text': str(reply_text or '').strip(),
            'trigger_keywords': [],
            'payload': {},
            'priority': 0,
            'enabled': True,
        }

    @staticmethod
    def _extract_binding_values(message_text: str) -> dict[str, str]:
        text = str(message_text or '')
        patterns = {
            'uid': r'(?:uid|角色id)[:：\s]*([A-Za-z0-9_-]+)',
            'server': r'(?:区服|服务器)[:：\s]*([A-Za-z0-9_-]+)',
            'role_name': r'(?:角色名|角色名称)[:：\s]*([^\s,，]+)',
        }
        values: dict[str, str] = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                values[key] = match.group(1).strip()
        return values

    async def _send_wecom_private_welcome_message_if_needed(
        self,
        *,
        bot_entity,
        source_event,
        pipeline_uuid: str,
        reception_config: dict | None = None,
    ) -> None:
        if getattr(bot_entity, 'adapter', None) != 'wecomprivate':
            return
        if not self._get_value(reception_config, 'reception_enabled', True):
            return
        if not self._get_value(reception_config, 'welcome_enabled', True):
            return

        welcome_code = str(getattr(source_event, 'welcome_code', '') or '').strip()
        if not welcome_code:
            return

        welcome_text = await self._get_wecom_private_welcome_text(pipeline_uuid)
        if not welcome_text:
            return

        try:
            await self._call_async_method(
                getattr(self.ap, 'wecom_private_service', None),
                'send_welcome_message',
                bot_uuid=bot_entity.uuid,
                welcome_code=welcome_code,
                text=welcome_text,
            )
        except Exception as exc:
            logger = getattr(self.ap, 'logger', None)
            if logger is not None and hasattr(logger, 'warning'):
                logger.warning(f'Failed to send wecom private welcome message: {exc}')
            return

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

    @staticmethod
    def _normalize_message_timestamp(value) -> tuple[float, str]:
        if value is None:
            return (0.0, '')
        if isinstance(value, datetime.datetime):
            return (value.timestamp(), value.isoformat())
        if hasattr(value, 'timestamp') and hasattr(value, 'isoformat'):
            return (float(value.timestamp()), value.isoformat())
        if isinstance(value, str):
            normalized = value.replace('Z', '+00:00')
            try:
                parsed = datetime.datetime.fromisoformat(normalized)
            except ValueError:
                return (0.0, value)
            return (parsed.timestamp(), value)
        return (0.0, str(value))

    @classmethod
    def _build_timeline_message_key(cls, message: dict) -> str:
        message_id = str(message.get('id') or '').strip()
        if message_id:
            return message_id

        _timestamp_value, timestamp_text = cls._normalize_message_timestamp(
            message.get('timestamp')
        )
        return '::'.join(
            [
                str(message.get('session_id') or ''),
                timestamp_text,
                str(message.get('role') or ''),
                str(message.get('message_content') or ''),
            ]
        )

    @classmethod
    def _merge_timeline_messages(cls, *message_groups: list[dict]) -> list[dict]:
        merged: dict[str, dict] = {}
        for group in message_groups:
            for message in group or []:
                if not isinstance(message, dict):
                    continue
                key = cls._build_timeline_message_key(message)
                if key not in merged:
                    merged[key] = message

        return sorted(
            merged.values(),
            key=lambda item: (
                cls._normalize_message_timestamp(item.get('timestamp'))[0],
                str(item.get('id') or ''),
            ),
        )

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

    async def _load_messages_by_external_user(
        self,
        *,
        bot_uuid: str,
        external_user_id: str,
        limit: int = SERVICE_DESK_TIMELINE_LIMIT,
    ) -> list[dict]:
        if not bot_uuid or not external_user_id:
            return []

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringMessage)
            .where(
                persistence_monitoring.MonitoringMessage.bot_id == bot_uuid,
                persistence_monitoring.MonitoringMessage.user_id == external_user_id,
            )
            .order_by(
                persistence_monitoring.MonitoringMessage.timestamp.asc(),
                persistence_monitoring.MonitoringMessage.id.asc(),
            )
            .limit(limit)
        )

        messages: list[dict] = []
        for row in result.all():
            msg = row[0] if isinstance(row, tuple) else self._unwrap_model(row)
            serialized_msg = self.ap.persistence_mgr.serialize_model(
                persistence_monitoring.MonitoringMessage,
                msg,
            )
            messages.append(serialized_msg)

        return messages

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

    async def _record_intercepted_customer_message(
        self,
        *,
        bot_entity,
        event,
        session_id: str,
        context: dict[str, str],
        pipeline_uuid: str | None = None,
    ) -> None:
        monitoring_service = getattr(self.ap, 'monitoring_service', None)
        if monitoring_service is None or not hasattr(monitoring_service, 'record_message'):
            return

        pipeline_id = pipeline_uuid or getattr(bot_entity, 'use_pipeline_uuid', '') or ''
        pipeline_name = getattr(bot_entity, 'use_pipeline_name', '') or pipeline_id
        bot_name = getattr(bot_entity, 'name', None) or getattr(bot_entity, 'uuid', '')
        sender_name = self._get_sender_name(event)
        user_id = str(context.get('external_user_id') or getattr(getattr(event, 'sender', None), 'id', '') or '')

        try:
            await monitoring_service.record_message(
                bot_id=bot_entity.uuid,
                bot_name=bot_name,
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
                message_content=self._serialize_message_content(
                    getattr(event, 'message_chain', '')
                ),
                session_id=session_id,
                status='success',
                level='info',
                platform=getattr(bot_entity, 'adapter', None),
                user_id=user_id,
                user_name=sender_name,
                role='user',
            )

            if hasattr(monitoring_service, 'update_session_activity'):
                session_updated = await monitoring_service.update_session_activity(
                    session_id,
                    pipeline_id=pipeline_id,
                    pipeline_name=pipeline_name,
                )
                if (
                    not session_updated
                    and hasattr(monitoring_service, 'record_session_start')
                ):
                    await monitoring_service.record_session_start(
                        session_id=session_id,
                        bot_id=bot_entity.uuid,
                        bot_name=bot_name,
                        pipeline_id=pipeline_id,
                        pipeline_name=pipeline_name,
                        platform=getattr(bot_entity, 'adapter', None),
                        user_id=user_id or None,
                        user_name=sender_name,
                    )
        except Exception:
            return

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
        lead_id: str | None = None,
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
        if lead_id is not None:
            update_values['lead_id'] = lead_id

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
                'claimed_by_user_name': None,
                'manual_claimed_at': None,
                'silent_since': None,
                'last_customer_message_at': now,
                'last_manual_reply_at': None,
                'unresolved_count': 0,
                'lead_id': lead_id,
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

        wecom_private_service = getattr(self.ap, 'wecom_private_service', None)
        lead = None
        if getattr(bot_entity, 'adapter', None) == 'wecomprivate':
            lead = await self._call_async_method(
                wecom_private_service,
                'bootstrap_private_lead',
                bot_uuid=bot_entity.uuid,
                external_user_id=context['external_user_id'],
                follow_user_id=str(getattr(source_event, 'follow_user_id', '') or ''),
                source_entry_id=context['source_entry_id'],
            )

        session_id = self._get_session_id(event, adapter)
        session = await self._touch_session(
            session_id=session_id,
            bot_uuid=bot_entity.uuid,
            pipeline_uuid=pipeline_uuid or getattr(bot_entity, 'use_pipeline_uuid', '') or '',
            context=context,
            sender_name=self._get_sender_name(event),
            lead_id=self._get_value(lead, 'id'),
        )
        reception_config = {}
        if getattr(bot_entity, 'adapter', None) == 'wecomprivate':
            reception_config = await self._get_wecom_private_reception_config(bot_entity.uuid)
        resolved_pipeline_uuid = pipeline_uuid or getattr(bot_entity, 'use_pipeline_uuid', '') or ''
        await self._send_wecom_private_welcome_message_if_needed(
            bot_entity=bot_entity,
            source_event=source_event,
            pipeline_uuid=resolved_pipeline_uuid,
            reception_config=reception_config,
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

        queue_status = self._get_value(session, 'queue_status')
        if queue_status in {'manual', 'pending_manual'}:
            await self._record_intercepted_customer_message(
                bot_entity=bot_entity,
                event=event,
                session_id=session_id,
                context=context,
                pipeline_uuid=pipeline_uuid,
            )
            return ServiceDeskDecision(action='skip_pipeline', reason=queue_status)

        materials = await self.list_materials(bot_entity.uuid)
        matched_material = match_material(str(getattr(event, 'message_chain', '')), materials)
        if matched_material is not None:
            await self._record_intercepted_customer_message(
                bot_entity=bot_entity,
                event=event,
                session_id=session_id,
                context=context,
                pipeline_uuid=pipeline_uuid,
            )
            return ServiceDeskDecision(action='send_material', reason='material', material=matched_material)

        matched_keyword = None
        if config is not None and config.get('enabled', True):
            matched_keyword = self._match_handoff_keyword(
                str(getattr(event, 'message_chain', '')),
                config.get('handoff_keywords', []),
            )

        if matched_keyword is not None:
            await self._update_session_state(
                session_id,
                mode='manual',
                queue_status='pending_manual',
                handoff_reason='keyword',
            )
            if getattr(bot_entity, 'adapter', None) == 'wecomprivate':
                await self._call_async_method(
                    wecom_private_service,
                    'record_routing_decision',
                    session_id=session_id,
                    trigger_type='rule',
                    trigger_reason='keyword',
                    decision='pending_manual',
                    matched_rule=matched_keyword,
                    confidence=1.0,
                )
            await self._record_intercepted_customer_message(
                bot_entity=bot_entity,
                event=event,
                session_id=session_id,
                context=context,
                pipeline_uuid=pipeline_uuid,
            )
            return ServiceDeskDecision(
                action='skip_pipeline',
                reason='pending_manual',
            )

        if (
            getattr(bot_entity, 'adapter', None) == 'wecomprivate'
            and reception_config.get('reception_enabled', True)
        ):
            overlay = await self._call_async_method(
                wecom_private_service,
                'get_session_overlay',
                session_id,
            )
            binding_task = overlay.get('binding_task') if isinstance(overlay, dict) else None
            message_text = str(getattr(event, 'message_chain', '') or '')
            required_fields = reception_config.get('binding_required_fields') or ['uid', 'server']
            trigger_keywords = reception_config.get('binding_trigger_keywords') or []
            extracted_values = self._extract_binding_values(message_text)
            current_values = {
                'uid': str(self._get_value(binding_task, 'provided_uid', '') or ''),
                'server': str(self._get_value(binding_task, 'provided_server', '') or ''),
                'role_name': str(self._get_value(binding_task, 'provided_role_name', '') or ''),
            }
            binding_task_pending = (
                str(self._get_value(binding_task, 'verify_status', '') or '') == 'pending'
            )
            merged_values = {
                key: extracted_values.get(key) or current_values.get(key, '')
                for key in ('uid', 'server', 'role_name')
            }
            missing_fields = [field for field in required_fields if not merged_values.get(field)]

            if (
                missing_fields
                and (
                    self._contains_keyword(message_text, trigger_keywords)
                    or binding_task_pending
                )
            ):
                await self._call_async_method(
                    wecom_private_service,
                    'upsert_binding_task',
                    session_id=session_id,
                    data={
                        'requested_fields': required_fields,
                        'provided_uid': merged_values.get('uid') or None,
                        'provided_server': merged_values.get('server') or None,
                        'provided_role_name': merged_values.get('role_name') or None,
                        'verify_status': 'pending',
                    },
                )
                await self._record_intercepted_customer_message(
                    bot_entity=bot_entity,
                    event=event,
                    session_id=session_id,
                    context=context,
                    pipeline_uuid=pipeline_uuid,
                )
                return ServiceDeskDecision(
                    action='send_material_and_skip',
                    reason='binding_required',
                    material=self._build_reply_material(
                        reception_config.get('binding_prompt_text')
                        or '请补充 UID / 区服 信息'
                    ),
                )

            if binding_task_pending and not missing_fields:
                await self._call_async_method(
                    wecom_private_service,
                    'upsert_binding_task',
                    session_id=session_id,
                    data={
                        'requested_fields': required_fields,
                        'provided_uid': merged_values.get('uid') or None,
                        'provided_server': merged_values.get('server') or None,
                        'provided_role_name': merged_values.get('role_name') or None,
                        'verify_status': 'completed',
                    },
                )

            if self._is_unresolved_followup(message_text):
                next_unresolved_count = int(
                    self._get_value(session, 'unresolved_count', 0) or 0
                ) + 1
                fallback_threshold = int(
                    (config or {}).get('fallback_unresolved_count', 2) or 2
                )
                fallback_reply_text = str(
                    reception_config.get('fallback_reply_text') or ''
                ).strip()
                if next_unresolved_count >= fallback_threshold and fallback_reply_text:
                    await self._update_session_state(
                        session_id,
                        unresolved_count=next_unresolved_count,
                        mode='manual',
                        queue_status='pending_manual',
                        handoff_reason='fallback_unresolved',
                    )
                    await self._call_async_method(
                        wecom_private_service,
                        'record_routing_decision',
                        session_id=session_id,
                        trigger_type='fallback',
                        trigger_reason='unresolved_threshold',
                        decision='pending_manual',
                        matched_rule=None,
                        confidence=1.0,
                    )
                    await self._record_intercepted_customer_message(
                        bot_entity=bot_entity,
                        event=event,
                        session_id=session_id,
                        context=context,
                        pipeline_uuid=pipeline_uuid,
                    )
                    return ServiceDeskDecision(
                        action='send_material_and_skip',
                        reason='fallback_route',
                        material=self._build_reply_material(fallback_reply_text),
                    )

                await self._update_session_state(
                    session_id,
                    unresolved_count=next_unresolved_count,
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

        direct_messages: list[dict] = []
        monitoring_service = getattr(self.ap, 'monitoring_service', None)
        if monitoring_service is not None and hasattr(monitoring_service, 'get_messages'):
            direct_messages, _ = await monitoring_service.get_messages(
                session_ids=[session_id],
                limit=SERVICE_DESK_TIMELINE_LIMIT,
                offset=0,
            )
        external_user_messages = await self._load_messages_by_external_user(
            bot_uuid=str(self._get_value(session, 'bot_uuid', '') or ''),
            external_user_id=str(
                self._get_value(session, 'external_user_id', '') or ''
            ),
            limit=SERVICE_DESK_TIMELINE_LIMIT,
        )
        messages = self._merge_timeline_messages(
            external_user_messages,
            direct_messages,
        )

        bot_payload = {'uuid': self._get_value(session, 'bot_uuid')}
        platform_mgr = getattr(self.ap, 'platform_mgr', None)
        if platform_mgr is not None and hasattr(platform_mgr, 'get_bot_by_uuid'):
            runtime_bot = await platform_mgr.get_bot_by_uuid(self._get_value(session, 'bot_uuid'))
            if runtime_bot is not None:
                bot_payload['name'] = getattr(getattr(runtime_bot, 'bot_entity', None), 'name', None)

        overlay = {
            'lead': None,
            'routing_decisions': [],
            'binding_task': None,
            'closure_record': None,
        }
        wecom_private_service = getattr(self.ap, 'wecom_private_service', None)
        overlay_payload = await self._call_async_method(
            wecom_private_service,
            'get_session_overlay',
            session_id,
        )
        if isinstance(overlay_payload, dict):
            overlay = overlay_payload

        return {
            'session': serialized_session,
            'messages': messages,
            'bot': bot_payload,
            'assist_draft': None,
            **overlay,
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

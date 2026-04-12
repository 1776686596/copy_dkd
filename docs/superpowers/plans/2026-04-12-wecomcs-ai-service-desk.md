# WeCom CS AI Service Desk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a WeCom customer-service-only AI service desk on top of the existing LangBot codebase, with multi-account access, AI-hosted reception, manual takeover, structured link/gift replies, and reusable knowledge-base-backed pipelines.

**Architecture:** Reuse `Bot` as the WeCom customer-service account, reuse `LegacyPipeline` as the AI agent profile, and reuse `KnowledgeBase` as the RAG resource. Add a small `service_desk_*` persistence overlay for desk-only state (manual takeover queue, structured reply materials, and per-bot desk config), then integrate it into `RuntimeBot` before the normal pipeline enqueue step so the implementation stays aligned with the current message flow and monitoring model.

**Tech Stack:** Python 3.11+, Quart, SQLAlchemy async ORM, existing LangBot persistence migrations, React 19 + Vite + TypeScript, existing `BackendClient`, existing monitoring and knowledge-base pages.

---

## Related Docs

- Development outline: `docs/superpowers/specs/2026-04-12-wecomcs-ai-service-desk-development-outline-design.md`
- Phase roadmap: `docs/superpowers/plans/2026-04-12-wecomcs-roadmap.md`

---

## Tech Stack Rules

- Keep the existing backend stack: `Python + Quart + SQLAlchemy Async`.
- Keep the existing frontend stack: `React + Vite + TypeScript`.
- Keep `wecomcs` as the only business channel in V1; do not introduce another channel framework.
- Reuse `Bot` for customer-service account management; do not create a parallel account subsystem.
- Reuse `LegacyPipeline` for AI profile configuration; do not create a second agent-config subsystem in V1.
- Reuse `KnowledgeBase` for RAG resources; do not create a second knowledge-base subsystem.
- Reuse `MonitoringSession` and `MonitoringMessage` as the primary conversation log; only add service-desk-specific overlay state where current monitoring fields are insufficient.
- Default local development database: `SQLite`.
- Default production database: `PostgreSQL`.
- Default V1 vector database: `Chroma`.
- Default V1 file storage: `local`.
- Default V1 workbench refresh model: HTTP polling first, WebSocket later if operationally necessary.
- Default V1 timeout / silent-state handling: in-process scheduled logic first, not Redis/Celery/MQ.
- Prefer extension or refactor over copying existing `bot / pipeline / knowledge / monitoring` logic.

---

### Task 1: Add service-desk persistence models and migration

**Files:**
- Create: `src/langbot/pkg/entity/persistence/service_desk.py`
- Create: `src/langbot/pkg/persistence/migrations/dbm026_service_desk_tables.py`
- Modify: `src/langbot/pkg/utils/constants.py`
- Test: `tests/unit_tests/service_desk/test_models.py`

- [ ] **Step 1: Write the failing model test**

```python
import sqlalchemy


def test_required_database_version_is_26():
    from langbot.pkg.utils import constants

    assert constants.required_database_version == 26


def test_service_desk_session_has_manual_takeover_fields():
    from langbot.pkg.entity.persistence.service_desk import ServiceDeskSession

    columns = ServiceDeskSession.__table__.c

    assert 'session_id' in columns
    assert 'bot_uuid' in columns
    assert 'mode' in columns
    assert 'queue_status' in columns
    assert 'source_entry_id' in columns
    assert 'last_message_id' in columns
    assert 'claimed_by_user_uuid' in columns
    assert 'silent_since' in columns


def test_service_desk_material_has_keyword_and_payload_fields():
    from langbot.pkg.entity.persistence.service_desk import ServiceDeskMaterial

    columns = ServiceDeskMaterial.__table__.c

    assert isinstance(columns['trigger_keywords'].type, sqlalchemy.JSON)
    assert isinstance(columns['payload'].type, sqlalchemy.JSON)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_models.py -v`

Expected: FAIL with `ModuleNotFoundError` for `langbot.pkg.entity.persistence.service_desk` and version assertion failure because `required_database_version` is still `25`.

- [ ] **Step 3: Write the minimal persistence layer and migration**

```python
# src/langbot/pkg/entity/persistence/service_desk.py
import sqlalchemy

from .base import Base


class ServiceDeskBotConfig(Base):
    __tablename__ = 'service_desk_bot_configs'

    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    version_label = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    handoff_keywords = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=list)
    fallback_unresolved_count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=2)
    manual_timeout_seconds = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=900)
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class ServiceDeskMaterial(Base):
    __tablename__ = 'service_desk_materials'

    uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    material_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)  # download_link, gift_pack, quick_reply
    title = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    trigger_keywords = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=list)
    reply_text = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    payload = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=dict)
    priority = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=100)
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class ServiceDeskSession(Base):
    __tablename__ = 'service_desk_sessions'

    session_id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    pipeline_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    mode = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, default='ai_hosted')
    queue_status = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, default='ai')  # ai, pending_manual, manual, silent
    handoff_reason = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    source_entry_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    external_user_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    last_message_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    claimed_by_user_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    claimed_by_user_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    manual_claimed_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    silent_since = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    last_customer_message_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    last_manual_reply_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    unresolved_count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )
```

```python
# src/langbot/pkg/persistence/migrations/dbm026_service_desk_tables.py
import sqlalchemy
from .. import migration


@migration.migration_class(26)
class DBMigrateServiceDeskTables(migration.DBMigration):
    async def upgrade(self):
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                '''
                CREATE TABLE service_desk_bot_configs (
                    bot_uuid VARCHAR(255) PRIMARY KEY,
                    version_label VARCHAR(255) NOT NULL,
                    handoff_keywords JSON NOT NULL DEFAULT '[]',
                    fallback_unresolved_count INTEGER NOT NULL DEFAULT 2,
                    manual_timeout_seconds INTEGER NOT NULL DEFAULT 900,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                '''
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                '''
                CREATE TABLE service_desk_materials (
                    uuid VARCHAR(255) PRIMARY KEY,
                    bot_uuid VARCHAR(255) NOT NULL,
                    material_type VARCHAR(50) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    trigger_keywords JSON NOT NULL DEFAULT '[]',
                    reply_text TEXT NOT NULL,
                    payload JSON NOT NULL DEFAULT '{}',
                    priority INTEGER NOT NULL DEFAULT 100,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                '''
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                '''
                CREATE TABLE service_desk_sessions (
                    session_id VARCHAR(255) PRIMARY KEY,
                    bot_uuid VARCHAR(255) NOT NULL,
                    pipeline_uuid VARCHAR(255) NOT NULL,
                    mode VARCHAR(50) NOT NULL DEFAULT 'ai_hosted',
                    queue_status VARCHAR(50) NOT NULL DEFAULT 'ai',
                    handoff_reason VARCHAR(255),
                    source_entry_id VARCHAR(255) NOT NULL,
                    external_user_id VARCHAR(255) NOT NULL,
                    last_message_id VARCHAR(255),
                    claimed_by_user_uuid VARCHAR(255),
                    claimed_by_user_name VARCHAR(255),
                    manual_claimed_at TIMESTAMP,
                    silent_since TIMESTAMP,
                    last_customer_message_at TIMESTAMP,
                    last_manual_reply_at TIMESTAMP,
                    unresolved_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                '''
            )
        )

    async def downgrade(self):
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE service_desk_sessions'))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE service_desk_materials'))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE service_desk_bot_configs'))
```

```python
# src/langbot/pkg/utils/constants.py
required_database_version = 26
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_models.py -v`

Expected: PASS with `3 passed`.

- [ ] **Step 5: Commit**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/entity/persistence/service_desk.py \
  src/langbot/pkg/persistence/migrations/dbm026_service_desk_tables.py \
  src/langbot/pkg/utils/constants.py \
  tests/unit_tests/service_desk/test_models.py
git commit -m "feat(service-desk): add persistence models and migration"
```

### Task 2: Add service-desk backend service and HTTP API

**Files:**
- Create: `src/langbot/pkg/api/http/service/service_desk.py`
- Create: `src/langbot/pkg/api/http/controller/groups/service_desk.py`
- Modify: `src/langbot/pkg/core/stages/build_app.py`
- Modify: `web/src/app/infra/http/BackendClient.ts`
- Modify: `web/src/app/infra/entities/api/index.ts`
- Test: `tests/unit_tests/service_desk/test_service_desk_service.py`

- [ ] **Step 1: Write the failing service test**

```python
import pytest


@pytest.mark.asyncio
async def test_claim_session_sets_manual_owner():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    service = ServiceDeskService(ap=None)

    with pytest.raises(AttributeError):
        await service.claim_session('session-1', 'user-1', '客服A')


def test_match_material_returns_highest_priority_hit():
    from langbot.pkg.api.http.service.service_desk import match_material

    materials = [
        {'title': '礼包', 'priority': 20, 'trigger_keywords': ['礼包'], 'reply_text': '礼包A'},
        {'title': '下载', 'priority': 10, 'trigger_keywords': ['下载'], 'reply_text': '下载A'},
    ]

    matched = match_material('我要下载链接', materials)
    assert matched['title'] == '下载'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_service_desk_service.py -v`

Expected: FAIL with `ModuleNotFoundError` for `service_desk`.

- [ ] **Step 3: Implement the backend service and routes**

```python
# src/langbot/pkg/api/http/service/service_desk.py
from __future__ import annotations

import datetime
import uuid
import sqlalchemy

from ....core import app
from ....entity.persistence import service_desk as persistence_service_desk
from ....entity.persistence import monitoring as persistence_monitoring


def match_material(message_text: str, materials: list[dict]) -> dict | None:
    normalized = message_text.strip().lower()
    for material in sorted(materials, key=lambda item: item['priority']):
        if any(keyword.lower() in normalized for keyword in material['trigger_keywords']):
            return material
    return None


class ServiceDeskService:
    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def list_bot_configs(self) -> list[dict]:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_service_desk.ServiceDeskBotConfig)
        )
        return [
            self.ap.persistence_mgr.serialize_model(persistence_service_desk.ServiceDeskBotConfig, row)
            for row in result.all()
        ]

    async def upsert_bot_config(self, bot_uuid: str, data: dict) -> None:
        payload = {'bot_uuid': bot_uuid, **data}
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_service_desk.ServiceDeskBotConfig)
            .values(payload)
            .prefix_with('OR REPLACE')
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

    async def claim_session(self, session_id: str, user_uuid: str, user_name: str) -> None:
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_service_desk.ServiceDeskSession)
            .where(persistence_service_desk.ServiceDeskSession.session_id == session_id)
            .values(
                mode='manual',
                queue_status='manual',
                claimed_by_user_uuid=user_uuid,
                claimed_by_user_name=user_name,
                manual_claimed_at=datetime.datetime.utcnow(),
            )
        )
```

```python
# src/langbot/pkg/api/http/controller/groups/service_desk.py
import quart

from .. import group


@group.group_class('service_desk', '/api/v1/service-desk')
class ServiceDeskRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/bot-configs', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def list_bot_configs(user_email: str) -> str:
            return self.success(data={'items': await self.ap.service_desk_service.list_bot_configs()})

        @self.route('/bot-configs/<bot_uuid>', methods=['PUT'], auth_type=group.AuthType.USER_TOKEN)
        async def update_bot_config(bot_uuid: str, user_email: str) -> str:
            payload = await quart.request.json
            await self.ap.service_desk_service.upsert_bot_config(bot_uuid, payload)
            return self.success()

        @self.route('/bots/<bot_uuid>/materials', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN)
        async def materials(bot_uuid: str, user_email: str) -> str:
            if quart.request.method == 'GET':
                return self.success(data={'items': await self.ap.service_desk_service.list_materials(bot_uuid)})
            payload = await quart.request.json
            material_id = await self.ap.service_desk_service.create_material(bot_uuid, payload)
            return self.success(data={'uuid': material_id})

        @self.route('/sessions', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def list_sessions(user_email: str) -> str:
            params = quart.request.args
            items, total = await self.ap.service_desk_service.list_workbench_sessions(
                bot_uuid=params.get('botUuid'),
                queue_status=params.get('queueStatus'),
                claimed_by=params.get('claimedBy'),
                limit=int(params.get('limit', 50)),
                offset=int(params.get('offset', 0)),
            )
            return self.success(data={'sessions': items, 'total': total})

        @self.route('/sessions/<session_id>/claim', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def claim_session(session_id: str, user_email: str) -> str:
            user = await self.ap.user_service.get_user_by_email(user_email)
            await self.ap.service_desk_service.claim_session(session_id, user.uuid, user.email)
            return self.success()
```

```python
# src/langbot/pkg/core/stages/build_app.py
from ...api.http.service import service_desk as service_desk_service

service_desk_service_inst = service_desk_service.ServiceDeskService(ap)
ap.service_desk_service = service_desk_service_inst
```

```ts
// web/src/app/infra/http/BackendClient.ts
public getServiceDeskSessions(params: {
  botUuid?: string;
  queueStatus?: string;
  claimedBy?: string;
  limit?: number;
  offset?: number;
}): Promise<{ sessions: ServiceDeskSession[]; total: number }> {
  const queryParams = new URLSearchParams();
  if (params.botUuid) queryParams.append('botUuid', params.botUuid);
  if (params.queueStatus) queryParams.append('queueStatus', params.queueStatus);
  if (params.claimedBy) queryParams.append('claimedBy', params.claimedBy);
  queryParams.append('limit', String(params.limit ?? 50));
  queryParams.append('offset', String(params.offset ?? 0));
  return this.get(`/api/v1/service-desk/sessions?${queryParams.toString()}`);
}
```

- [ ] **Step 4: Run tests and basic checks**

Run:
- `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_service_desk_service.py -v`
- `cd /home/daisheng/code/copy_dkd/LangBot && uv run ruff check src/langbot/pkg/api/http/service/service_desk.py src/langbot/pkg/api/http/controller/groups/service_desk.py tests/unit_tests/service_desk/test_service_desk_service.py`

Expected:
- `pytest`: PASS
- `ruff`: no errors

- [ ] **Step 5: Commit**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/api/http/service/service_desk.py \
  src/langbot/pkg/api/http/controller/groups/service_desk.py \
  src/langbot/pkg/core/stages/build_app.py \
  web/src/app/infra/http/BackendClient.ts \
  web/src/app/infra/entities/api/index.ts \
  tests/unit_tests/service_desk/test_service_desk_service.py
git commit -m "feat(service-desk): add backend service and api"
```

### Task 3: Integrate service-desk routing into the WeCom CS runtime

**Files:**
- Modify: `src/langbot/pkg/platform/botmgr.py`
- Modify: `src/langbot/pkg/platform/sources/wecomcs.py`
- Modify: `src/langbot/pkg/api/http/service/monitoring.py`
- Test: `tests/unit_tests/service_desk/test_runtime_flow.py`

- [ ] **Step 1: Write the failing runtime test**

```python
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.asyncio
async def test_manual_session_skips_pipeline_enqueue():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskDecision

    event = Mock()
    adapter = Mock()
    ap = Mock()
    ap.service_desk_service.handle_incoming_message = AsyncMock(
        return_value=ServiceDeskDecision(action='skip_pipeline', reason='manual')
    )
    ap.msg_aggregator.add_message = AsyncMock()

    assert ap.msg_aggregator.add_message.await_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_runtime_flow.py -v`

Expected: FAIL because `ServiceDeskDecision` and the new runtime branch do not exist yet.

- [ ] **Step 3: Add the runtime decision branch**

```python
# src/langbot/pkg/api/http/service/service_desk.py
from dataclasses import dataclass


@dataclass
class ServiceDeskDecision:
    action: str  # continue_ai, skip_pipeline, send_material
    reason: str | None = None
    material: dict | None = None
```

```python
# src/langbot/pkg/platform/botmgr.py
decision = await self.ap.service_desk_service.handle_incoming_message(
    bot_entity=self.bot_entity,
    event=event,
    adapter=adapter,
)

if decision.action == 'skip_pipeline':
    await self.logger.info(f'Service desk skipped pipeline: {decision.reason}')
    return

if decision.action == 'send_material':
    await self.ap.service_desk_service.send_structured_reply(
        runtime_bot=self,
        event=event,
        adapter=adapter,
        material=decision.material,
    )
    return
```

```python
# src/langbot/pkg/platform/sources/wecomcs.py
class WecomCSAdapter(...):
    def extract_service_desk_context(self, event: WecomCSEvent) -> dict[str, str]:
        return {
            'source_entry_id': event.receiver_id,
            'external_user_id': event.user_id,
            'last_message_id': str(event.message_id),
        }
```

```python
# src/langbot/pkg/api/http/service/monitoring.py
assistant_message_id = await self.record_message(
    bot_id=bot_id,
    bot_name=bot_name,
    pipeline_id=pipeline_id,
    pipeline_name=pipeline_name,
    message_content=reply_text,
    session_id=session_id,
    platform=platform,
    user_id=user_id,
    user_name=user_name,
    role='assistant',
)
```

- [ ] **Step 4: Run the focused runtime tests**

Run:
- `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_runtime_flow.py -v`
- `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/platform/test_routing_rules.py -v`

Expected:
- New service-desk runtime tests PASS
- Existing routing rules tests continue to PASS

- [ ] **Step 5: Commit**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/platform/botmgr.py \
  src/langbot/pkg/platform/sources/wecomcs.py \
  src/langbot/pkg/api/http/service/monitoring.py \
  tests/unit_tests/service_desk/test_runtime_flow.py
git commit -m "feat(service-desk): integrate runtime routing and manual queue"
```

### Task 4: Add manual-reply APIs and session workbench queries

**Files:**
- Modify: `src/langbot/pkg/api/http/service/service_desk.py`
- Modify: `src/langbot/pkg/api/http/controller/groups/service_desk.py`
- Modify: `src/langbot/pkg/platform/botmgr.py`
- Test: `tests/unit_tests/service_desk/test_manual_reply.py`

- [ ] **Step 1: Write the failing manual reply test**

```python
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.asyncio
async def test_reply_to_session_uses_runtime_bot_and_records_assistant_message():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.platform_mgr.get_bot_by_uuid = AsyncMock()
    ap.monitoring_service.record_message = AsyncMock()
    service = ServiceDeskService(ap)

    with pytest.raises(Exception):
        await service.reply_to_session('session-1', '人工已接手')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_manual_reply.py -v`

Expected: FAIL because `reply_to_session` is not implemented.

- [ ] **Step 3: Implement manual reply and query endpoints**

```python
# src/langbot/pkg/api/http/service/service_desk.py
async def reply_to_session(self, session_id: str, reply_text: str) -> None:
    session_row = await self.ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_service_desk.ServiceDeskSession).where(
            persistence_service_desk.ServiceDeskSession.session_id == session_id
        )
    )
    desk_session = session_row.first()
    if desk_session is None:
        raise ValueError('service desk session not found')

    runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(desk_session.bot_uuid)
    if runtime_bot is None:
        raise ValueError('runtime bot not found')

    await runtime_bot.adapter.bot.send_text_msg(
        open_kfid=desk_session.source_entry_id,
        external_userid=desk_session.external_user_id,
        msgid=desk_session.last_message_id,
        content=reply_text,
    )

    await self.ap.monitoring_service.record_message(
        bot_id=desk_session.bot_uuid,
        bot_name=runtime_bot.bot_entity.name,
        pipeline_id=desk_session.pipeline_uuid,
        pipeline_name=runtime_bot.bot_entity.use_pipeline_name,
        message_content=reply_text,
        session_id=session_id,
        platform='wecomcs',
        user_id=desk_session.external_user_id,
        role='assistant',
    )
```

```python
# src/langbot/pkg/api/http/controller/groups/service_desk.py
@self.route('/sessions/<session_id>/reply', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
async def reply_session(session_id: str, user_email: str) -> str:
    payload = await quart.request.json
    await self.ap.service_desk_service.reply_to_session(session_id, payload['reply_text'])
    return self.success()
```

- [ ] **Step 4: Run tests and the service-desk API checks**

Run:
- `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_manual_reply.py -v`
- `cd /home/daisheng/code/copy_dkd/LangBot && uv run ruff check src/langbot/pkg/api/http/service/service_desk.py src/langbot/pkg/api/http/controller/groups/service_desk.py tests/unit_tests/service_desk/test_manual_reply.py`

Expected:
- `pytest`: PASS
- `ruff`: no errors

- [ ] **Step 5: Commit**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/api/http/service/service_desk.py \
  src/langbot/pkg/api/http/controller/groups/service_desk.py \
  tests/unit_tests/service_desk/test_manual_reply.py
git commit -m "feat(service-desk): add manual reply api"
```

### Task 5: Add the service-desk workbench and admin screens

**Files:**
- Create: `web/src/app/home/service-desk/page.tsx`
- Create: `web/src/app/home/service-desk/ServiceDeskContent.tsx`
- Create: `web/src/app/home/service-desk/components/SessionList.tsx`
- Create: `web/src/app/home/service-desk/components/SessionDetail.tsx`
- Create: `web/src/app/home/service-desk/components/BotDeskConfigForm.tsx`
- Create: `web/src/app/home/service-desk/components/MaterialManager.tsx`
- Modify: `web/src/app/home/components/home-sidebar/sidbarConfigList.tsx`
- Modify: `web/src/app/home/layout.tsx`
- Modify: `web/src/app/infra/http/BackendClient.ts`
- Modify: `web/src/app/infra/entities/api/index.ts`
- Modify: `web/src/i18n/locales/en-US.ts`
- Modify: `web/src/i18n/locales/zh-Hans.ts`

- [ ] **Step 1: Write the failing UI smoke check**

```ts
// Treat the first pass as a build-level smoke check because this repo has no frontend test harness.
// The failure signal is a missing route/type/client method during `pnpm build`.
```

- [ ] **Step 2: Run build to verify the current code does not have the new workbench**

Run: `cd /home/daisheng/code/copy_dkd/LangBot/web && pnpm build`

Expected: PASS now, but there is no `/home/service-desk` route, no service-desk client methods, and no sidebar entry yet.

- [ ] **Step 3: Implement the workbench and config views**

```tsx
// web/src/app/home/service-desk/page.tsx
import ServiceDeskContent from './ServiceDeskContent';

export default function ServiceDeskPage() {
  return <ServiceDeskContent />;
}
```

```tsx
// web/src/app/home/service-desk/ServiceDeskContent.tsx
import { useEffect, useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { httpClient } from '@/app/infra/http/HttpClient';
import SessionList from './components/SessionList';
import SessionDetail from './components/SessionDetail';
import BotDeskConfigForm from './components/BotDeskConfigForm';
import MaterialManager from './components/MaterialManager';

export default function ServiceDeskContent() {
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState([]);

  useEffect(() => {
    httpClient.getServiceDeskSessions({ queueStatus: 'pending_manual', limit: 50, offset: 0 }).then((resp) => {
      setSessions(resp.sessions);
    });
  }, []);

  return (
    <Tabs defaultValue="workbench" className="h-full">
      <TabsList>
        <TabsTrigger value="workbench">客服台</TabsTrigger>
        <TabsTrigger value="bot-config">客服号规则</TabsTrigger>
        <TabsTrigger value="materials">素材库</TabsTrigger>
      </TabsList>
      <TabsContent value="workbench" className="grid grid-cols-[360px_1fr] gap-4">
        <SessionList sessions={sessions} selectedSessionId={selectedSessionId} onSelect={setSelectedSessionId} />
        <SessionDetail sessionId={selectedSessionId} />
      </TabsContent>
      <TabsContent value="bot-config">
        <BotDeskConfigForm />
      </TabsContent>
      <TabsContent value="materials">
        <MaterialManager />
      </TabsContent>
    </Tabs>
  );
}
```

```tsx
// web/src/app/home/components/home-sidebar/sidbarConfigList.tsx
new SidebarChildVO({
  id: 'service-desk',
  name: t('serviceDesk.title'),
  route: '/home/service-desk',
  description: t('serviceDesk.description'),
  helpLink: { en_US: '', zh_Hans: '' },
  section: 'home',
})
```

```ts
// web/src/app/infra/entities/api/index.ts
export interface ServiceDeskSession {
  session_id: string;
  bot_uuid: string;
  pipeline_uuid: string;
  mode: 'ai_hosted' | 'manual';
  queue_status: 'ai' | 'pending_manual' | 'manual' | 'silent';
  source_entry_id: string;
  external_user_id: string;
  claimed_by_user_name?: string | null;
  handoff_reason?: string | null;
  updated_at: string;
}
```

- [ ] **Step 4: Run frontend validation**

Run:
- `cd /home/daisheng/code/copy_dkd/LangBot/web && pnpm lint`
- `cd /home/daisheng/code/copy_dkd/LangBot/web && pnpm build`

Expected:
- `pnpm lint`: no ESLint errors
- `pnpm build`: TypeScript + Vite build passes and the `/home/service-desk` page is included in the SPA output

- [ ] **Step 5: Commit**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add web/src/app/home/service-desk \
  web/src/app/home/components/home-sidebar/sidbarConfigList.tsx \
  web/src/app/home/layout.tsx \
  web/src/app/infra/http/BackendClient.ts \
  web/src/app/infra/entities/api/index.ts \
  web/src/i18n/locales/en-US.ts \
  web/src/i18n/locales/zh-Hans.ts
git commit -m "feat(service-desk): add workbench and admin ui"
```

### Task 6: Verification, regression checks, and delivery notes

**Files:**
- Modify: `docs/TESTING_SUMMARY.md`
- Test: `tests/unit_tests/service_desk/test_end_to_end_rules.py`

- [ ] **Step 1: Write the final focused rule-flow regression test**

```python
import pytest


@pytest.mark.asyncio
async def test_keyword_to_manual_then_timeout_to_silent_then_reopen_to_ai():
    from datetime import datetime, timedelta

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    service = ServiceDeskService(ap=None)

    session = {
        'mode': 'manual',
        'queue_status': 'manual',
        'manual_claimed_at': datetime.utcnow() - timedelta(seconds=901),
        'silent_since': None,
    }

    timed_out = service._should_mark_silent(session, timeout_seconds=900)
    reopened = service._reopen_mode_after_customer_message('silent')

    assert timed_out is True
    assert reopened == ('ai_hosted', 'ai')
```

- [ ] **Step 2: Run the full focused backend suite**

Run:
- `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk -v`
- `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/platform/test_routing_rules.py -v`
- `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/pipeline/test_resprule.py -v`

Expected:
- All new `service_desk` tests PASS
- Existing platform and pipeline rule tests still PASS

- [ ] **Step 3: Run repository-level verification**

Run:
- `cd /home/daisheng/code/copy_dkd/LangBot && uv run ruff check src/langbot tests/unit_tests/service_desk`
- `cd /home/daisheng/code/copy_dkd/LangBot/web && pnpm lint`
- `cd /home/daisheng/code/copy_dkd/LangBot/web && pnpm build`

Expected:
- Ruff clean for the touched backend files
- Frontend lint clean
- Frontend production build succeeds

- [ ] **Step 4: Update the testing note**

```md
## Service Desk Verification

- WeCom customer-service bots are created from the existing Bots page (`adapter = wecomcs`)
- AI profile continues to reuse the existing Pipeline page
- Knowledge resources continue to reuse the existing Knowledge Base page
- New workbench flow to verify manually:
  1. Create a `wecomcs` bot and bind a pipeline
  2. Configure service-desk keywords and materials
  3. Send a normal FAQ -> stays in `ai_hosted`
  4. Send `下载` -> direct structured reply
  5. Send a handoff keyword -> queue becomes `pending_manual`
  6. Claim session and send manual reply
  7. Wait for timeout -> session becomes `silent`
  8. Send the next user message -> session reopens to `ai_hosted`
```

- [ ] **Step 5: Commit**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add docs/TESTING_SUMMARY.md tests/unit_tests/service_desk/test_end_to_end_rules.py
git commit -m "docs(service-desk): add verification notes"
```

## Notes for the implementer

- This plan must follow the tech-stack rules above and the roadmap file `docs/superpowers/plans/2026-04-12-wecomcs-roadmap.md`.
- Keep `wecomcs` account credentials in the existing `bots` table and UI. Do not invent a parallel customer-service-account entity.
- Keep AI profile configuration in the existing `legacy_pipelines` flow and UI. Do not create a second “agent profile” subsystem in V1.
- Keep knowledge resources in the existing `knowledge_bases` flow and UI. The only new binding is desk-specific bot config plus structured materials.
- The critical runtime hook is `RuntimeBot.initialize` in `src/langbot/pkg/platform/botmgr.py`. The new service-desk decision must happen before `msg_aggregator.add_message(...)`.
- Manual reply must not use the generic `BotService.send_message(...)` path because `WecomCSAdapter.send_message(...)` is currently empty. Use the runtime `WecomCSClient.send_text_msg(...)` with values stored in `service_desk_sessions`.

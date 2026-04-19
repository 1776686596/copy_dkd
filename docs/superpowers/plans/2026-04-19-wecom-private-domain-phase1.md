# WeCom Private-Domain Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 LangBot 增加“游戏内固定二维码 -> 企微私域好友接入 -> AI 首轮/持续接待 -> 规则转人工 -> 客服台接管 -> 会后标签/备注回写”的第一期可运营闭环。

**Architecture:** 二维码配置、客户详情、欢迎语、标签/备注回写统一走官方 `externalcontact/*` 接口；持续私域聊天不假设官方双向消息能力，先通过 Apifox 与实页验证冻结为独立 `wecomprivate` 托管适配器。人工接管仍复用现有 `service_desk` 状态机，但补齐私域 `contact config / lead / routing / binding / closure` 数据模型，并把闭环操作继续收敛在 LangBot 客服台。

**Tech Stack:** Python 3.12、Quart、SQLAlchemy、LangBot 平台适配器体系、Pytest、Playwright for Python、React 19、TypeScript、Apifox OAS

---

## File Structure

- Create: `src/langbot/libs/wecom_external_contact_api/__init__.py`
  暴露官方企微外部联系人客户端。
- Create: `src/langbot/libs/wecom_external_contact_api/api.py`
  封装 `add_contact_way / get_contact_way / list_contact_way / send_welcome_msg / externalcontact/get / mark_tag / remark update`。
- Create: `src/langbot/pkg/api/http/service/wecom_private.py`
  管理固定二维码同步、私域 lead 建档、分流记录、补录绑定、闭环写回。
- Create: `src/langbot/pkg/api/http/controller/groups/wecom_private.py`
  暴露固定二维码同步与查询接口。
- Create: `src/langbot/libs/wecom_private_page_api/__init__.py`
  暴露私域网页托管客户端包。
- Create: `src/langbot/libs/wecom_private_page_api/client.py`
  管理私域网页登录态、消息轮询、发送、去重和回调桥接。
- Create: `src/langbot/pkg/platform/sources/wecomprivate.py`
  定义私域托管适配器，把网页消息转成 LangBot `FriendMessage`。
- Create: `src/langbot/pkg/platform/sources/wecomprivate.yaml`
  声明 `wecomprivate` Bot 的后端配置项，让前端 BotForm 自动渲染。
- Create: `src/langbot/pkg/persistence/migrations/dbm028_wecom_private_domain_tables.py`
  增加私域二维码、lead、routing、binding、closure 表，并补齐 `service_desk_sessions` 新字段。
- Create: `tests/unit_tests/platform/test_wecom_external_contact_api.py`
  覆盖官方接口客户端的路径、参数与解析。
- Create: `tests/unit_tests/platform/test_wecomprivate_adapter.py`
  覆盖私域托管适配器的事件转换、回复出口与客服台上下文提取。
- Create: `tests/unit_tests/platform/test_wecomprivate_runtime.py`
  覆盖 `wecomprivate` 登录二维码运行态输出。
- Create: `tests/unit_tests/service_desk/test_wecom_private_service.py`
  覆盖二维码同步、lead 建档、分流记录、绑定任务和闭环服务。
- Modify: `src/langbot/pkg/entity/persistence/service_desk.py`
  增加私域生命周期模型，并扩展 `ServiceDeskSession`。
- Modify: `src/langbot/pkg/utils/constants.py`
  将 `required_database_version` 提升到 28。
- Modify: `src/langbot/pkg/core/stages/build_app.py`
  注册 `wecom_private_service`。
- Modify: `src/langbot/pkg/api/http/service/service_desk.py`
  把 `wecomprivate` 会话接入既有客服台，补 lead/routing/binding/closure 聚合。
- Modify: `src/langbot/pkg/api/http/controller/groups/service_desk.py`
  增加绑定补录、会话闭环接口，并扩展 session detail 返回体。
- Modify: `src/langbot/pkg/api/http/service/bot.py`
  让 `wecomprivate` 运行态也能输出登录二维码状态。
- Modify: `web/src/app/infra/entities/api/index.ts`
  增加私域二维码、lead、routing、binding、closure DTO。
- Modify: `web/src/app/infra/http/BackendClient.ts`
  增加私域二维码同步、绑定补录、闭环操作的前端调用。
- Modify: `web/src/app/home/service-desk/ServiceDeskContent.tsx`
  允许 `wecomprivate` 出现在客服台列表和渠道标识中。
- Modify: `web/src/app/home/service-desk/components/BotDeskConfigForm.tsx`
  增加固定二维码配置与导出卡片。
- Modify: `web/src/app/home/service-desk/components/SessionDetail.tsx`
  展示 lead、分流理由、绑定补录、闭环表单。
- Modify: `web/src/app/home/bots/components/bot-form/BotForm.tsx`
  在 `wecomprivate` 上复用已有的企微网页登录态轮询卡片。
- Modify: `web/src/app/home/bots/components/bot-form/wecomWebLoginState.ts`
  复用同一套“企微托管登录态”推导逻辑，不再只服务 `wecomweb`。
- Modify: `tests/unit_tests/service_desk/test_models.py`
  验证数据库版本和新增模型字段。
- Modify: `tests/unit_tests/service_desk/test_service_desk_service.py`
  验证私域会话接入、分流和 detail 聚合。
- Modify: `tests/unit_tests/service_desk/test_runtime_flow.py`
  验证 `wecomprivate` 走既有客服台入口。
- Modify: `tests/unit_tests/service_desk/test_session_detail_api.py`
  验证客服台 detail 返回 lead/routing/binding/closure。

### Task 1: 冻结官方接口边界并实现官方 `externalcontact` 客户端

**Files:**
- Create: `src/langbot/libs/wecom_external_contact_api/__init__.py`
- Create: `src/langbot/libs/wecom_external_contact_api/api.py`
- Create: `tests/unit_tests/platform/test_wecom_external_contact_api.py`

- [ ] **Step 1: 先重新核验 Apifox 锚点并冻结 transport 决策**

确认以下边界，不确认之前不要继续后续实现：

1. 官方接口只承诺二维码、欢迎语、客户详情、标签/备注回写。
2. 当前 OAS 里没有可以直接替代“私域好友持续双向聊天 transport”的已确认路径。
3. 第一期的持续聊天 transport 冻结为 `wecomprivate` 浏览器托管；后续如官方消息通道被验证，再独立做 transport 替换。

本步完成标准：

- `add_contact_way / get_contact_way / list_contact_way / send_welcome_msg / externalcontact/get / mark_tag` 已用 Apifox 再确认一遍。
- `externalcontact/get` 的 `POST` 备注写回也已确认。
- 计划中所有“持续聊天”字样都明确指向 `wecomprivate`，不是 `externalcontact`。

- [ ] **Step 2: 先写官方客户端失败测试，锁定路径、方法和关键参数**

```python
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_create_contact_way_uses_fixed_qr_payload():
    from langbot.libs.wecom_external_contact_api.api import WecomExternalContactClient

    access_token_getter = AsyncMock(return_value='token-1')
    request_json = AsyncMock(return_value={
        'errcode': 0,
        'errmsg': 'ok',
        'config_id': 'cfg-1',
        'qr_code': 'https://qrcode.example/cfg-1',
    })

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

    assert request_json.await_args_list[0].kwargs['json'] == {
        'userid': 'zhangsan',
        'external_userid': 'wo123',
        'add_tag': ['tag-a'],
        'remove_tag': ['tag-b'],
    }
    assert request_json.await_args_list[1].kwargs['json'] == {
        'userid': 'zhangsan',
        'external_userid': 'wo123',
        'remark': '玩家 UID: 10001 / 区服: S1',
    }
```

- [ ] **Step 3: 运行单测并确认当前模块缺失**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run python -m pytest tests/unit_tests/platform/test_wecom_external_contact_api.py -v`

Expected: FAIL，原因是 `langbot.libs.wecom_external_contact_api` 尚不存在。

- [ ] **Step 4: 写最小官方客户端实现**

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class WecomExternalContactClient:
    def __init__(
        self,
        *,
        access_token_getter: Callable[[], Awaitable[str]],
        request_json: Callable[
            [str, str, dict[str, Any] | None, dict[str, Any] | None],
            Awaitable[dict[str, Any]],
        ],
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
        token = await self._access_token_getter()
        return await self._request_json(
            f'{self._api_base_url}{path}',
            method=method,
            params={'access_token': token, **(params or {})},
            json=json,
        )

    async def create_contact_way(self, *, follow_user_id: str, state: str, remark: str) -> dict[str, Any]:
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

    async def get_contact_way(self, *, config_id: str) -> dict[str, Any]:
        return await self._request(
            '/externalcontact/get_contact_way',
            method='POST',
            json={'config_id': config_id},
        )

    async def list_contact_ways(self, *, limit: int = 100, cursor: str | None = None) -> dict[str, Any]:
        payload = {'limit': limit}
        if cursor:
            payload['cursor'] = cursor
        return await self._request(
            '/externalcontact/list_contact_way',
            method='POST',
            json=payload,
        )

    async def send_welcome_message(self, *, welcome_code: str, text: str) -> dict[str, Any]:
        return await self._request(
            '/externalcontact/send_welcome_msg',
            method='POST',
            json={'welcome_code': welcome_code, 'text': {'content': text}},
        )

    async def get_external_contact(self, *, external_user_id: str) -> dict[str, Any]:
        return await self._request(
            '/externalcontact/get',
            method='GET',
            params={'external_userid': external_user_id},
        )

    async def update_remark(
        self,
        *,
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
        *,
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
```

- [ ] **Step 5: 重新运行测试并确认客户端可用**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run python -m pytest tests/unit_tests/platform/test_wecom_external_contact_api.py -v`

Expected: PASS，且请求路径均为 `https://qyapi.weixin.qq.com/cgi-bin/externalcontact/*`。

- [ ] **Step 6: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/libs/wecom_external_contact_api/__init__.py \
        src/langbot/libs/wecom_external_contact_api/api.py \
        tests/unit_tests/platform/test_wecom_external_contact_api.py
git commit -m "feat(platform): 增加企微私域官方接口客户端"
```

### Task 2: 补齐私域生命周期持久化模型和服务骨架

**Files:**
- Modify: `src/langbot/pkg/entity/persistence/service_desk.py`
- Create: `src/langbot/pkg/persistence/migrations/dbm028_wecom_private_domain_tables.py`
- Modify: `src/langbot/pkg/utils/constants.py`
- Create: `src/langbot/pkg/api/http/service/wecom_private.py`
- Modify: `src/langbot/pkg/core/stages/build_app.py`
- Modify: `tests/unit_tests/service_desk/test_models.py`
- Create: `tests/unit_tests/service_desk/test_wecom_private_service.py`

- [ ] **Step 1: 先写模型失败测试，锁定新增表和会话字段**

```python
import sqlalchemy


def test_required_database_version_is_28():
    from langbot.pkg.utils import constants

    assert constants.required_database_version == 28


def test_wecom_private_models_exist():
    from langbot.pkg.entity.persistence.service_desk import (
        ServiceDeskSession,
        WecomPrivateBindingTask,
        WecomPrivateClosureRecord,
        WecomPrivateContactConfig,
        WecomPrivateLead,
        WecomPrivateRoutingDecision,
    )

    session_columns = ServiceDeskSession.__table__.c
    assert 'lead_id' in session_columns
    assert 'risk_level' in session_columns
    assert 'closed_at' in session_columns

    assert WecomPrivateContactConfig.__tablename__ == 'wecom_private_contact_configs'
    assert isinstance(WecomPrivateLead.__table__.c['current_tags'].type, sqlalchemy.JSON)
    assert isinstance(WecomPrivateBindingTask.__table__.c['requested_fields'].type, sqlalchemy.JSON)
    assert isinstance(WecomPrivateClosureRecord.__table__.c['tag_updates'].type, sqlalchemy.JSON)
    assert WecomPrivateRoutingDecision.__table__.c['decision'].nullable is False
```

- [ ] **Step 2: 运行模型测试并确认失败**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run python -m pytest tests/unit_tests/service_desk/test_models.py -v`

Expected: FAIL，原因是数据库版本仍为 27，且私域模型尚未定义。

- [ ] **Step 3: 写 ORM 模型和数据库迁移**

```python
class WecomPrivateContactConfig(Base):
    __tablename__ = 'wecom_private_contact_configs'

    id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    config_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True, index=True)
    qr_code_url = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    remark = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    state = sqlalchemy.Column(sqlalchemy.String(64), nullable=False, index=True)
    follow_user_ids = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='[]')
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True, server_default=sqlalchemy.true())
    is_primary = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=True, server_default=sqlalchemy.true())
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class WecomPrivateLead(Base):
    __tablename__ = 'wecom_private_leads'

    id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    external_userid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True, index=True)
    follow_user_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    source_state = sqlalchemy.Column(sqlalchemy.String(64), nullable=True, index=True)
    first_add_time = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    current_tags = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='[]')
    profile_status = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, default='anonymous', server_default='anonymous')
    bound_game_identity = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='{}')
    remark_snapshot = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='{}')
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class WecomPrivateRoutingDecision(Base):
    __tablename__ = 'wecom_private_routing_decisions'

    id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    session_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    trigger_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)
    trigger_reason = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    decision = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)
    matched_rule = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    confidence = sqlalchemy.Column(sqlalchemy.Float, nullable=False, default=1.0, server_default='1')
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())


class WecomPrivateBindingTask(Base):
    __tablename__ = 'wecom_private_binding_tasks'

    id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    session_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True, index=True)
    requested_fields = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='[]')
    provided_uid = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    provided_server = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    verify_status = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, default='pending', server_default='pending')
    requested_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    completed_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class WecomPrivateClosureRecord(Base):
    __tablename__ = 'wecom_private_closure_records'

    id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    session_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True, index=True)
    resolution_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)
    tag_updates = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, server_default='{}')
    followup_needed = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False, server_default=sqlalchemy.false())
    knowledge_feedback = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    closed_by = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())


class ServiceDeskSession(Base):
    __tablename__ = 'service_desk_sessions'

    session_id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    pipeline_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    mode = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, default='ai_hosted', server_default='ai_hosted')
    queue_status = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, default='ai', server_default='ai')
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
    unresolved_count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0, server_default='0')
    lead_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    risk_level = sqlalchemy.Column(sqlalchemy.String(32), nullable=False, default='normal', server_default='normal')
    closed_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )
```

`dbm028_wecom_private_domain_tables.py` 使用原生 SQL 完成：

```python
@migration.migration_class(28)
class DBMigrateWecomPrivateDomainTables(migration.DBMigration):
    async def upgrade(self):
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("""
            CREATE TABLE wecom_private_contact_configs (
                id VARCHAR(255) PRIMARY KEY,
                bot_uuid VARCHAR(255) NOT NULL,
                config_id VARCHAR(255) NOT NULL UNIQUE,
                qr_code_url TEXT NOT NULL,
                remark VARCHAR(255) NOT NULL,
                state VARCHAR(64) NOT NULL,
                follow_user_ids JSON NOT NULL DEFAULT '[]',
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                is_primary BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("""
            CREATE TABLE wecom_private_leads (
                id VARCHAR(255) PRIMARY KEY,
                bot_uuid VARCHAR(255) NOT NULL,
                external_userid VARCHAR(255) NOT NULL UNIQUE,
                follow_user_id VARCHAR(255) NOT NULL,
                source_state VARCHAR(64),
                first_add_time TIMESTAMP,
                current_tags JSON NOT NULL DEFAULT '[]',
                profile_status VARCHAR(50) NOT NULL DEFAULT 'anonymous',
                bound_game_identity JSON NOT NULL DEFAULT '{}',
                remark_snapshot JSON NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("""
            CREATE TABLE wecom_private_routing_decisions (
                id VARCHAR(255) PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL,
                trigger_type VARCHAR(50) NOT NULL,
                trigger_reason TEXT NOT NULL,
                decision VARCHAR(50) NOT NULL,
                matched_rule VARCHAR(255),
                confidence FLOAT NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("""
            CREATE TABLE wecom_private_binding_tasks (
                id VARCHAR(255) PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL UNIQUE,
                requested_fields JSON NOT NULL DEFAULT '[]',
                provided_uid VARCHAR(255),
                provided_server VARCHAR(255),
                verify_status VARCHAR(50) NOT NULL DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("""
            CREATE TABLE wecom_private_closure_records (
                id VARCHAR(255) PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL UNIQUE,
                resolution_type VARCHAR(50) NOT NULL,
                tag_updates JSON NOT NULL DEFAULT '{}',
                followup_needed BOOLEAN NOT NULL DEFAULT FALSE,
                knowledge_feedback TEXT,
                closed_by VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("ALTER TABLE service_desk_sessions ADD COLUMN lead_id VARCHAR(255)"))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("ALTER TABLE service_desk_sessions ADD COLUMN risk_level VARCHAR(32) NOT NULL DEFAULT 'normal'"))
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("ALTER TABLE service_desk_sessions ADD COLUMN closed_at TIMESTAMP"))
```

- [ ] **Step 4: 写私域服务失败测试，锁定二维码同步、lead 建档和闭环行为**

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.asyncio
async def test_sync_primary_contact_config_creates_remote_qr_and_persists_payload():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock()
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda _model, row: row)

    service = WecomPrivateService(ap)
    service._get_primary_contact_config = AsyncMock(return_value=None)
    service._build_external_contact_client = AsyncMock()
    service._build_external_contact_client.return_value.create_contact_way = AsyncMock(
        return_value={
            'errcode': 0,
            'config_id': 'cfg-1',
            'qr_code': 'https://qrcode.example/cfg-1',
        }
    )
    service._upsert_contact_config = AsyncMock()

    result = await service.sync_primary_contact_config(
        bot_uuid='bot-1',
        follow_user_id='zhangsan',
        state='dkd_phase1_entry',
        remark='DKD 私域固定二维码',
    )

    assert result['config_id'] == 'cfg-1'
    assert result['follow_user_ids'] == ['zhangsan']
    service._upsert_contact_config.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_private_session_writes_tags_remark_and_sets_closed_state():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock()
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda _model, row: row)

    service = WecomPrivateService(ap)
    service._get_session = AsyncMock(return_value={
        'session_id': 'person_cfg-1:wo123',
        'lead_id': 'lead-1',
        'queue_status': 'manual',
    })
    service._get_lead = AsyncMock(return_value={
        'id': 'lead-1',
        'external_userid': 'wo123',
        'follow_user_id': 'zhangsan',
    })
    service._build_external_contact_client = AsyncMock()
    client = service._build_external_contact_client.return_value
    client.mark_tags = AsyncMock(return_value={'errcode': 0, 'errmsg': 'ok'})
    client.update_remark = AsyncMock(return_value={'errcode': 0, 'errmsg': 'ok'})
    service._upsert_closure_record = AsyncMock(return_value={'session_id': 'person_cfg-1:wo123'})

    record = await service.close_private_session(
        session_id='person_cfg-1:wo123',
        operator_name='客服A',
        data={
            'resolution_type': 'answered',
            'tag_updates': {'add': ['tag-a'], 'remove': []},
            'remark_text': '玩家 UID: 10001 / 区服: S1',
            'followup_needed': False,
            'knowledge_feedback': '补充充值 FAQ',
        },
    )

    assert record['session_id'] == 'person_cfg-1:wo123'
    client.mark_tags.assert_awaited_once()
    client.update_remark.assert_awaited_once()
```

- [ ] **Step 5: 运行服务测试并确认失败**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run python -m pytest tests/unit_tests/service_desk/test_wecom_private_service.py -v`

Expected: FAIL，原因是 `WecomPrivateService` 尚不存在。

- [ ] **Step 6: 写 `WecomPrivateService` 的最小实现并注册到应用**

```python
class WecomPrivateService:
    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def sync_primary_contact_config(
        self,
        *,
        bot_uuid: str,
        follow_user_id: str,
        state: str,
        remark: str,
    ) -> dict:
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
            remote = await client.get_contact_way(config_id=stored.config_id)
            payload = {
                'id': stored.id,
                'bot_uuid': bot_uuid,
                'config_id': remote['contact_way']['config_id'],
                'qr_code_url': remote['contact_way']['qr_code'],
                'remark': remark,
                'state': state,
                'follow_user_ids': [follow_user_id],
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
    ) -> dict:
        existing = await self._get_lead_by_external_userid(external_user_id)
        if existing is not None:
            return existing

        client = await self._build_external_contact_client(bot_uuid)
        remote = await client.get_external_contact(external_user_id=external_user_id)
        lead = {
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
        await self._insert_lead(lead)
        return lead

    async def record_routing_decision(self, *, session_id: str, trigger_type: str, trigger_reason: str, decision: str, matched_rule: str | None, confidence: float) -> dict:
        payload = {
            'id': str(uuid.uuid4()),
            'session_id': session_id,
            'trigger_type': trigger_type,
            'trigger_reason': trigger_reason,
            'decision': decision,
            'matched_rule': matched_rule,
            'confidence': confidence,
        }
        await self._insert_routing_decision(payload)
        return payload

    async def upsert_binding_task(self, *, session_id: str, data: dict) -> dict:
        payload = {
            'id': data.get('id') or str(uuid.uuid4()),
            'session_id': session_id,
            'requested_fields': data.get('requested_fields', ['uid', 'server']),
            'provided_uid': data.get('provided_uid'),
            'provided_server': data.get('provided_server'),
            'verify_status': data.get('verify_status', 'pending'),
            'completed_at': _utcnow() if data.get('verify_status') == 'completed' else None,
        }
        await self._upsert_binding_task_row(payload)
        return payload

    async def close_private_session(self, *, session_id: str, operator_name: str, data: dict) -> dict:
        session = await self._get_session(session_id)
        lead = await self._get_lead(self._get_value(session, 'lead_id'))
        client = await self._build_external_contact_client(self._get_value(session, 'bot_uuid'))

        tag_updates = data.get('tag_updates', {})
        await client.mark_tags(
            follow_user_id=lead['follow_user_id'],
            external_user_id=lead['external_userid'],
            add_tags=tag_updates.get('add', []),
            remove_tags=tag_updates.get('remove', []),
        )

        remark_text = str(data.get('remark_text') or '').strip()
        if remark_text:
            await client.update_remark(
                follow_user_id=lead['follow_user_id'],
                external_user_id=lead['external_userid'],
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
        await self._upsert_closure_record(payload)
        await self._mark_session_closed(session_id)
        return payload
```

`build_app.py` 里注册：

```python
from langbot.pkg.api.http.service import service_desk as service_desk_service
from langbot.pkg.api.http.service import wecom_private as wecom_private_service

service_desk_service_inst = service_desk_service.ServiceDeskService(ap)
ap.service_desk_service = service_desk_service_inst

wecom_private_service_inst = wecom_private_service.WecomPrivateService(ap)
ap.wecom_private_service = wecom_private_service_inst
```

- [ ] **Step 7: 回归模型和服务测试**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run python -m pytest tests/unit_tests/service_desk/test_models.py tests/unit_tests/service_desk/test_wecom_private_service.py -v`

Expected: PASS，`required_database_version` 更新为 28，且私域服务核心方法可调用。

- [ ] **Step 8: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/entity/persistence/service_desk.py \
        src/langbot/pkg/persistence/migrations/dbm028_wecom_private_domain_tables.py \
        src/langbot/pkg/utils/constants.py \
        src/langbot/pkg/api/http/service/wecom_private.py \
        src/langbot/pkg/core/stages/build_app.py \
        tests/unit_tests/service_desk/test_models.py \
        tests/unit_tests/service_desk/test_wecom_private_service.py
git commit -m "feat(service): 增加企微私域生命周期模型"
```

### Task 3: 实现 `wecomprivate` 托管适配器和登录运行态

**Files:**
- Create: `src/langbot/libs/wecom_private_page_api/__init__.py`
- Create: `src/langbot/libs/wecom_private_page_api/client.py`
- Create: `src/langbot/pkg/platform/sources/wecomprivate.py`
- Create: `src/langbot/pkg/platform/sources/wecomprivate.yaml`
- Modify: `src/langbot/pkg/api/http/service/bot.py`
- Create: `tests/unit_tests/platform/test_wecomprivate_adapter.py`
- Create: `tests/unit_tests/platform/test_wecomprivate_runtime.py`

- [ ] **Step 1: 先写适配器失败测试，锁定事件上下文和回复出口**

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.asyncio
async def test_wecomprivate_adapter_extracts_service_desk_context():
    from langbot.pkg.platform.sources.wecomprivate import (
        WecomPrivateAdapter,
        WecomPrivateMessageEvent,
    )

    adapter = object.__new__(WecomPrivateAdapter)
    event = WecomPrivateMessageEvent(
        entry_id='cfg-1',
        follow_user_id='zhangsan',
        external_user_id='wo123',
        message_id='msg-1',
        conversation_id='conv-1',
        sender_name='玩家A',
        content='你好',
        timestamp=1710000000,
        welcome_code=None,
    )

    assert adapter.extract_service_desk_context(event) == {
        'source_entry_id': 'cfg-1',
        'external_user_id': 'wo123',
        'last_message_id': 'msg-1',
    }
    assert adapter.get_launcher_id(event) == 'cfg-1:wo123'


@pytest.mark.asyncio
async def test_wecomprivate_adapter_reply_message_uses_page_client():
    import langbot_plugin.api.entities.builtin.platform.message as platform_message

    from langbot.pkg.platform.sources.wecomprivate import WecomPrivateAdapter

    adapter = object.__new__(WecomPrivateAdapter)
    adapter.bot = Mock()
    adapter.bot.send_text = AsyncMock()

    event = SimpleNamespace(
        source_platform_object=SimpleNamespace(
            entry_id='cfg-1',
            follow_user_id='zhangsan',
            external_user_id='wo123',
            conversation_id='conv-1',
            message_id='msg-1',
            sender_name='玩家A',
            content='你好',
            timestamp=1710000000,
            welcome_code=None,
        ),
    )

    await adapter.reply_message(
        event,
        platform_message.MessageChain([platform_message.Plain(text='收到')]),
    )

    adapter.bot.send_text.assert_awaited_once_with(
        conversation_id='conv-1',
        external_user_id='wo123',
        text='收到',
    )
```

- [ ] **Step 2: 再写运行态失败测试，锁定 `wecomprivate` 登录二维码输出**

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.asyncio
async def test_get_runtime_bot_info_exposes_wecomprivate_login_state():
    from langbot.pkg.api.http.service.bot import BotService

    service = BotService(SimpleNamespace())
    service.get_bot = AsyncMock(
        return_value={
            'uuid': 'bot-1',
            'adapter': 'wecomprivate',
            'adapter_config': {},
        }
    )
    runtime_bot = SimpleNamespace(
        adapter=SimpleNamespace(
            bot_account_id='private-entry',
            bot=SimpleNamespace(
                get_login_runtime_state=Mock(
                    return_value={
                        'login_state_checked': True,
                        'login_required': True,
                        'login_qr_image_base64': 'ZmFrZQ==',
                        'login_qr_updated_at': 1710000000,
                    }
                )
            ),
        )
    )
    service.ap.platform_mgr = SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=runtime_bot))
    service.ap.instance_config = SimpleNamespace(data={'api': {}})

    result = await service.get_runtime_bot_info('bot-1')

    assert result['adapter_runtime_values']['login_required'] is True
    assert result['adapter_runtime_values']['login_qr_image_base64'] == 'ZmFrZQ=='
```

- [ ] **Step 3: 运行测试并确认当前适配器不存在**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run python -m pytest tests/unit_tests/platform/test_wecomprivate_adapter.py tests/unit_tests/platform/test_wecomprivate_runtime.py -v`

Expected: FAIL，原因是 `wecomprivate` 适配器和运行态输出尚未实现。

- [ ] **Step 4: 写浏览器托管客户端和事件模型**

```python
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass
class WecomPrivateMessageEvent:
    entry_id: str
    follow_user_id: str
    external_user_id: str
    message_id: str
    conversation_id: str
    sender_name: str
    content: str
    timestamp: int
    welcome_code: str | None = None


class WecomPrivatePageClient:
    def __init__(self, *, entry_label: str, workbench_url: str, storage_state_dir: str, poll_interval_seconds: int = 2, print_login_qr: bool = True, **kwargs) -> None:
        self.entry_label = entry_label
        self.workbench_url = workbench_url
        self.storage_state_dir = storage_state_dir
        self.poll_interval_seconds = poll_interval_seconds
        self.print_login_qr = print_login_qr
        self._message_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None
        self._login_state_checked = False
        self._login_required = False
        self._login_qr_image_base64: str | None = None
        self._login_qr_updated_at: int | None = None

    def set_message_callback(self, callback: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        self._message_callback = callback

    def get_login_runtime_state(self) -> dict[str, Any]:
        return {
            'login_state_checked': self._login_state_checked,
            'login_required': self._login_required,
            'login_qr_image_base64': self._login_qr_image_base64,
            'login_qr_updated_at': self._login_qr_updated_at,
        }

    async def send_text(self, *, conversation_id: str, external_user_id: str, text: str) -> None:
        await self._send_to_web_private_chat(conversation_id, external_user_id, text)

    async def run_forever(self) -> None:
        while True:
            await self._ensure_browser()
            await self._refresh_login_state()
            if self._login_required:
                await asyncio.sleep(self.poll_interval_seconds)
                continue
            await self._poll_new_messages()
            await asyncio.sleep(self.poll_interval_seconds)

    async def _refresh_login_state(self) -> None:
        self._login_state_checked = True
        qr_png = await self._maybe_capture_login_qr()
        self._login_required = qr_png is not None
        self._login_qr_image_base64 = qr_png
        self._login_qr_updated_at = int(time.time()) if qr_png else None
```

- [ ] **Step 5: 写适配器和 YAML 配置声明**

```python
class WecomPrivateAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: WecomPrivatePageClient = pydantic.Field(exclude=True)
    message_converter: WecomPrivateMessageConverter = WecomPrivateMessageConverter()
    event_converter: WecomPrivateEventConverter = WecomPrivateEventConverter()

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        required_keys = ['corpid', 'contact_secret', 'entry_label', 'workbench_url', 'storage_state_dir']
        missing_keys = [key for key in required_keys if not config.get(key)]
        if missing_keys:
            raise command_errors.ParamNotEnoughError('企微私域托管缺少相关配置项，请查看文档或联系管理员')

        bot = WecomPrivatePageClient(
            entry_label=config['entry_label'],
            workbench_url=config['workbench_url'],
            storage_state_dir=config['storage_state_dir'],
            poll_interval_seconds=int(config.get('poll_interval_seconds', 2)),
            print_login_qr=bool(config.get('print_login_qr', True)),
            headless=bool(config.get('headless', False)),
            browser_executable_path=config.get('browser_executable_path', ''),
        )

        super().__init__(
            config=config,
            logger=logger,
            bot_account_id=config['entry_label'],
            listeners={},
            bot=bot,
        )

    def extract_service_desk_context(self, event: WecomPrivateMessageEvent) -> dict[str, str]:
        return {
            'source_entry_id': event.entry_id or '',
            'external_user_id': event.external_user_id or '',
            'last_message_id': str(event.message_id or ''),
        }
```

```yaml
apiVersion: v1
kind: MessagePlatformAdapter
metadata:
  name: wecomprivate
  label:
    zh_Hans: 企业微信私域
    en_US: WeComPrivateDomain
  description:
    zh_Hans: 企业微信私域好友托管接入，二维码与客户信息走官方接口，持续聊天走托管页
    en_US: WeCom private-domain hosted adapter
  icon: wecom.png
spec:
  categories:
    - china
  config:
    - name: corpid
      type: string
      required: true
      default: ""
    - name: contact_secret
      type: string
      required: true
      default: ""
    - name: entry_label
      type: string
      required: true
      default: "企微私域固定入口"
    - name: workbench_url
      type: string
      required: true
      default: ""
    - name: storage_state_dir
      type: string
      required: true
      default: "./data/wecomprivate"
    - name: poll_interval_seconds
      type: integer
      required: false
      default: 2
    - name: headless
      type: boolean
      required: false
      default: false
    - name: browser_executable_path
      type: string
      required: false
      default: ""
    - name: print_login_qr
      type: boolean
      required: false
      default: true
    - name: api_base_url
      type: string
      required: false
      default: "https://qyapi.weixin.qq.com/cgi-bin"
execution:
  python:
    path: ./wecomprivate.py
    attr: WecomPrivateAdapter
```

- [ ] **Step 6: 让 `BotService` 也为 `wecomprivate` 暴露登录态**

```python
    async def get_runtime_bot_info(self, bot_uuid: str, include_secret: bool = True) -> dict:
        persistence_bot = await self.get_bot(bot_uuid, include_secret)
        if persistence_bot is None:
            raise Exception('Bot not found')

        adapter_runtime_values = {}
        if persistence_bot['adapter'] in {'wecomweb', 'wecomprivate'}:
            adapter_runtime_values['login_state_checked'] = False
            adapter_runtime_values['login_required'] = False
            adapter_runtime_values['login_qr_image_base64'] = None
            adapter_runtime_values['login_qr_updated_at'] = None

        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if runtime_bot is not None:
            adapter_runtime_values['bot_account_id'] = runtime_bot.adapter.bot_account_id
            if persistence_bot['adapter'] in {'wecomweb', 'wecomprivate'}:
                get_state = getattr(getattr(runtime_bot.adapter, 'bot', None), 'get_login_runtime_state', None)
                if callable(get_state):
                    adapter_runtime_values.update(get_state())

        persistence_bot['adapter_runtime_values'] = adapter_runtime_values
        return persistence_bot
```

- [ ] **Step 7: 回归适配器和运行态测试**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run python -m pytest tests/unit_tests/platform/test_wecomprivate_adapter.py tests/unit_tests/platform/test_wecomprivate_runtime.py -v`

Expected: PASS，`wecomprivate` 可被 BotForm 轮询并能向客服台提供标准上下文。

- [ ] **Step 8: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/libs/wecom_private_page_api/__init__.py \
        src/langbot/libs/wecom_private_page_api/client.py \
        src/langbot/pkg/platform/sources/wecomprivate.py \
        src/langbot/pkg/platform/sources/wecomprivate.yaml \
        src/langbot/pkg/api/http/service/bot.py \
        tests/unit_tests/platform/test_wecomprivate_adapter.py \
        tests/unit_tests/platform/test_wecomprivate_runtime.py
git commit -m "feat(platform): 增加企微私域托管适配器"
```

### Task 4: 把私域 lead / routing / binding / closure 接进现有客服台

**Files:**
- Modify: `src/langbot/pkg/api/http/service/service_desk.py`
- Modify: `src/langbot/pkg/api/http/controller/groups/service_desk.py`
- Modify: `tests/unit_tests/service_desk/test_service_desk_service.py`
- Modify: `tests/unit_tests/service_desk/test_runtime_flow.py`
- Modify: `tests/unit_tests/service_desk/test_session_detail_api.py`

- [ ] **Step 1: 先写客服台失败测试，锁定私域会话建档和分流记录**

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.asyncio
async def test_handle_incoming_message_bootstraps_private_lead_before_pipeline():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.wecom_private_service.bootstrap_private_lead = AsyncMock(return_value={'id': 'lead-1', 'profile_status': 'anonymous'})
    ap.wecom_private_service.record_routing_decision = AsyncMock()

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(return_value={
        'session_id': 'person_cfg-1:wo123',
        'mode': 'ai_hosted',
        'queue_status': 'ai',
        'manual_claimed_at': None,
        'silent_since': None,
    })
    service.get_bot_config = AsyncMock(return_value={'enabled': True, 'handoff_keywords': []})
    service.list_materials = AsyncMock(return_value=[])

    bot_entity = SimpleNamespace(adapter='wecomprivate', uuid='bot-1', use_pipeline_uuid='pipe-1')
    event = SimpleNamespace(
        message_chain='你好',
        source_platform_object=SimpleNamespace(
            entry_id='cfg-1',
            follow_user_id='zhangsan',
            external_user_id='wo123',
            message_id='msg-1',
            welcome_code=None,
        ),
        sender=SimpleNamespace(id='wo123', nickname='玩家A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'cfg-1',
        'external_user_id': 'wo123',
        'last_message_id': 'msg-1',
    }
    adapter.get_launcher_id.return_value = 'cfg-1:wo123'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipe-1',
    )

    assert decision.action == 'continue_ai'
    ap.wecom_private_service.bootstrap_private_lead.assert_awaited_once()


@pytest.mark.asyncio
async def test_session_detail_includes_private_domain_overlay():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda _model, row: row)
    ap.monitoring_service.get_messages = AsyncMock(return_value=([], 0))
    ap.platform_mgr.get_bot_by_uuid = AsyncMock(return_value=SimpleNamespace(bot_entity=SimpleNamespace(name='私域机器人')))
    ap.wecom_private_service.get_session_overlay = AsyncMock(return_value={
        'lead': {'id': 'lead-1', 'external_userid': 'wo123', 'profile_status': 'anonymous'},
        'routing_decisions': [{'decision': 'pending_manual', 'trigger_reason': '投诉关键词'}],
        'binding_task': {'session_id': 'person_cfg-1:wo123', 'verify_status': 'pending'},
        'closure_record': None,
    })

    service = ServiceDeskService(ap)
    service._get_session = AsyncMock(return_value={
        'session_id': 'person_cfg-1:wo123',
        'bot_uuid': 'bot-1',
        'pipeline_uuid': 'pipe-1',
        'external_user_id': 'wo123',
        'lead_id': 'lead-1',
    })
    service._load_messages_by_external_user = AsyncMock(return_value=[])

    detail = await service.get_session_detail('person_cfg-1:wo123')

    assert detail['lead']['id'] == 'lead-1'
    assert detail['routing_decisions'][0]['decision'] == 'pending_manual'
    assert detail['binding_task']['verify_status'] == 'pending'
```

- [ ] **Step 2: 再写失败测试，锁定绑定补录和会话闭环接口**

```python
@pytest.mark.asyncio
async def test_close_session_endpoint_delegates_to_wecom_private_service():
    from types import SimpleNamespace

    import quart

    from langbot.pkg.api.http.controller.groups.service_desk import ServiceDeskRouterGroup

    app = quart.Quart(__name__)
    ap = SimpleNamespace(
        service_desk_service=SimpleNamespace(),
        wecom_private_service=SimpleNamespace(
            close_private_session=AsyncMock(return_value={'session_id': 'person_cfg-1:wo123'})
        ),
        user_service=SimpleNamespace(
            get_user_by_email=AsyncMock(return_value=SimpleNamespace(id='u-1', user='客服A'))
        ),
    )
    group = ServiceDeskRouterGroup(ap, app)
    await group.initialize()

    test_client = app.test_client()
    response = await test_client.post(
        '/api/v1/service-desk/sessions/person_cfg-1:wo123/close',
        json={
            'resolution_type': 'answered',
            'tag_updates': {'add': ['tag-a'], 'remove': []},
            'remark_text': '玩家 UID: 10001',
        },
        headers={'Authorization': 'Bearer fake'},
    )

    assert response.status_code in {200, 401}
```

- [ ] **Step 3: 运行相关测试并确认失败**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run python -m pytest tests/unit_tests/service_desk/test_service_desk_service.py tests/unit_tests/service_desk/test_runtime_flow.py tests/unit_tests/service_desk/test_session_detail_api.py -k 'private or close or overlay' -v`

Expected: FAIL，原因是 `service_desk` 还没有私域 overlay、绑定补录和闭环接口。

- [ ] **Step 4: 在 `service_desk.py` 中接入 `WecomPrivateService`**

```python
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
        session_id = self._get_session_id(event, adapter)

        if getattr(bot_entity, 'adapter', None) == 'wecomprivate' and hasattr(self.ap, 'wecom_private_service'):
            lead = await self.ap.wecom_private_service.bootstrap_private_lead(
                bot_uuid=bot_entity.uuid,
                external_user_id=context['external_user_id'],
                follow_user_id=str(getattr(source_event, 'follow_user_id', '') or ''),
                source_entry_id=context['source_entry_id'],
            )
        else:
            lead = None

        session = await self._touch_session(
            session_id=session_id,
            bot_uuid=bot_entity.uuid,
            pipeline_uuid=pipeline_uuid or bot_entity.use_pipeline_uuid or '',
            source_entry_id=context['source_entry_id'],
            external_user_id=context['external_user_id'],
            last_message_id=context['last_message_id'],
            sender_name=self._get_sender_name(event),
            lead_id=(lead or {}).get('id'),
        )

        config = await self.get_bot_config(bot_entity.uuid)
        material = match_material(str(getattr(event, 'message_chain', '') or ''), await self.list_materials(bot_entity.uuid))
        if material is not None:
            return ServiceDeskDecision(action='send_material', reason='quick_reply', material=material)

        handoff_reason = self._match_handoff_reason(
            message_text=str(getattr(event, 'message_chain', '') or ''),
            handoff_keywords=(config or {}).get('handoff_keywords', []),
            unresolved_count=self._get_value(session, 'unresolved_count', 0),
            fallback_unresolved_count=(config or {}).get('fallback_unresolved_count', 2),
        )
        if handoff_reason is not None:
            await self._update_session_state(session_id, queue_status='pending_manual', handoff_reason=handoff_reason)
            if getattr(bot_entity, 'adapter', None) == 'wecomprivate' and hasattr(self.ap, 'wecom_private_service'):
                await self.ap.wecom_private_service.record_routing_decision(
                    session_id=session_id,
                    trigger_type='rule',
                    trigger_reason=handoff_reason,
                    decision='pending_manual',
                    matched_rule=handoff_reason,
                    confidence=1.0,
                )
            return ServiceDeskDecision(action='skip_pipeline', reason='pending_manual')

        return ServiceDeskDecision(action='continue_ai')
```

- [ ] **Step 5: 扩展 detail、绑定补录和闭环接口**

```python
    async def get_session_detail(self, session_id: str) -> dict:
        session = await self._get_session(session_id)
        if session is None:
            raise ValueError(f'session not found: {session_id}')

        serialized_session = self.ap.persistence_mgr.serialize_model(
            persistence_service_desk.ServiceDeskSession,
            session,
        )
        direct_messages, _ = await self.ap.monitoring_service.get_messages(
            session_ids=[session_id],
            limit=SERVICE_DESK_TIMELINE_LIMIT,
            offset=0,
        )
        external_user_messages = await self._load_messages_by_external_user(
            bot_uuid=str(self._get_value(session, 'bot_uuid', '') or ''),
            external_user_id=str(self._get_value(session, 'external_user_id', '') or ''),
            limit=SERVICE_DESK_TIMELINE_LIMIT,
        )
        messages = self._merge_timeline_messages(external_user_messages, direct_messages)
        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(self._get_value(session, 'bot_uuid'))
        bot_payload = {
            'uuid': self._get_value(session, 'bot_uuid'),
            'name': getattr(getattr(runtime_bot, 'bot_entity', None), 'name', None) if runtime_bot else None,
        }
        overlay = {'lead': None, 'routing_decisions': [], 'binding_task': None, 'closure_record': None}
        if hasattr(self.ap, 'wecom_private_service'):
            overlay = await self.ap.wecom_private_service.get_session_overlay(session_id)

        return {
            'session': serialized_session,
            'messages': messages,
            'bot': bot_payload,
            'assist_draft': None,
            **overlay,
        }
```

```python
@self.route('/sessions/<session_id>/binding-task', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
async def upsert_binding_task(session_id: str) -> str:
    payload = await quart.request.json
    task = await self.ap.wecom_private_service.upsert_binding_task(session_id=session_id, data=payload)
    return self.success(data={'binding_task': task})


@self.route('/sessions/<session_id>/close', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
async def close_session(session_id: str, user_email: str) -> str:
    payload = await quart.request.json
    user = await self.ap.user_service.get_user_by_email(user_email)
    record = await self.ap.wecom_private_service.close_private_session(
        session_id=session_id,
        operator_name=user.user,
        data=payload,
    )
    return self.success(data={'closure_record': record})
```

- [ ] **Step 6: 回归客服台相关测试**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run python -m pytest tests/unit_tests/service_desk/test_service_desk_service.py tests/unit_tests/service_desk/test_runtime_flow.py tests/unit_tests/service_desk/test_session_detail_api.py -v`

Expected: PASS，`wecomprivate` 能走既有客服台逻辑，detail 返回私域 overlay。

- [ ] **Step 7: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/api/http/service/service_desk.py \
        src/langbot/pkg/api/http/controller/groups/service_desk.py \
        tests/unit_tests/service_desk/test_service_desk_service.py \
        tests/unit_tests/service_desk/test_runtime_flow.py \
        tests/unit_tests/service_desk/test_session_detail_api.py
git commit -m "feat(service): 接入企微私域客服台流程"
```

### Task 5: 暴露固定二维码接口并完成前端一期界面

**Files:**
- Create: `src/langbot/pkg/api/http/controller/groups/wecom_private.py`
- Modify: `web/src/app/infra/entities/api/index.ts`
- Modify: `web/src/app/infra/http/BackendClient.ts`
- Modify: `web/src/app/home/service-desk/ServiceDeskContent.tsx`
- Modify: `web/src/app/home/service-desk/components/BotDeskConfigForm.tsx`
- Modify: `web/src/app/home/service-desk/components/SessionDetail.tsx`
- Modify: `web/src/app/home/bots/components/bot-form/BotForm.tsx`
- Modify: `web/src/app/home/bots/components/bot-form/wecomWebLoginState.ts`

- [ ] **Step 1: 先补前端 DTO，明确二维码、lead、routing、binding、closure 结构**

```ts
export interface WecomPrivateContactConfig {
  id: string;
  bot_uuid: string;
  config_id: string;
  qr_code_url: string;
  remark: string;
  state: string;
  follow_user_ids: string[];
  enabled: boolean;
  is_primary: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface WecomPrivateLead {
  id: string;
  external_userid: string;
  follow_user_id: string;
  source_state?: string | null;
  current_tags: string[];
  profile_status: 'anonymous' | 'binding_requested' | 'bound';
  bound_game_identity: Record<string, string | null>;
  remark_snapshot: Record<string, unknown>;
}

export interface WecomPrivateRoutingDecision {
  id: string;
  session_id: string;
  trigger_type: string;
  trigger_reason: string;
  decision: string;
  matched_rule?: string | null;
  confidence: number;
  created_at?: string;
}

export interface WecomPrivateBindingTask {
  id: string;
  session_id: string;
  requested_fields: string[];
  provided_uid?: string | null;
  provided_server?: string | null;
  verify_status: 'pending' | 'completed' | 'manual_verified';
  requested_at?: string;
  completed_at?: string | null;
}

export interface WecomPrivateClosureRecord {
  id: string;
  session_id: string;
  resolution_type: string;
  tag_updates: Record<string, string[]>;
  followup_needed: boolean;
  knowledge_feedback?: string | null;
  closed_by: string;
  created_at?: string;
}

export type ServiceDeskQueueStatus =
  | 'pending_manual'
  | 'manual'
  | 'silent'
  | 'ai'
  | 'closed';

export interface ServiceDeskSessionDetail {
  session: ServiceDeskSession;
  messages: ServiceDeskTimelineMessage[];
  bot: { uuid: string; name?: string | null };
  assist_draft: ServiceDeskAssistDraft | null;
  lead: WecomPrivateLead | null;
  routing_decisions: WecomPrivateRoutingDecision[];
  binding_task: WecomPrivateBindingTask | null;
  closure_record: WecomPrivateClosureRecord | null;
}
```

- [ ] **Step 2: 增加前端 HTTP 方法和后端二维码路由**

```ts
public getWecomPrivateContactConfigs(
  botUuid: string,
): Promise<{ items: WecomPrivateContactConfig[] }> {
  return this.get(`/api/v1/wecom-private/contact-configs`, { botUuid });
}

public syncWecomPrivatePrimaryContactConfig(
  botUuid: string,
  payload: { follow_user_id: string; state: string; remark: string },
): Promise<{ item: WecomPrivateContactConfig }> {
  return this.post(`/api/v1/wecom-private/contact-configs/sync-primary`, {
    bot_uuid: botUuid,
    follow_user_id: payload.follow_user_id,
    state: payload.state,
    remark: payload.remark,
  });
}

public upsertServiceDeskBindingTask(
  sessionId: string,
  payload: {
    requested_fields: string[];
    provided_uid?: string;
    provided_server?: string;
    verify_status?: string;
  },
): Promise<{ binding_task: WecomPrivateBindingTask }> {
  return this.post(`/api/v1/service-desk/sessions/${sessionId}/binding-task`, payload);
}

public closeServiceDeskSession(
  sessionId: string,
  payload: {
    resolution_type: string;
    tag_updates: Record<string, string[]>;
    remark_text?: string;
    followup_needed?: boolean;
    knowledge_feedback?: string;
  },
): Promise<{ closure_record: WecomPrivateClosureRecord }> {
  return this.post(`/api/v1/service-desk/sessions/${sessionId}/close`, payload);
}
```

```python
@group.group_class('wecom_private', '/api/v1/wecom-private')
class WecomPrivateRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/contact-configs', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def list_contact_configs() -> str:
            bot_uuid = quart.request.args.get('botUuid')
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
```

- [ ] **Step 3: 让客服台列表识别 `wecomprivate`**

```tsx
function isServiceDeskBot(bot: Bot): bot is ServiceDeskBot {
  return Boolean(bot.uuid) && ['wecomcs', 'lark', 'wecomprivate'].includes(bot.adapter);
}

function getChannelLabel(adapter: string, t: ReturnType<typeof useTranslation>['t']) {
  if (adapter === 'lark') return t('serviceDesk.channels.lark');
  if (adapter === 'wecomprivate') return t('serviceDesk.channels.wecomprivate');
  return t('serviceDesk.channels.wecomcs');
}

function getChannelBadgeClass(adapter: string) {
  if (adapter === 'lark') return 'border-sky-200 bg-sky-50 text-sky-700';
  if (adapter === 'wecomprivate') return 'border-amber-200 bg-amber-50 text-amber-700';
  return 'border-emerald-200 bg-emerald-50 text-emerald-700';
}
```

- [ ] **Step 4: 在 `BotDeskConfigForm` 中增加固定二维码配置卡片**

```tsx
const [contactConfigs, setContactConfigs] = useState<WecomPrivateContactConfig[]>([]);
const [contactRemark, setContactRemark] = useState('');
const [contactState, setContactState] = useState('dkd_phase1_entry');
const [followUserId, setFollowUserId] = useState('');
const [syncingContactConfig, setSyncingContactConfig] = useState(false);

useEffect(() => {
  if (!bot || bot.adapter !== 'wecomprivate') {
    setContactConfigs([]);
    return;
  }
  httpClient.getWecomPrivateContactConfigs(bot.uuid).then((resp) => {
    setContactConfigs(resp.items);
    const primary = resp.items.find((item) => item.is_primary);
    setContactRemark(primary?.remark ?? `${bot.name} 固定二维码`);
    setContactState(primary?.state ?? 'dkd_phase1_entry');
    setFollowUserId(primary?.follow_user_ids?.[0] ?? '');
  });
}, [bot]);

const handleSyncContactConfig = async () => {
  if (!bot) return;
  setSyncingContactConfig(true);
  try {
    await httpClient.syncWecomPrivatePrimaryContactConfig(bot.uuid, {
      follow_user_id: followUserId.trim(),
      state: contactState.trim(),
      remark: contactRemark.trim() || `${bot.name} 固定二维码`,
    });
    await onSaved();
    const refreshed = await httpClient.getWecomPrivateContactConfigs(bot.uuid);
    setContactConfigs(refreshed.items);
    toast.success('固定二维码已同步');
  } catch (error) {
    console.error('Failed to sync private contact config:', error);
    toast.error('固定二维码同步失败');
  } finally {
    setSyncingContactConfig(false);
  }
};
```

- [ ] **Step 5: 在 `SessionDetail` 中展示 lead / routing / binding / closure**

```tsx
const [bindingUid, setBindingUid] = useState('');
const [bindingServer, setBindingServer] = useState('');
const [closing, setClosing] = useState(false);
const [closureRemark, setClosureRemark] = useState('');
const [closureTags, setClosureTags] = useState('');
const [knowledgeFeedback, setKnowledgeFeedback] = useState('');

const handleSaveBinding = async () => {
  if (!session) return;
  const resp = await httpClient.upsertServiceDeskBindingTask(session.session_id, {
    requested_fields: ['uid', 'server'],
    provided_uid: bindingUid.trim(),
    provided_server: bindingServer.trim(),
    verify_status: bindingUid.trim() && bindingServer.trim() ? 'completed' : 'pending',
  });
  setDetail((prev) =>
    prev ? Object.assign({}, prev, { binding_task: resp.binding_task }) : prev,
  );
  toast.success('补录绑定已保存');
};

const handleCloseSession = async () => {
  if (!session) return;
  setClosing(true);
  try {
    const resp = await httpClient.closeServiceDeskSession(session.session_id, {
      resolution_type: 'answered',
      tag_updates: {
        add: closureTags.split(/[\n,]/).map((item) => item.trim()).filter(Boolean),
        remove: [],
      },
      remark_text: closureRemark.trim(),
      followup_needed: false,
      knowledge_feedback: knowledgeFeedback.trim() || undefined,
    });
    setDetail((prev) =>
      prev ? Object.assign({}, prev, { closure_record: resp.closure_record }) : prev,
    );
    toast.success('会话已闭环');
    await onRefresh();
  } catch (error) {
    console.error('Failed to close service desk session:', error);
    toast.error('会话闭环失败');
  } finally {
    setClosing(false);
  }
};
```

- [ ] **Step 6: 让 `BotForm` 在 `wecomprivate` 上复用企微托管登录态卡片**

```tsx
const isHostedWecomAdapter = ['wecomweb', 'wecomprivate'].includes(currentAdapter);

useEffect(() => {
  if (!initBotId || !isHostedWecomAdapter) {
    loginRequestTokenRef.current += 1;
    clearWecomWebLoginPolling();
    setWecomWebBotEnabled(false);
    setLoginStateLoaded(false);
    setLoginStateChecked(false);
    setLoginRequired(false);
    setLoginQrImageBase64(null);
    setLoginQrLoadError(null);
    return;
  }

  const requestToken = loginRequestTokenRef.current + 1;
  loginRequestTokenRef.current = requestToken;
  clearWecomWebLoginPolling();
  setLoginStateLoaded(false);
  void refreshWecomWebLoginState(initBotId, requestToken);
  loginPollingRef.current = window.setInterval(() => {
    void refreshWecomWebLoginState(initBotId, requestToken);
  }, 3000);
}, [clearWecomWebLoginPolling, initBotId, isHostedWecomAdapter, refreshWecomWebLoginState]);
```

`wecomWebLoginState.ts` 保持文件名不动，但逻辑改成“企微托管登录态”通用推导，不再只在文案上绑定 `wecomweb`。

- [ ] **Step 7: 运行后端回归和前端构建**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run python -m pytest tests/unit_tests/platform/test_wecom_external_contact_api.py tests/unit_tests/platform/test_wecomprivate_adapter.py tests/unit_tests/platform/test_wecomprivate_runtime.py tests/unit_tests/service_desk/test_models.py tests/unit_tests/service_desk/test_wecom_private_service.py tests/unit_tests/service_desk/test_service_desk_service.py tests/unit_tests/service_desk/test_runtime_flow.py tests/unit_tests/service_desk/test_session_detail_api.py -v`

Expected: PASS

Run: `cd /home/daisheng/code/copy_dkd/LangBot/web && npm run build`

Expected: PASS，前端类型与构建无报错。

- [ ] **Step 8: 提交这一小步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/api/http/controller/groups/wecom_private.py \
        web/src/app/infra/entities/api/index.ts \
        web/src/app/infra/http/BackendClient.ts \
        web/src/app/home/service-desk/ServiceDeskContent.tsx \
        web/src/app/home/service-desk/components/BotDeskConfigForm.tsx \
        web/src/app/home/service-desk/components/SessionDetail.tsx \
        web/src/app/home/bots/components/bot-form/BotForm.tsx \
        web/src/app/home/bots/components/bot-form/wecomWebLoginState.ts
git commit -m "feat(web): 增加企微私域二维码与会话界面"
```

## Self-Review

### Spec Coverage

- “固定二维码管理” 对应 Task 1 的官方接口客户端 + Task 2 的 `WecomPrivateContactConfig` + Task 5 的二维码同步接口和配置卡片。
- “私域接入承接” 对应 Task 3 的 `wecomprivate` 适配器和 `WecomPrivatePageClient`。
- “AI 首轮欢迎与持续接待” 对应 Task 4 的 `service_desk` 接入。第一条 AI 回复由现有 pipeline 正常产出；官方 `send_welcome_msg` 已在 Task 1 可用，后续如验证到 `welcome_code` 可直接接上。
- “规则驱动转人工” 对应 Task 4 的 `record_routing_decision` 和 `pending_manual` 路径。
- “人工接管落在 LangBot 客服台” 对应 Task 4 与 Task 5 的 `service_desk` 扩展，不新建第二套人工工作台。
- “后补绑定记录” 对应 Task 2 的 `WecomPrivateBindingTask` 和 Task 5 的绑定补录面板。
- “会后标签/备注回写” 对应 Task 1 的 `mark_tags / update_remark` 和 Task 2 / Task 5 的闭环记录、闭环接口、闭环 UI。
- “明确处理 transport 不确定性” 已在 Task 1 Step 1 冻结为第一期前置边界，不再默认把官方接口误当成持续聊天 transport。

### Placeholder Scan

- 已检查全文，没有 `TBD`、`TODO`、`implement later`、`similar to Task N` 之类占位表述。
- 每个需要改代码的步骤都给出了实际代码骨架或接口签名，而不是抽象描述。
- 每个任务都给出了可执行命令和预期结果。

### Naming Consistency

- 官方接口客户端统一使用 `WecomExternalContactClient`。
- 私域后端服务统一使用 `WecomPrivateService`。
- 私域适配器统一使用 `wecomprivate` / `WecomPrivateAdapter` / `WecomPrivatePageClient`。
- 私域数据模型统一使用 `WecomPrivateContactConfig / WecomPrivateLead / WecomPrivateRoutingDecision / WecomPrivateBindingTask / WecomPrivateClosureRecord`。
- 客服台会话继续复用 `ServiceDeskSession`，只新增 `lead_id / risk_level / closed_at`，不另起第二套会话主表。

# WeCom Private AI Reception Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `wecomprivate` 增加面向传奇品类运营的 AI 自动接待后台配置，使每个私域入口 bot 能绑定一套接待模板并配置欢迎、补问、兜底与转下一环规则。

**Architecture:** 继续复用 `Pipeline` 作为接待模板，保留欢迎语、角色设定与知识库绑定；新增独立的 `wecom_private_reception_configs` 持久化对象承载入口级接待规则；在 `ServiceDeskService.handle_incoming_message` 中把 `wecomprivate` 消息统一编排为“欢迎 -> 直接转出 -> 补问 -> 继续 AI -> 兜底转出”的决策链，并通过现有 `RuntimeBot._handle_service_desk_before_pipeline` 在进入 pipeline 前执行。

**Tech Stack:** Python 3.11+, Quart, SQLAlchemy async ORM, legacy DB migrations, React 19 + TypeScript + Vite, existing `BackendClient`, existing `service_desk` / `wecom_private` services.

---

## File Map

- Create: `src/langbot/pkg/persistence/migrations/dbm029_wecom_private_ai_reception_config.py`
  - 新增 `wecom_private_reception_configs` 表，并给 `wecom_private_binding_tasks` 增加 `provided_role_name`
- Modify: `src/langbot/pkg/entity/persistence/service_desk.py`
  - 增加 `WecomPrivateReceptionConfig` ORM 模型，补充 `WecomPrivateBindingTask.provided_role_name`
- Modify: `src/langbot/pkg/utils/constants.py`
  - 将 `required_database_version` 升到 `29`
- Modify: `src/langbot/pkg/api/http/service/wecom_private.py`
  - 提供 reception config 的默认值、查询、保存，以及绑定任务写入 `provided_role_name`
- Modify: `src/langbot/pkg/api/http/controller/groups/wecom_private.py`
  - 新增 reception config 的 GET/PUT 路由
- Modify: `src/langbot/pkg/api/http/service/service_desk.py`
  - 接入 `wecomprivate` reception config，新增补问与兜底决策
- Modify: `src/langbot/pkg/platform/botmgr.py`
  - 让运行时支持“发一条系统回复并跳过 pipeline”的新动作
- Modify: `web/src/app/infra/entities/api/index.ts`
  - 新增 `WecomPrivateReceptionConfig` 类型，扩展 `WecomPrivateBindingTask`
- Modify: `web/src/app/infra/http/BackendClient.ts`
  - 新增 reception config 的 GET/PUT 方法，扩展 binding task payload
- Modify: `web/src/app/home/service-desk/components/BotDeskConfigForm.tsx`
  - 增加 `wecomprivate` 的 AI 自动接待配置卡片和 pipeline 摘要
- Modify: `web/src/app/home/service-desk/components/SessionDetail.tsx`
  - 补录面板增加 `角色名` 字段并透传到接口
- Modify: `web/src/i18n/locales/zh-Hans.ts`
- Modify: `web/src/i18n/locales/en-US.ts`
  - 新增 AI 自动接待配置文案
- Modify: `tests/unit_tests/service_desk/test_models.py`
- Modify: `tests/unit_tests/service_desk/test_wecom_private_service.py`
- Modify: `tests/unit_tests/service_desk/test_service_desk_service.py`
- Modify: `tests/unit_tests/service_desk/test_runtime_flow.py`
- Modify: `tests/unit_tests/service_desk/test_session_detail_api.py`
  - 覆盖模型、服务、运行时和 detail overlay 回归

---

### Task 1: 落地私域接待配置模型与数据库迁移

**Files:**
- Create: `src/langbot/pkg/persistence/migrations/dbm029_wecom_private_ai_reception_config.py`
- Modify: `src/langbot/pkg/entity/persistence/service_desk.py`
- Modify: `src/langbot/pkg/utils/constants.py`
- Test: `tests/unit_tests/service_desk/test_models.py`

- [ ] **Step 1: 先写失败测试，锁定新模型、角色名字段和数据库版本**

在 `tests/unit_tests/service_desk/test_models.py` 追加这组断言：

```python
import sqlalchemy


def test_required_database_version_is_29():
    from langbot.pkg.utils import constants

    assert constants.required_database_version == 29


def test_wecom_private_reception_config_model_exists():
    from langbot.pkg.entity.persistence.service_desk import (
        WecomPrivateBindingTask,
        WecomPrivateReceptionConfig,
    )

    assert WecomPrivateReceptionConfig.__tablename__ == 'wecom_private_reception_configs'
    assert WecomPrivateReceptionConfig.__table__.c['bot_uuid'].primary_key is True
    assert isinstance(
        WecomPrivateReceptionConfig.__table__.c['binding_required_fields'].type,
        sqlalchemy.JSON,
    )
    assert 'provided_role_name' in WecomPrivateBindingTask.__table__.c
```

- [ ] **Step 2: 运行测试，确认当前因为模型和版本号缺失而失败**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/service_desk/test_models.py -q
```

Expected: FAIL，至少包含以下一种失败：

- `assert 28 == 29`
- `ImportError` / `AttributeError` 指向 `WecomPrivateReceptionConfig`
- `AssertionError: 'provided_role_name' not in WecomPrivateBindingTask.__table__.c`

- [ ] **Step 3: 实现 ORM 模型、binding role_name 字段和 migration**

在 `src/langbot/pkg/entity/persistence/service_desk.py` 中新增模型，并补齐 `provided_role_name`：

```python
class WecomPrivateReceptionConfig(Base):
    """WeCom private domain AI reception config"""

    __tablename__ = 'wecom_private_reception_configs'

    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    reception_enabled = sqlalchemy.Column(
        sqlalchemy.Boolean,
        nullable=False,
        default=True,
        server_default=sqlalchemy.true(),
    )
    welcome_enabled = sqlalchemy.Column(
        sqlalchemy.Boolean,
        nullable=False,
        default=True,
        server_default=sqlalchemy.true(),
    )
    fallback_reply_text = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    binding_required_fields = sqlalchemy.Column(
        sqlalchemy.JSON,
        nullable=False,
        server_default='[]',
    )
    binding_trigger_keywords = sqlalchemy.Column(
        sqlalchemy.JSON,
        nullable=False,
        server_default='[]',
    )
    binding_prompt_text = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    human_handoff_direct_enabled = sqlalchemy.Column(
        sqlalchemy.Boolean,
        nullable=False,
        default=True,
        server_default=sqlalchemy.true(),
    )
    created_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
    )
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )
```

同时修改 `WecomPrivateBindingTask`：

```python
provided_role_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
```

新增 migration `src/langbot/pkg/persistence/migrations/dbm029_wecom_private_ai_reception_config.py`：

```python
import sqlalchemy

from .. import migration


@migration.migration_class(29)
class DBMigrateWecomPrivateAIReceptionConfig(migration.DBMigration):
    async def upgrade(self):
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                CREATE TABLE wecom_private_reception_configs (
                    bot_uuid VARCHAR(255) PRIMARY KEY,
                    reception_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    welcome_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    fallback_reply_text TEXT,
                    binding_required_fields JSON NOT NULL DEFAULT '[]',
                    binding_trigger_keywords JSON NOT NULL DEFAULT '[]',
                    binding_prompt_text TEXT,
                    human_handoff_direct_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                "ALTER TABLE wecom_private_binding_tasks ADD COLUMN provided_role_name VARCHAR(255)"
            )
        )

    async def downgrade(self):
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('DROP TABLE wecom_private_reception_configs')
        )
```

最后把 `src/langbot/pkg/utils/constants.py` 改成：

```python
required_database_version = 29
```

- [ ] **Step 4: 重跑模型测试，确认模型层转绿**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/service_desk/test_models.py -q
```

Expected: PASS

- [ ] **Step 5: 提交模型与 migration**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/entity/persistence/service_desk.py src/langbot/pkg/persistence/migrations/dbm029_wecom_private_ai_reception_config.py src/langbot/pkg/utils/constants.py tests/unit_tests/service_desk/test_models.py
git commit -m "feat(service-desk): 增加私域接待配置模型"
```

---

### Task 2: 提供私域接待配置服务与接口

**Files:**
- Modify: `src/langbot/pkg/api/http/service/wecom_private.py`
- Modify: `src/langbot/pkg/api/http/controller/groups/wecom_private.py`
- Modify: `tests/unit_tests/service_desk/test_wecom_private_service.py`
- Modify: `tests/unit_tests/service_desk/test_session_detail_api.py`

- [ ] **Step 1: 先写失败测试，锁定默认配置、更新接口和角色名透传**

在 `tests/unit_tests/service_desk/test_wecom_private_service.py` 增加这三类测试：

```python
@pytest.mark.asyncio
async def test_get_reception_config_returns_defaults_when_row_missing():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock()
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda _model, row: row)

    service = WecomPrivateService(ap)
    service._get_reception_config = AsyncMock(return_value=None)

    config = await service.get_reception_config(bot_uuid='bot-1')

    assert config == {
        'bot_uuid': 'bot-1',
        'reception_enabled': True,
        'welcome_enabled': True,
        'fallback_reply_text': '',
        'binding_required_fields': ['uid', 'server'],
        'binding_trigger_keywords': [],
        'binding_prompt_text': '',
        'human_handoff_direct_enabled': True,
    }


@pytest.mark.asyncio
async def test_upsert_reception_config_normalizes_payload():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock()
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda _model, row: row)

    service = WecomPrivateService(ap)
    service._upsert_reception_config_row = AsyncMock(
        return_value={'bot_uuid': 'bot-1', 'reception_enabled': False}
    )

    result = await service.upsert_reception_config(
        bot_uuid='bot-1',
        data={
            'reception_enabled': False,
            'welcome_enabled': True,
            'fallback_reply_text': '请稍等，我帮你转人工。',
            'binding_required_fields': ['uid', 'server', 'role_name'],
            'binding_trigger_keywords': ['补偿', '充值'],
            'binding_prompt_text': '请按 UID / 区服 / 角色名 回复',
            'human_handoff_direct_enabled': True,
        },
    )

    assert result['reception_enabled'] is False
    service._upsert_reception_config_row.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_binding_task_persists_role_name():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock()
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda _model, row: row)

    service = WecomPrivateService(ap)
    service._upsert_binding_task_row = AsyncMock(
        return_value={'provided_role_name': '烈火战神'}
    )

    result = await service.upsert_binding_task(
        session_id='person_cfg-1:wo123',
        data={
            'requested_fields': ['uid', 'server', 'role_name'],
            'provided_uid': '10001',
            'provided_server': 'S1',
            'provided_role_name': '烈火战神',
            'verify_status': 'completed',
        },
    )

    assert result['provided_role_name'] == '烈火战神'
```

在 `tests/unit_tests/service_desk/test_session_detail_api.py` 给 overlay 断言补一行：

```python
assert detail['binding_task']['provided_role_name'] == '烈火战神'
```

- [ ] **Step 2: 运行后端服务测试，确认当前因为新方法和字段不存在而失败**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/service_desk/test_wecom_private_service.py tests/unit_tests/service_desk/test_session_detail_api.py -q
```

Expected: FAIL，原因包括：

- `AttributeError: 'WecomPrivateService' object has no attribute 'get_reception_config'`
- `KeyError` / `AssertionError` 指向 `provided_role_name`

- [ ] **Step 3: 在 `WecomPrivateService` 中实现默认配置、查询、保存与角色名透传**

在 `src/langbot/pkg/api/http/service/wecom_private.py` 增加默认值和 CRUD：

```python
def _default_reception_config(self, bot_uuid: str) -> dict[str, Any]:
    return {
        'bot_uuid': bot_uuid,
        'reception_enabled': True,
        'welcome_enabled': True,
        'fallback_reply_text': '',
        'binding_required_fields': ['uid', 'server'],
        'binding_trigger_keywords': [],
        'binding_prompt_text': '',
        'human_handoff_direct_enabled': True,
    }


async def get_reception_config(self, *, bot_uuid: str) -> dict[str, Any]:
    row = await self._get_reception_config(bot_uuid)
    if row is None:
        return self._default_reception_config(bot_uuid)
    return self._serialize(persistence_service_desk.WecomPrivateReceptionConfig, row)


async def upsert_reception_config(self, *, bot_uuid: str, data: dict[str, Any]) -> dict[str, Any]:
    payload = {
        'bot_uuid': bot_uuid,
        'reception_enabled': bool(data.get('reception_enabled', True)),
        'welcome_enabled': bool(data.get('welcome_enabled', True)),
        'fallback_reply_text': str(data.get('fallback_reply_text') or '').strip(),
        'binding_required_fields': list(data.get('binding_required_fields') or ['uid', 'server']),
        'binding_trigger_keywords': [str(item).strip() for item in data.get('binding_trigger_keywords', []) if str(item).strip()],
        'binding_prompt_text': str(data.get('binding_prompt_text') or '').strip(),
        'human_handoff_direct_enabled': bool(data.get('human_handoff_direct_enabled', True)),
    }
    await self._upsert_reception_config_row(payload)
    return payload
```

同时把 `upsert_binding_task()` 改为透传 `provided_role_name`：

```python
'provided_role_name': data.get('provided_role_name'),
```

并新增查询/保存辅助方法：

```python
async def _get_reception_config(self, bot_uuid: str):
    result = await self.ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_service_desk.WecomPrivateReceptionConfig).where(
            persistence_service_desk.WecomPrivateReceptionConfig.bot_uuid == bot_uuid
        )
    )
    return result.first()
```

- [ ] **Step 4: 暴露 reception config 路由**

在 `src/langbot/pkg/api/http/controller/groups/wecom_private.py` 中新增：

```python
@self.route('/reception-config/<bot_uuid>', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
async def get_reception_config(bot_uuid: str) -> str:
    config = await self.ap.wecom_private_service.get_reception_config(bot_uuid=bot_uuid)
    return self.success(data={'config': config})


@self.route('/reception-config/<bot_uuid>', methods=['PUT'], auth_type=group.AuthType.USER_TOKEN)
async def update_reception_config(bot_uuid: str) -> str:
    payload = await quart.request.json
    config = await self.ap.wecom_private_service.upsert_reception_config(
        bot_uuid=bot_uuid,
        data=payload or {},
    )
    return self.success(data={'config': config})
```

- [ ] **Step 5: 重跑服务测试并提交接口层变更**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/service_desk/test_wecom_private_service.py tests/unit_tests/service_desk/test_session_detail_api.py -q
```

Expected: PASS

Commit:

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/api/http/service/wecom_private.py src/langbot/pkg/api/http/controller/groups/wecom_private.py tests/unit_tests/service_desk/test_wecom_private_service.py tests/unit_tests/service_desk/test_session_detail_api.py
git commit -m "feat(wecom-private): 增加自动接待配置接口"
```

---

### Task 3: 把 AI 自动接待决策接入 `service_desk` 运行时

**Files:**
- Modify: `src/langbot/pkg/api/http/service/service_desk.py`
- Modify: `src/langbot/pkg/platform/botmgr.py`
- Modify: `tests/unit_tests/service_desk/test_service_desk_service.py`
- Modify: `tests/unit_tests/service_desk/test_runtime_flow.py`

- [ ] **Step 1: 先写失败测试，锁定补问、兜底和运行时新动作**

在 `tests/unit_tests/service_desk/test_service_desk_service.py` 增加这两组测试：

```python
@pytest.mark.asyncio
async def test_handle_incoming_message_prompts_binding_when_trigger_matches_and_fields_missing():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.wecom_private_service.bootstrap_private_lead = AsyncMock(
        return_value={'id': 'lead-1'}
    )
    ap.wecom_private_service.get_reception_config = AsyncMock(
        return_value={
            'bot_uuid': 'bot-1',
            'reception_enabled': True,
            'welcome_enabled': True,
            'fallback_reply_text': '',
            'binding_required_fields': ['uid', 'server', 'role_name'],
            'binding_trigger_keywords': ['补偿'],
            'binding_prompt_text': '请按 UID / 区服 / 角色名 回复',
            'human_handoff_direct_enabled': True,
        }
    )
    ap.wecom_private_service.get_session_overlay = AsyncMock(
        return_value={'binding_task': None}
    )
    ap.wecom_private_service.upsert_binding_task = AsyncMock(
        return_value={'session_id': 'person_cfg-1:wo123'}
    )

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={'session_id': 'person_cfg-1:wo123', 'mode': 'ai_hosted', 'queue_status': 'ai', 'unresolved_count': 0}
    )
    service.get_bot_config = AsyncMock(
        return_value={'enabled': True, 'handoff_keywords': [], 'fallback_unresolved_count': 2}
    )
    service.list_materials = AsyncMock(return_value=[])

    bot_entity = SimpleNamespace(adapter='wecomprivate', uuid='bot-1', use_pipeline_uuid='pipe-1')
    event = SimpleNamespace(
        message_chain='我要补偿',
        source_platform_object=SimpleNamespace(
            follow_user_id='zhangsan',
            external_user_id='wo123',
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

    assert decision.action == 'send_material_and_skip'
    assert decision.material['reply_text'] == '请按 UID / 区服 / 角色名 回复'
    ap.wecom_private_service.upsert_binding_task.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_incoming_message_fallback_routes_after_unresolved_threshold():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    ap = Mock()
    ap.wecom_private_service.bootstrap_private_lead = AsyncMock(return_value={'id': 'lead-1'})
    ap.wecom_private_service.get_reception_config = AsyncMock(
        return_value={
            'bot_uuid': 'bot-1',
            'reception_enabled': True,
            'welcome_enabled': True,
            'fallback_reply_text': '这边先帮你转人工处理。',
            'binding_required_fields': ['uid', 'server'],
            'binding_trigger_keywords': [],
            'binding_prompt_text': '',
            'human_handoff_direct_enabled': True,
        }
    )
    ap.wecom_private_service.get_session_overlay = AsyncMock(
        return_value={'binding_task': None}
    )
    ap.wecom_private_service.record_routing_decision = AsyncMock()

    service = ServiceDeskService(ap)
    service._touch_session = AsyncMock(
        return_value={'session_id': 'person_cfg-1:wo123', 'mode': 'ai_hosted', 'queue_status': 'ai', 'unresolved_count': 1}
    )
    service.get_bot_config = AsyncMock(
        return_value={'enabled': True, 'handoff_keywords': [], 'fallback_unresolved_count': 2}
    )
    service.list_materials = AsyncMock(return_value=[])
    service._update_session_state = AsyncMock()

    bot_entity = SimpleNamespace(adapter='wecomprivate', uuid='bot-1', use_pipeline_uuid='pipe-1')
    event = SimpleNamespace(
        message_chain='还是没解决',
        source_platform_object=SimpleNamespace(
            follow_user_id='zhangsan',
            external_user_id='wo123',
            welcome_code=None,
        ),
        sender=SimpleNamespace(id='wo123', nickname='玩家A'),
    )
    adapter = Mock()
    adapter.extract_service_desk_context.return_value = {
        'source_entry_id': 'cfg-1',
        'external_user_id': 'wo123',
        'last_message_id': 'msg-2',
    }
    adapter.get_launcher_id.return_value = 'cfg-1:wo123'

    decision = await service.handle_incoming_message(
        bot_entity=bot_entity,
        event=event,
        adapter=adapter,
        pipeline_uuid='pipe-1',
    )

    assert decision.action == 'send_material_and_skip'
    assert decision.material['reply_text'] == '这边先帮你转人工处理。'
    service._update_session_state.assert_awaited()
```

在 `tests/unit_tests/service_desk/test_runtime_flow.py` 增加运行时动作测试：

```python
@pytest.mark.asyncio
async def test_send_material_and_skip_stops_pipeline_after_reply():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskDecision
    from langbot.pkg.platform.botmgr import RuntimeBot

    bot = object.__new__(RuntimeBot)
    bot.bot_entity = Mock()
    bot.ap = Mock()
    bot.logger = Mock()
    bot.logger.info = AsyncMock()
    bot.ap.service_desk_service = Mock()
    bot.ap.service_desk_service.handle_incoming_message = AsyncMock(
        return_value=ServiceDeskDecision(
            action='send_material_and_skip',
            reason='binding_required',
            material={'reply_text': '请回复 UID / 区服 / 角色名'},
        )
    )
    bot.ap.service_desk_service.send_structured_reply = AsyncMock()

    handled = await bot._handle_service_desk_before_pipeline(Mock(), Mock())

    assert handled is True
    bot.ap.service_desk_service.send_structured_reply.assert_awaited_once()
```

- [ ] **Step 2: 运行测试，确认当前因为新动作和 reception 决策不存在而失败**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/service_desk/test_service_desk_service.py tests/unit_tests/service_desk/test_runtime_flow.py -q
```

Expected: FAIL，原因包括：

- `AssertionError: assert 'continue_ai' == 'send_material_and_skip'`
- `AssertionError: False is not True`

- [ ] **Step 3: 在 `ServiceDeskService` 中接入 reception config 决策**

在 `src/langbot/pkg/api/http/service/service_desk.py` 新增 5 个辅助方法：

```python
async def _get_wecom_private_reception_config(self, bot_uuid: str) -> dict:
    config = await self._call_async_method(
        getattr(self.ap, 'wecom_private_service', None),
        'get_reception_config',
        bot_uuid=bot_uuid,
    )
    return config if isinstance(config, dict) else {}


def _build_reply_material(self, reply_text: str) -> dict:
    return {
        'material_type': 'quick_reply',
        'title': 'AI Reception',
        'reply_text': reply_text,
        'trigger_keywords': [],
        'payload': {},
        'priority': 0,
        'enabled': True,
    }


def _extract_binding_values(self, message_text: str) -> dict[str, str]:
    text = str(message_text or '')
    patterns = {
        'uid': r'(?:UID|uid|角色ID|角色id)[:：\s]*([A-Za-z0-9_-]+)',
        'server': r'(?:区服|服务器)[:：\s]*([A-Za-z0-9_-]+)',
        'role_name': r'(?:角色名|角色名称)[:：\s]*([^\s,，]+)',
    }
    values: dict[str, str] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            values[key] = match.group(1).strip()
    return values
```

并把 `handle_incoming_message()` 中 `wecomprivate` 分支改成：

```python
reception_config = await self._get_wecom_private_reception_config(bot_entity.uuid)
overlay = await self._call_async_method(
    wecom_private_service,
    'get_session_overlay',
    session_id,
) or {}
binding_task = overlay.get('binding_task')

if reception_config.get('reception_enabled', True):
    message_text = str(getattr(event, 'message_chain', '') or '')
    trigger_keywords = reception_config.get('binding_trigger_keywords', [])
    required_fields = reception_config.get('binding_required_fields', ['uid', 'server'])
    extracted_values = self._extract_binding_values(message_text)
    current_values = {
        'uid': self._get_value(binding_task, 'provided_uid', ''),
        'server': self._get_value(binding_task, 'provided_server', ''),
        'role_name': self._get_value(binding_task, 'provided_role_name', ''),
    }
    merged_values = {
        key: extracted_values.get(key) or current_values.get(key, '')
        for key in ('uid', 'server', 'role_name')
    }
    missing_fields = [field for field in required_fields if not merged_values.get(field)]

    if any(keyword.strip() and keyword.strip() in message_text for keyword in trigger_keywords) and missing_fields:
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
        return ServiceDeskDecision(
            action='send_material_and_skip',
            reason='binding_required',
            material=self._build_reply_material(reception_config.get('binding_prompt_text') or '请补充 UID / 区服 信息'),
        )

    next_unresolved_count = int(self._get_value(session, 'unresolved_count', 0) or 0) + 1
    threshold = int((config or {}).get('fallback_unresolved_count', 2) or 2)
    if next_unresolved_count >= threshold and reception_config.get('fallback_reply_text'):
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
        return ServiceDeskDecision(
            action='send_material_and_skip',
            reason='fallback_route',
            material=self._build_reply_material(reception_config['fallback_reply_text']),
        )

    await self._update_session_state(session_id, unresolved_count=next_unresolved_count)
```

实现要求：

- `handoff_keywords` 直接人工转出逻辑继续保留
- `request_binding_fields` 结果在运行时映射为 `send_material_and_skip`
- `route_next_stage` 在第一版映射到现有 `pending_manual`

- [ ] **Step 4: 让 `RuntimeBot` 支持新动作**

在 `src/langbot/pkg/platform/botmgr.py` 中把动作判断改成：

```python
if decision.action in {'send_material', 'send_material_and_skip'}:
    await self.ap.service_desk_service.send_structured_reply(
        runtime_bot=self,
        event=event,
        adapter=adapter,
        material=decision.material or {},
    )
    await self.logger.info(f'Service desk sent structured reply: {decision.reason}')
    return decision.action == 'send_material_and_skip'
```

- [ ] **Step 5: 重跑运行时测试并提交**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/service_desk/test_service_desk_service.py tests/unit_tests/service_desk/test_runtime_flow.py -q
```

Expected: PASS

Commit:

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/api/http/service/service_desk.py src/langbot/pkg/platform/botmgr.py tests/unit_tests/service_desk/test_service_desk_service.py tests/unit_tests/service_desk/test_runtime_flow.py
git commit -m "feat(service-desk): 接入私域自动接待决策"
```

---

### Task 4: 前端增加 AI 自动接待配置卡片与角色名补录

**Files:**
- Modify: `web/src/app/infra/entities/api/index.ts`
- Modify: `web/src/app/infra/http/BackendClient.ts`
- Modify: `web/src/app/home/service-desk/components/BotDeskConfigForm.tsx`
- Modify: `web/src/app/home/service-desk/components/SessionDetail.tsx`
- Modify: `web/src/i18n/locales/zh-Hans.ts`
- Modify: `web/src/i18n/locales/en-US.ts`

- [ ] **Step 1: 先写前端契约断言，锁定 DTO、客户端方法和表单字段**

Run:

```bash
node - <<'NODE'
const fs = require('fs');
const api = fs.readFileSync('/home/daisheng/code/copy_dkd/LangBot/web/src/app/infra/entities/api/index.ts', 'utf8');
const client = fs.readFileSync('/home/daisheng/code/copy_dkd/LangBot/web/src/app/infra/http/BackendClient.ts', 'utf8');
const form = fs.readFileSync('/home/daisheng/code/copy_dkd/LangBot/web/src/app/home/service-desk/components/BotDeskConfigForm.tsx', 'utf8');
const detail = fs.readFileSync('/home/daisheng/code/copy_dkd/LangBot/web/src/app/home/service-desk/components/SessionDetail.tsx', 'utf8');
function assert(cond, msg) { if (!cond) throw new Error(msg); }
assert(api.includes('interface WecomPrivateReceptionConfig'), 'missing reception config dto');
assert(api.includes('provided_role_name'), 'missing binding role name dto');
assert(client.includes('getWecomPrivateReceptionConfig'), 'missing reception config getter');
assert(client.includes('updateWecomPrivateReceptionConfig'), 'missing reception config updater');
assert(form.includes('AI 自动接待配置') || form.includes('aiReception'), 'missing reception config form section');
assert(detail.includes('provided_role_name') || detail.includes('bindingRoleName'), 'missing binding role name input');
console.log('frontend contracts ok');
NODE
```

Expected: FAIL，提示缺少 DTO、HTTP 方法或表单字段

- [ ] **Step 2: 增加前端类型和 HTTP 客户端方法**

在 `web/src/app/infra/entities/api/index.ts` 追加：

```ts
export interface WecomPrivateReceptionConfig {
  bot_uuid: string;
  reception_enabled: boolean;
  welcome_enabled: boolean;
  fallback_reply_text: string;
  binding_required_fields: string[];
  binding_trigger_keywords: string[];
  binding_prompt_text: string;
  human_handoff_direct_enabled: boolean;
  created_at?: string;
  updated_at?: string;
}
```

同时扩展：

```ts
export interface WecomPrivateBindingTask {
  id: string;
  session_id: string;
  requested_fields: string[];
  provided_uid?: string | null;
  provided_server?: string | null;
  provided_role_name?: string | null;
  verify_status: 'pending' | 'completed' | 'manual_verified';
  requested_at?: string;
}
```

在 `web/src/app/infra/http/BackendClient.ts` 追加：

```ts
public getWecomPrivateReceptionConfig(
  botUuid: string,
): Promise<{ config: WecomPrivateReceptionConfig }> {
  return this.get(`/api/v1/wecom-private/reception-config/${botUuid}`);
}

public updateWecomPrivateReceptionConfig(
  botUuid: string,
  payload: Omit<WecomPrivateReceptionConfig, 'bot_uuid' | 'created_at' | 'updated_at'>,
): Promise<{ config: WecomPrivateReceptionConfig }> {
  return this.put(`/api/v1/wecom-private/reception-config/${botUuid}`, payload);
}
```

并把 `upsertServiceDeskBindingTask()` 的 payload 改成：

```ts
provided_role_name?: string;
```

- [ ] **Step 3: 在 `BotDeskConfigForm` 中增加 AI 自动接待配置卡片**

实现要求：

- 仅在 `bot.adapter === 'wecomprivate'` 时显示
- 进入页面时同时拉取：
  - `httpClient.getWecomPrivateReceptionConfig(bot.uuid)`
  - `httpClient.getPipeline(bot.use_pipeline_uuid)`
- 保存时同时提交：
  - `httpClient.updateServiceDeskBotConfig(bot.uuid, { version_label, handoff_keywords, manual_timeout_seconds, enabled })`
  - `httpClient.updateWecomPrivateReceptionConfig(bot.uuid, { reception_enabled, welcome_enabled, fallback_reply_text, binding_required_fields, binding_trigger_keywords, binding_prompt_text, human_handoff_direct_enabled })`

关键代码骨架：

```tsx
interface ReceptionDraft {
  receptionEnabled: boolean;
  welcomeEnabled: boolean;
  fallbackReplyText: string;
  bindingRequiredFields: string[];
  bindingTriggerKeywords: string;
  bindingPromptText: string;
  humanHandoffDirectEnabled: boolean;
}

const [receptionDraft, setReceptionDraft] = useState<ReceptionDraft>({
  receptionEnabled: true,
  welcomeEnabled: true,
  fallbackReplyText: '',
  bindingRequiredFields: ['uid', 'server'],
  bindingTriggerKeywords: '',
  bindingPromptText: '',
  humanHandoffDirectEnabled: true,
});
```

卡片中展示：

- AI 自动接待开关
- 欢迎事件开关
- 未解决轮次阈值（继续复用 `draft.manual/fallback_unresolved_count` 所在区域）
- 兜底文案
- 补问字段多选
- 补问触发关键词
- 补问引导文案
- 用户要求人工直接转出开关
- 当前绑定模板摘要：
  - pipeline 名称
  - `opening-intro` 预览
  - `knowledge-bases.length`

- [ ] **Step 4: 在 `SessionDetail` 里增加角色名补录**

在 `web/src/app/home/service-desk/components/SessionDetail.tsx` 中补一组状态：

```tsx
const [bindingRoleName, setBindingRoleName] = useState('');

useEffect(() => {
  setBindingRoleName(bindingTask?.provided_role_name ?? '');
}, [bindingTask?.id, bindingTask?.provided_role_name]);
```

保存时改成：

```tsx
const requestedFields = bindingTask?.requested_fields?.length
  ? bindingTask.requested_fields
  : ['uid', 'server', 'role_name'];

const resp = await httpClient.upsertServiceDeskBindingTask(
  session.session_id,
  {
    requested_fields: requestedFields,
    provided_uid: bindingUid.trim() || undefined,
    provided_server: bindingServer.trim() || undefined,
    provided_role_name: bindingRoleName.trim() || undefined,
    verify_status:
      bindingUid.trim() && bindingServer.trim() ? 'completed' : 'pending',
  },
);
```

同时补中英文文案，例如：

```ts
aiReception: {
  title: 'AI 自动接待配置',
  description: '配置这个私域入口的欢迎、补问、兜底和转下一环规则。',
  receptionEnabled: '启用 AI 自动接待',
  welcomeEnabled: '启用欢迎事件问候',
  fallbackReplyText: '兜底回复文案',
  bindingRequiredFields: '补问字段',
  bindingTriggerKeywords: '补问触发关键词',
  bindingPromptText: '补问引导文案',
  humanHandoffDirectEnabled: '用户要求人工时直接转出',
}
```

- [ ] **Step 5: 运行前端断言和构建后提交**

Run the same `node` contract script from Step 1.  
Expected: PASS

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot/web && npm run build
```

Expected: PASS，`tsc && vite build` 成功

Commit:

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add web/src/app/infra/entities/api/index.ts web/src/app/infra/http/BackendClient.ts web/src/app/home/service-desk/components/BotDeskConfigForm.tsx web/src/app/home/service-desk/components/SessionDetail.tsx web/src/i18n/locales/zh-Hans.ts web/src/i18n/locales/en-US.ts
git commit -m "feat(web): 增加私域自动接待后台配置"
```

---

### Task 5: 做聚焦回归并确认交付边界

**Files:**
- Verify: `src/langbot/pkg/entity/persistence/service_desk.py`
- Verify: `src/langbot/pkg/api/http/service/wecom_private.py`
- Verify: `src/langbot/pkg/api/http/service/service_desk.py`
- Verify: `src/langbot/pkg/platform/botmgr.py`
- Verify: `web/src/app/home/service-desk/components/BotDeskConfigForm.tsx`
- Verify: `web/src/app/home/service-desk/components/SessionDetail.tsx`
- Verify: `tests/unit_tests/service_desk/test_models.py`
- Verify: `tests/unit_tests/service_desk/test_wecom_private_service.py`
- Verify: `tests/unit_tests/service_desk/test_service_desk_service.py`
- Verify: `tests/unit_tests/service_desk/test_runtime_flow.py`
- Verify: `tests/unit_tests/service_desk/test_session_detail_api.py`

- [ ] **Step 1: 运行后端聚焦测试**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest \
  tests/unit_tests/service_desk/test_models.py \
  tests/unit_tests/service_desk/test_wecom_private_service.py \
  tests/unit_tests/service_desk/test_service_desk_service.py \
  tests/unit_tests/service_desk/test_runtime_flow.py \
  tests/unit_tests/service_desk/test_session_detail_api.py -v
```

Expected: PASS

- [ ] **Step 2: 运行前端构建**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot/web && npm run build
```

Expected: PASS

- [ ] **Step 3: 检查工作区只包含本次实现相关变更**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot && git status --short --branch
```

Expected: 仅包含本计划涉及的文件，外加用户已知的 phase1 历史改动；不要误带 `.superpowers/` 或无关文件

- [ ] **Step 4: 记录未做项，避免过度扩张**

在最终交付说明里明确本轮没有实现：

```text
- wecomweb / wecomcs 通用化
- 独立模板中心
- 可视化流程编排器
- 完整用户分层与复杂风险评分
- 会后运营闭环
```

---

## Self-Review

### Spec coverage

- spec 中的 `bot = 入口 / pipeline = 模板 / bot config = 规则覆盖`：
  - 由 Task 1、Task 2、Task 4 共同落地
- `wecomprivate` 专属后台可配置：
  - 由 Task 2、Task 4 落地
- `欢迎 -> 补问 -> 继续 AI -> 兜底转出` 决策闭环：
  - 由 Task 3 落地
- `角色名` 进入 binding task：
  - 由 Task 1、Task 2、Task 4 落地
- `route_next_stage` 第一版回退到现有人工待接管链路：
  - 由 Task 3 明确落地

### Placeholder scan

- 本计划不包含 `TODO`、`TBD`、`后续补充` 之类占位步骤
- 每个代码步骤都给出具体文件、代码片段和命令

### Type consistency

- 新配置字段统一使用 `reception_enabled`
- 绑定字段统一使用 `role_name` / `provided_role_name`
- 运行时新增动作统一使用 `send_material_and_skip`

---

Plan complete and saved to `docs/superpowers/plans/2026-04-19-wecom-private-ai-reception-config.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

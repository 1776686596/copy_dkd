# WeCom Private User Identification And Layering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `wecomprivate` 的私域 lead 补齐稳定的“用户识别进度 + 粗分层结果”结构，让客服台和后续阶段都能读取统一画像，而不是继续把所有语义混进 `profile_status`。

**Architecture:** 保留 `WecomPrivateLead.profile_status` 表达识别进度，仅表示 `anonymous / binding_requested / bound`；新增 `user_layer / layer_source / profile_signals / layer_updated_at` 表达分层结果与命中信号；由 `WecomPrivateService` 在 lead 建档与绑定补录时统一刷新画像；客服台继续复用现有 `session detail overlay`，直接展示 lead 新字段，不新起独立画像中心。

**Tech Stack:** Python 3.11+, Quart, SQLAlchemy async ORM, legacy DB migrations, React 19 + TypeScript, existing `wecom_private` service, existing `service_desk` detail page.

---

## Scope Notes

- 本计划只覆盖蓝图第三阶段的最小闭环：`可持久化的识别状态 + 可计算的粗分层结果 + 客服台可见`。
- 本计划明确不做：
  - 独立画像中心或单独后台页面
  - 会话列表按层级筛选 / 排序
  - 人工手动改层级接口
  - 游戏侧实时画像回流
  - 复杂分层引擎、风险评分、自动运营动作
- 这一版落地后，第四阶段和第五阶段应直接消费 `WecomPrivateLead` 的新字段，而不是重新发明一套分层结构。

## File Map

- Create: `src/langbot/pkg/persistence/migrations/dbm030_wecom_private_user_layering.py`
  - 给 `wecom_private_leads` 增加 `user_layer / layer_source / profile_signals / layer_updated_at`
- Modify: `src/langbot/pkg/entity/persistence/service_desk.py`
  - 扩展 `WecomPrivateLead` ORM 模型
- Modify: `src/langbot/pkg/utils/constants.py`
  - 将 `required_database_version` 升到 `30`
- Modify: `src/langbot/pkg/api/http/service/wecom_private.py`
  - 增加“刷新 lead 画像”逻辑，并在建档与 binding 补录后调用
- Modify: `web/src/app/infra/entities/api/index.ts`
  - 扩展 `WecomPrivateLead` TypeScript 类型
- Modify: `web/src/app/home/service-desk/components/SessionDetail.tsx`
  - 展示分层结果、命中信号和最近刷新时间
- Modify: `web/src/i18n/locales/zh-Hans.ts`
- Modify: `web/src/i18n/locales/en-US.ts`
  - 增加第三阶段 UI 文案
- Modify: `tests/unit_tests/service_desk/test_models.py`
- Modify: `tests/unit_tests/service_desk/test_wecom_private_service.py`
- Modify: `tests/unit_tests/service_desk/test_session_detail_api.py`
  - 覆盖模型、分层规则和会话详情回归

---

### Task 1: 扩展 lead 持久化结构，给第三阶段字段留稳定槽位

**Files:**
- Create: `src/langbot/pkg/persistence/migrations/dbm030_wecom_private_user_layering.py`
- Modify: `src/langbot/pkg/entity/persistence/service_desk.py`
- Modify: `src/langbot/pkg/utils/constants.py`
- Test: `tests/unit_tests/service_desk/test_models.py`

- [ ] **Step 1: 先写失败测试，锁定版本号和 lead 新字段**

在 `tests/unit_tests/service_desk/test_models.py` 追加以下断言：

```python
def test_required_database_version_is_30():
    from langbot.pkg.utils import constants

    assert constants.required_database_version == 30


def test_wecom_private_lead_layering_columns_exist():
    from langbot.pkg.entity.persistence.service_desk import WecomPrivateLead

    lead_columns = WecomPrivateLead.__table__.c

    assert isinstance(lead_columns['user_layer'].type, sqlalchemy.String)
    assert lead_columns['user_layer'].nullable is False
    assert isinstance(lead_columns['layer_source'].type, sqlalchemy.String)
    assert lead_columns['layer_source'].nullable is False
    assert isinstance(lead_columns['profile_signals'].type, sqlalchemy.JSON)
    assert lead_columns['layer_updated_at'].nullable is True
```

- [ ] **Step 2: 运行模型测试，确认当前因版本号和字段缺失而失败**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/service_desk/test_models.py -q
```

Expected: FAIL，并至少包含以下一种失败：

- `assert 29 == 30`
- `KeyError: 'user_layer'`
- `KeyError: 'profile_signals'`

- [ ] **Step 3: 实现 ORM 和 migration，固定第三阶段的数据边界**

在 `src/langbot/pkg/entity/persistence/service_desk.py` 的 `WecomPrivateLead` 中补齐字段：

```python
user_layer = sqlalchemy.Column(
    sqlalchemy.String(50),
    nullable=False,
    default='normal',
    server_default='normal',
)
layer_source = sqlalchemy.Column(
    sqlalchemy.String(50),
    nullable=False,
    default='system',
    server_default='system',
)
profile_signals = sqlalchemy.Column(
    sqlalchemy.JSON,
    nullable=False,
    server_default='[]',
)
layer_updated_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
```

新增 migration `src/langbot/pkg/persistence/migrations/dbm030_wecom_private_user_layering.py`：

```python
import sqlalchemy

from .. import migration


@migration.migration_class(30)
class DBMigrateWecomPrivateUserLayering(migration.DBMigration):
    async def upgrade(self):
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                ALTER TABLE wecom_private_leads
                ADD COLUMN user_layer VARCHAR(50) NOT NULL DEFAULT 'normal'
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                ALTER TABLE wecom_private_leads
                ADD COLUMN layer_source VARCHAR(50) NOT NULL DEFAULT 'system'
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                ALTER TABLE wecom_private_leads
                ADD COLUMN profile_signals JSON NOT NULL DEFAULT '[]'
                """
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                ALTER TABLE wecom_private_leads
                ADD COLUMN layer_updated_at TIMESTAMP NULL
                """
            )
        )

    async def downgrade(self):
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                "ALTER TABLE wecom_private_leads DROP COLUMN layer_updated_at"
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                "ALTER TABLE wecom_private_leads DROP COLUMN profile_signals"
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                "ALTER TABLE wecom_private_leads DROP COLUMN layer_source"
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                "ALTER TABLE wecom_private_leads DROP COLUMN user_layer"
            )
        )
```

并将 `src/langbot/pkg/utils/constants.py` 更新为：

```python
required_database_version = 30
```

- [ ] **Step 4: 重跑模型测试，确认结构层转绿**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/service_desk/test_models.py -q
```

Expected: PASS

- [ ] **Step 5: 提交持久化结构改动**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/entity/persistence/service_desk.py \
  src/langbot/pkg/persistence/migrations/dbm030_wecom_private_user_layering.py \
  src/langbot/pkg/utils/constants.py \
  tests/unit_tests/service_desk/test_models.py
git commit -m "feat(wecomprivate): 增加用户识别分层字段"
```

---

### Task 2: 在 wecom_private service 中统一计算识别状态和粗分层结果

**Files:**
- Modify: `src/langbot/pkg/api/http/service/wecom_private.py`
- Test: `tests/unit_tests/service_desk/test_wecom_private_service.py`

- [ ] **Step 1: 先写失败测试，锁定第三阶段规则**

在 `tests/unit_tests/service_desk/test_wecom_private_service.py` 追加以下三组测试：

```python
@pytest.mark.asyncio
async def test_bootstrap_private_lead_sets_default_layer_fields():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    service = WecomPrivateService(ap)
    service._get_lead_by_external_userid = AsyncMock(return_value=None)
    service._build_external_contact_client = AsyncMock()
    service._build_external_contact_client.return_value.get_external_contact = AsyncMock(
        return_value={'external_contact': {}, 'follow_user': []}
    )
    service._insert_lead = AsyncMock(side_effect=lambda payload: payload)
    service._refresh_lead_profile = AsyncMock(side_effect=lambda lead, **_: lead)

    result = await service.bootstrap_private_lead(
        bot_uuid='bot-1',
        external_user_id='ext-1',
        follow_user_id='staff-1',
        source_entry_id='entry-1',
    )

    assert result['user_layer'] == 'normal'
    assert result['layer_source'] == 'system'
    assert result['profile_signals'] == []


@pytest.mark.asyncio
async def test_upsert_binding_task_completes_bound_identity_and_profile_status():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    service = WecomPrivateService(ap)
    service._assert_wecom_private_session = AsyncMock()
    service._get_binding_task = AsyncMock(return_value=None)
    service._upsert_binding_task_row = AsyncMock(
        side_effect=lambda payload: {
            **payload,
            'provided_uid': payload.get('provided_uid'),
            'provided_server': payload.get('provided_server'),
            'provided_role_name': payload.get('provided_role_name'),
        }
    )
    service._get_session = AsyncMock(
        return_value={'session_id': 'person_ext-1', 'lead_id': 'lead-1'}
    )
    service._get_lead = AsyncMock(
        return_value={
            'id': 'lead-1',
            'profile_status': 'binding_requested',
            'bound_game_identity': {},
            'current_tags': [],
            'remark_snapshot': {},
            'source_state': 'dkd-entry',
            'first_add_time': None,
        }
    )
    service._update_lead = AsyncMock(side_effect=lambda lead_id, payload: payload)

    await service.upsert_binding_task(
        session_id='person_ext-1',
        data={
            'requested_fields': ['uid', 'server', 'role_name'],
            'provided_uid': '10001',
            'provided_server': 's1',
            'provided_role_name': '战士阿明',
            'verify_status': 'completed',
        },
    )

    service._update_lead.assert_awaited_once()
    update_payload = service._update_lead.await_args.kwargs['payload']
    assert update_payload['profile_status'] == 'bound'
    assert update_payload['bound_game_identity']['uid'] == '10001'
    assert update_payload['bound_game_identity']['server'] == 's1'
    assert update_payload['bound_game_identity']['role_name'] == '战士阿明'


@pytest.mark.asyncio
async def test_refresh_lead_profile_prefers_big_r_over_vip_and_new_user():
    from langbot.pkg.api.http.service.wecom_private import WecomPrivateService

    ap = Mock()
    service = WecomPrivateService(ap)

    lead = {
        'id': 'lead-1',
        'current_tags': ['VIP玩家', '大R用户'],
        'remark_snapshot': {'remark': '已确认大R'},
        'source_state': 'dkd_campaign',
        'first_add_time': datetime.datetime.utcnow(),
        'profile_status': 'anonymous',
        'bound_game_identity': {},
    }

    result = await service._refresh_lead_profile(lead)

    assert result['user_layer'] == 'big_r'
    assert result['layer_source'] == 'signal'
    assert 'tag_big_r' in result['profile_signals']
```

- [ ] **Step 2: 运行定向测试，确认当前缺少第三阶段逻辑**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/service_desk/test_wecom_private_service.py -q
```

Expected: FAIL，至少包含以下一种失败：

- `KeyError: 'user_layer'`
- `AttributeError: 'WecomPrivateService' object has no attribute '_refresh_lead_profile'`
- `AssertionError` 指向 `profile_status == 'bound'`

- [ ] **Step 3: 在 service 中实现统一刷新逻辑，并只在两个写入口触发**

在 `src/langbot/pkg/api/http/service/wecom_private.py` 中按以下边界实现：

1. `bootstrap_private_lead` 创建 payload 时先带默认字段：

```python
'user_layer': 'normal',
'layer_source': 'system',
'profile_signals': [],
'layer_updated_at': None,
```

2. 新增 `_refresh_lead_profile`，只负责把 lead 当前快照转成统一结构：

```python
async def _refresh_lead_profile(
    self,
    lead: dict[str, Any],
    *,
    binding_task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    identity = dict(self._get_value(lead, 'bound_game_identity', {}) or {})
    verify_status = str(self._get_value(binding_task, 'verify_status', '') or '')

    if verify_status in {'completed', 'manual_verified'}:
        if self._get_value(binding_task, 'provided_uid'):
            identity['uid'] = self._get_value(binding_task, 'provided_uid')
        if self._get_value(binding_task, 'provided_server'):
            identity['server'] = self._get_value(binding_task, 'provided_server')
        if self._get_value(binding_task, 'provided_role_name'):
            identity['role_name'] = self._get_value(binding_task, 'provided_role_name')

    if identity.get('uid') or identity.get('server'):
        profile_status = 'bound'
    elif binding_task is not None:
        profile_status = 'binding_requested'
    else:
        profile_status = 'anonymous'

    signals: list[str] = []
    tags = [str(item).strip().lower() for item in self._get_value(lead, 'current_tags', []) or []]
    remark_text = str(self._get_value(self._get_value(lead, 'remark_snapshot', {}), 'remark') or '').lower()
    source_state = str(self._get_value(lead, 'source_state') or '').lower()

    if any('大r' in item or 'bigr' in item for item in tags) or '大r' in remark_text:
        signals.append('tag_big_r')
        user_layer = 'big_r'
    elif any('vip' in item for item in tags) or 'vip' in remark_text or 'vip' in source_state:
        signals.append('tag_vip')
        user_layer = 'vip'
    elif self._is_recent_new_contact(self._get_value(lead, 'first_add_time')):
        signals.append('new_contact_7d')
        user_layer = 'new_user'
    else:
        user_layer = 'normal'

    if profile_status == 'bound':
        signals.append('binding_completed')

    layer_source = 'signal' if signals else 'system'

    return {
        **lead,
        'profile_status': profile_status,
        'bound_game_identity': identity,
        'user_layer': user_layer,
        'layer_source': layer_source,
        'profile_signals': signals,
        'layer_updated_at': _utcnow(),
    }
```

3. 新增 `_update_lead`，统一写回 lead：

```python
async def _update_lead(self, lead_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    await self.ap.persistence_mgr.execute_async(
        sqlalchemy.update(persistence_service_desk.WecomPrivateLead)
        .where(persistence_service_desk.WecomPrivateLead.id == lead_id)
        .values(payload)
    )
    return await self._get_lead(lead_id)
```

4. 只在两个地方触发刷新，避免逻辑散落：
   - `bootstrap_private_lead` 在 `_insert_lead` 后调用 `_refresh_lead_profile`
   - `upsert_binding_task` 在 `_upsert_binding_task_row` 后取 session/lead，再调用 `_refresh_lead_profile + _update_lead`

5. 新增一个小 helper，把“7 天内新好友”判断封装起来：

```python
@staticmethod
def _is_recent_new_contact(value: Any) -> bool:
    if not isinstance(value, datetime.datetime):
        return False
    return value >= (_utcnow() - datetime.timedelta(days=7))
```

- [ ] **Step 4: 重跑服务层测试，确认第三阶段规则稳定**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/service_desk/test_wecom_private_service.py -q
```

Expected: PASS

- [ ] **Step 5: 提交 service 规则改动**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/api/http/service/wecom_private.py \
  tests/unit_tests/service_desk/test_wecom_private_service.py
git commit -m "feat(wecomprivate): 增加用户识别分层规则"
```

---

### Task 3: 在客服台会话详情中展示第三阶段结果

**Files:**
- Modify: `web/src/app/infra/entities/api/index.ts`
- Modify: `web/src/app/home/service-desk/components/SessionDetail.tsx`
- Modify: `web/src/i18n/locales/zh-Hans.ts`
- Modify: `web/src/i18n/locales/en-US.ts`
- Test: `tests/unit_tests/service_desk/test_session_detail_api.py`

- [ ] **Step 1: 先补 contract regression 测试，锁定 session detail 返回的 lead 字段**

在 `tests/unit_tests/service_desk/test_session_detail_api.py` 的 `test_get_session_detail_returns_messages_and_overlay` 中把 mock lead 扩展为：

```python
'lead': {
    'id': 'lead-1',
    'external_userid': 'wo123',
    'profile_status': 'bound',
    'user_layer': 'vip',
    'layer_source': 'signal',
    'profile_signals': ['tag_vip', 'binding_completed'],
},
```

并追加断言：

```python
assert detail['lead']['user_layer'] == 'vip'
assert detail['lead']['layer_source'] == 'signal'
assert detail['lead']['profile_signals'] == ['tag_vip', 'binding_completed']
```

- [ ] **Step 2: 先运行后端 detail 测试，确认返回契约被锁住**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/service_desk/test_session_detail_api.py -q
```

Expected: PASS

说明：

- 这里的测试主要用于锁定 `session detail` 的返回契约
- 这一任务真正的红灯会出现在 Step 3 之后的 `npm run build`，如果 DTO、组件读取和 i18n 没同步，前端构建会直接失败

- [ ] **Step 3: 扩展 DTO 和 SessionDetail，只读展示第三阶段结果**

在 `web/src/app/infra/entities/api/index.ts` 中把 `WecomPrivateLead` 扩展为：

```ts
export interface WecomPrivateLead {
  id: string;
  external_userid: string;
  follow_user_id: string;
  source_state?: string | null;
  current_tags: string[];
  profile_status: 'anonymous' | 'binding_requested' | 'bound';
  user_layer: 'normal' | 'new_user' | 'vip' | 'big_r';
  layer_source: 'system' | 'signal';
  profile_signals: string[];
  bound_game_identity: Record<string, string | null>;
  remark_snapshot: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  layer_updated_at?: string | null;
}
```

在 `web/src/app/home/service-desk/components/SessionDetail.tsx` 中追加展示逻辑：

```tsx
const leadSignals = (lead?.profile_signals ?? []).map((item) =>
  t(`serviceDesk.workbench.profileSignal.${item}`, { defaultValue: item }),
);
```

在 lead 卡片中增加三行：

```tsx
<div>
  {t('serviceDesk.workbench.leadUserLayer')} ·{' '}
  <span className="font-medium">{lead.user_layer}</span>
</div>
<div>
  {t('serviceDesk.workbench.leadLayerSource')} ·{' '}
  <span className="font-medium">{lead.layer_source}</span>
</div>
<div>
  {t('serviceDesk.workbench.leadProfileSignals')} ·{' '}
  <span className="font-medium">
    {leadSignals.length > 0 ? leadSignals.join(', ') : '--'}
  </span>
</div>
```

并在 `zh-Hans.ts` / `en-US.ts` 中补齐：

```ts
leadUserLayer: '用户层级',
leadLayerSource: '分层来源',
leadProfileSignals: '识别信号',
profileSignal: {
  tag_vip: '命中 VIP 信号',
  tag_big_r: '命中大R信号',
  new_contact_7d: '7 天内新好友',
  binding_completed: '已完成身份绑定',
},
```

和对应英文文案：

```ts
leadUserLayer: 'User Layer',
leadLayerSource: 'Layer Source',
leadProfileSignals: 'Profile Signals',
profileSignal: {
  tag_vip: 'VIP signal matched',
  tag_big_r: 'Big-R signal matched',
  new_contact_7d: 'New contact within 7 days',
  binding_completed: 'Identity binding completed',
},
```

- [ ] **Step 4: 跑后端 detail 测试和前端构建，确认展示链路不回归**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest tests/unit_tests/service_desk/test_session_detail_api.py -q
cd /home/daisheng/code/copy_dkd/LangBot/web && npm run build
```

Expected:

- `tests/unit_tests/service_desk/test_session_detail_api.py` PASS
- `npm run build` PASS

- [ ] **Step 5: 提交第三阶段 UI 展示改动**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add web/src/app/infra/entities/api/index.ts \
  web/src/app/home/service-desk/components/SessionDetail.tsx \
  web/src/i18n/locales/zh-Hans.ts \
  web/src/i18n/locales/en-US.ts \
  tests/unit_tests/service_desk/test_session_detail_api.py
git commit -m "feat(service-desk): 展示私域用户分层结果"
```

---

### Task 4: 做第三阶段定向验证并固化边界

**Files:**
- Modify: `docs/superpowers/plans/2026-04-19-wecom-private-user-identification-layering.md`

- [ ] **Step 1: 运行第三阶段全量定向验证**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot && ./.venv/bin/pytest \
  tests/unit_tests/service_desk/test_models.py \
  tests/unit_tests/service_desk/test_wecom_private_service.py \
  tests/unit_tests/service_desk/test_session_detail_api.py -q
cd /home/daisheng/code/copy_dkd/LangBot/web && npm run build
```

Expected:

- 上述三个后端测试文件全部 PASS
- 前端构建 PASS

- [ ] **Step 2: 记录边界，防止第三阶段继续失控**

把以下结论追加回本计划底部的实施备注或任务注记中：

```md
- 第三阶段只负责 lead 识别进度和粗分层结果，不负责复杂风险评分。
- `profile_status` 只表达识别进度，不再承载 VIP / 大R 这类层级语义。
- `user_layer` 目前只服务会话详情展示和后续阶段消费，不扩散到 workbench 列表筛选。
```

- [ ] **Step 3: 提交最终验证与计划同步**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add docs/superpowers/plans/2026-04-19-wecom-private-user-identification-layering.md
git commit -m "docs(wecomprivate): 补充第三阶段实施计划"
```

---

## Self-Review

- Spec coverage:
  - 用户识别进度与粗分层结果拆开建模：Task 1 + Task 2
  - 识别闭环依赖 binding / lead 快照：Task 2
  - 客服台可见：Task 3
  - 暂不做复杂引擎、列表筛选、人工手动改层级：Scope Notes + Task 4
- Placeholder scan:
  - 无 `TODO` / `TBD`
  - 每个任务都带了具体文件、测试和命令
- Type consistency:
  - `profile_status` 固定为 `anonymous / binding_requested / bound`
  - `user_layer` 固定为 `normal / new_user / vip / big_r`
  - `layer_source` 固定为 `system / signal`

## Implementation Notes

- 第三阶段只负责 lead 识别进度和粗分层结果，不负责复杂风险评分。
- `profile_status` 只表达识别进度，不再承载 VIP / 大R 这类层级语义。
- `user_layer` 目前只服务会话详情展示和后续阶段消费，不扩散到 workbench 列表筛选。

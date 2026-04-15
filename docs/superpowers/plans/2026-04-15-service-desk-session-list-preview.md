# Service Desk Session List Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让客服台左侧会话列表直接显示最近一条对话摘要，减少人工介入前必须点进详情页才能理解上下文的问题。

**Architecture:** 保持完整历史消息仍由会话详情接口和时间线承载，只在列表接口额外聚合每个会话的最近一条监控消息，并在前端列表卡片中展示一段可读摘要。后端负责把原始监控消息转换为适合列表展示的短文本，前端只做轻展示，不重复实现消息解析逻辑。

**Tech Stack:** Python, SQLAlchemy, Quart, React, TypeScript, pytest

---

### Task 1: 为会话列表补最近消息摘要

**Files:**
- Modify: `LangBot/tests/unit_tests/service_desk/test_session_detail_api.py`
- Modify: `LangBot/src/langbot/pkg/api/http/service/service_desk.py`

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_list_workbench_sessions_includes_last_message_preview():
    from langbot.pkg.api.http.service.service_desk import ServiceDeskService

    source_items = [
        {
            'session_id': 'person_u1001',
            'bot_uuid': 'bot-1',
            'queue_status': 'manual',
            'claimed_by_user_uuid': 'user-1',
            'external_user_id': 'wx_u1001',
            'updated_at': None,
            'mode': 'manual',
        },
    ]

    async def _execute_async(statement):
        statement_text = str(statement).lower()
        if 'count(' in statement_text:
            return _FakeScalarResult(len(source_items))
        return _FakeListResult(source_items)

    ap = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(side_effect=_execute_async)
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda _model, row: dict(row))

    service = ServiceDeskService(ap)

    items, total = await service.list_workbench_sessions(bot_uuid='bot-1')

    assert total == 1
    assert items[0]['last_message_preview'] == '用户：我想了解礼包内容'
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_session_detail_api.py::test_list_workbench_sessions_includes_last_message_preview -v`
Expected: FAIL，因为当前 `list_workbench_sessions` 不会返回 `last_message_preview`

- [ ] **Step 3: 以最小实现补齐摘要聚合**

```python
async def _load_session_message_previews(self, session_ids: list[str]) -> dict[str, dict]:
    ...

def _build_message_preview(self, message_content: str, role: str | None) -> str:
    ...

async def list_workbench_sessions(...):
    ...
    preview_map = await self._load_session_message_previews(session_ids)
    for item in items:
        item.update(preview_map.get(item['session_id'], {}))
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_session_detail_api.py::test_list_workbench_sessions_includes_last_message_preview -v`
Expected: PASS

- [ ] **Step 5: 提交阶段性变更**

```bash
git add tests/unit_tests/service_desk/test_session_detail_api.py src/langbot/pkg/api/http/service/service_desk.py
git commit -m "feat(service-desk): add session list message preview"
```

### Task 2: 在前端会话卡片展示摘要

**Files:**
- Modify: `LangBot/web/src/app/infra/entities/api/index.ts`
- Modify: `LangBot/web/src/app/home/service-desk/components/SessionList.tsx`

- [ ] **Step 1: 扩展前端类型定义**

```ts
export interface ServiceDeskSession {
  ...
  last_message_preview?: string | null;
  last_message_role?: string | null;
  last_message_at?: string | null;
}
```

- [ ] **Step 2: 在列表卡片中展示摘要**

```tsx
{session.last_message_preview ? (
  <div className="mt-3 rounded-xl border border-border/60 bg-background/80 px-3 py-2 text-sm text-foreground/85 line-clamp-3">
    {session.last_message_preview}
  </div>
) : null}
```

- [ ] **Step 3: 运行前端构建验证类型与渲染通过**

Run: `cd /home/daisheng/code/copy_dkd/LangBot/web && npm run build`
Expected: PASS

- [ ] **Step 4: 提交阶段性变更**

```bash
git add web/src/app/infra/entities/api/index.ts web/src/app/home/service-desk/components/SessionList.tsx
git commit -m "feat(service-desk): show session preview in list"
```

### Task 3: 回归验证

**Files:**
- Test: `LangBot/tests/unit_tests/service_desk/test_session_detail_api.py`

- [ ] **Step 1: 运行客服台相关测试**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_session_detail_api.py -v`
Expected: PASS

- [ ] **Step 2: 再次运行前端构建**

Run: `cd /home/daisheng/code/copy_dkd/LangBot/web && npm run build`
Expected: PASS

- [ ] **Step 3: 提交最终整合变更**

```bash
git add docs/superpowers/plans/2026-04-15-service-desk-session-list-preview.md
git commit -m "docs(plan): record session list preview implementation"
```

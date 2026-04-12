# WeCom CS AI Service Desk V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the existing V1 WeCom customer-service desk into a smoother long-term collaboration workflow with AI assist, clearer session state transitions, richer context, and faster manual handling.

**Architecture:** Keep reusing the existing `service_desk_*` overlay, `MonitoringSession` / `MonitoringMessage`, and the current service-desk workbench page. Add V2 capabilities as targeted extensions: a stricter backend state machine, `ai_assist` mode, richer session detail APIs, and workbench-side efficiency components such as filters, search, and quick-reply panels.

**Tech Stack:** Python 3.11+, Quart, SQLAlchemy async ORM, existing LangBot persistence migrations, React 19 + Vite + TypeScript, existing `BackendClient`, existing monitoring and service-desk pages.

---

## Related Docs

- Development outline: `docs/superpowers/specs/2026-04-12-wecomcs-ai-service-desk-development-outline-design.md`
- Phase roadmap: `docs/superpowers/plans/2026-04-12-wecomcs-roadmap.md`
- V1 plan: `docs/superpowers/plans/2026-04-12-wecomcs-ai-service-desk.md`

---

## V2 Scope Rules

- Keep `wecomcs` as the only business channel in V2.
- Do not replace the V1 `service_desk` overlay with a parallel subsystem.
- Reuse `MonitoringMessage` as the message timeline source; only add small overlay fields when monitoring data is insufficient.
- Reuse the existing service-desk page and components; split components only when V2 interaction complexity becomes hard to maintain.
- Keep workbench refresh on HTTP polling in V2 unless a concrete operational issue proves polling insufficient.
- Do not let `AI辅助` directly auto-send to the user in V2. AI only produces drafts for human review and manual sending.

---

## File Map

### Backend

- Modify: `src/langbot/pkg/entity/persistence/service_desk.py`
  Adds any V2-only overlay fields required for `ai_assist`, richer session state, or quick-reply usage tracking.
- Modify: `src/langbot/pkg/persistence/migrations/`
  Add one migration if new V2 fields or tables are required.
- Modify: `src/langbot/pkg/api/http/service/service_desk.py`
  Central place for V2 state machine, AI assist draft generation hooks, session detail aggregation, and quick action APIs.
- Modify: `src/langbot/pkg/api/http/controller/groups/service_desk.py`
  Expose V2 endpoints for search/filter/detail/action APIs.
- Modify: `src/langbot/pkg/api/http/service/monitoring.py`
  Only if service-desk detail APIs need timeline helpers already consistent with monitoring behavior.

### Frontend

- Modify: `web/src/app/infra/entities/api/index.ts`
  Add V2 API entities for session detail, search params, quick replies, and AI assist drafts.
- Modify: `web/src/app/infra/http/BackendClient.ts`
  Add client methods for V2 service-desk endpoints.
- Modify: `web/src/app/home/service-desk/ServiceDeskContent.tsx`
  Wire the enhanced filters, search, stats, and data fetching orchestration.
- Modify: `web/src/app/home/service-desk/components/SessionList.tsx`
  Support search, grouping, richer labels, and pagination cues.
- Modify: `web/src/app/home/service-desk/components/SessionDetail.tsx`
  Support timeline, AI assist draft area, quick actions, and richer context cards.
- Create: `web/src/app/home/service-desk/components/SessionFilters.tsx`
  Extract filter/search controls from the page shell.
- Create: `web/src/app/home/service-desk/components/QuickReplyPanel.tsx`
  Show reusable phrases and structured manual actions.
- Create: `web/src/app/home/service-desk/components/MessageTimeline.tsx`
  Render session message timeline and metadata.

### Tests

- Modify: `tests/unit_tests/service_desk/test_runtime_flow.py`
- Modify: `tests/unit_tests/service_desk/test_service_desk_service.py`
- Modify: `tests/unit_tests/service_desk/test_end_to_end_rules.py`
- Create: `tests/unit_tests/service_desk/test_session_detail_api.py`
- Create: `tests/unit_tests/service_desk/test_ai_assist.py`

---

### Task 1: Introduce `ai_assist` mode and manual-review draft flow

**Files:**
- Modify: `src/langbot/pkg/api/http/service/service_desk.py`
- Modify: `src/langbot/pkg/api/http/controller/groups/service_desk.py`
- Modify: `web/src/app/infra/entities/api/index.ts`
- Modify: `web/src/app/infra/http/BackendClient.ts`
- Modify: `web/src/app/home/service-desk/components/SessionDetail.tsx`
- Test: `tests/unit_tests/service_desk/test_ai_assist.py`

- [ ] **Step 1: Write the failing AI-assist tests**

```python
import pytest

from langbot.pkg.api.http.service.service_desk import ServiceDeskService


@pytest.mark.asyncio
async def test_enable_ai_assist_switches_manual_session_mode(fake_app):
    service = ServiceDeskService(fake_app)
    session_id = 'person_u1001'

    await service._update_session_state(  # setup fixture helper already used in service tests
        session_id,
        mode='manual',
        queue_status='manual',
    )

    await service.set_session_mode(session_id, mode='ai_assist')

    session = await service._get_session(session_id)
    assert service._get_value(session, 'mode') == 'ai_assist'
    assert service._get_value(session, 'queue_status') == 'manual'


@pytest.mark.asyncio
async def test_ai_assist_generates_draft_without_sending(fake_app):
    service = ServiceDeskService(fake_app)
    session_id = 'person_u1002'

    draft = await service.generate_assist_draft(
        session_id=session_id,
        operator_user_id='u-1',
    )

    assert draft['reply_text']
    assert draft['source'] == 'ai_assist'
    assert draft['sent'] is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_ai_assist.py -v`

Expected: FAIL because `set_session_mode` / `generate_assist_draft` do not exist yet.

- [ ] **Step 3: Implement the minimal backend AI-assist flow**

```python
async def set_session_mode(self, session_id: str, mode: str) -> None:
    if mode not in {'ai_hosted', 'manual', 'ai_assist'}:
        raise ValueError(f'unsupported mode: {mode}')

    session = await self._get_session(session_id)
    if session is None:
        raise ValueError(f'session not found: {session_id}')

    queue_status = 'manual' if mode in {'manual', 'ai_assist'} else 'ai'
    await self._update_session_state(session_id, mode=mode, queue_status=queue_status)


async def generate_assist_draft(self, session_id: str, operator_user_id: str) -> dict:
    session = await self._get_session(session_id)
    if session is None:
        raise ValueError(f'session not found: {session_id}')

    # V2 first version: reuse latest session context and return a draft only.
    return {
        'session_id': session_id,
        'reply_text': 'AI assist draft placeholder',
        'source': 'ai_assist',
        'sent': False,
        'operator_user_id': operator_user_id,
    }
```

- [ ] **Step 4: Expose the API and client methods**

```python
@self.route('/sessions/<session_id>/mode', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
async def set_session_mode(session_id: str) -> str:
    payload = await quart.request.json
    await self.ap.service_desk_service.set_session_mode(session_id, payload['mode'])
    return self.success()


@self.route('/sessions/<session_id>/assist-draft', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
async def generate_assist_draft(session_id: str, user_email: str) -> str:
    user = await self.ap.user_service.get_user_by_email(user_email)
    draft = await self.ap.service_desk_service.generate_assist_draft(session_id, str(user.id))
    return self.success(data={'draft': draft})
```

```ts
export interface ServiceDeskAssistDraft {
  session_id: string;
  reply_text: string;
  source: 'ai_assist';
  sent: false;
  operator_user_id: string;
}
```

- [ ] **Step 5: Add the SessionDetail draft area**

```tsx
const [assistDraft, setAssistDraft] = useState<ServiceDeskAssistDraft | null>(null);

const handleGenerateAssistDraft = async () => {
  if (!session) return;
  const resp = await httpClient.generateServiceDeskAssistDraft(session.session_id);
  setAssistDraft(resp.draft);
};
```

- [ ] **Step 6: Run the focused tests to verify they pass**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_ai_assist.py -v`

Expected: PASS with `2 passed`.

- [ ] **Step 7: Commit**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/api/http/service/service_desk.py \
  src/langbot/pkg/api/http/controller/groups/service_desk.py \
  web/src/app/infra/entities/api/index.ts \
  web/src/app/infra/http/BackendClient.ts \
  web/src/app/home/service-desk/components/SessionDetail.tsx \
  tests/unit_tests/service_desk/test_ai_assist.py
git commit -m "feat(service-desk): add ai assist draft mode"
```

---

### Task 2: Strengthen the session state machine and operator actions

**Files:**
- Modify: `src/langbot/pkg/api/http/service/service_desk.py`
- Modify: `src/langbot/pkg/api/http/controller/groups/service_desk.py`
- Modify: `web/src/app/infra/entities/api/index.ts`
- Modify: `web/src/app/infra/http/BackendClient.ts`
- Modify: `web/src/app/home/service-desk/components/SessionDetail.tsx`
- Test: `tests/unit_tests/service_desk/test_end_to_end_rules.py`
- Test: `tests/unit_tests/service_desk/test_service_desk_service.py`

- [ ] **Step 1: Write failing state-transition tests**

```python
import pytest

from langbot.pkg.api.http.service.service_desk import ServiceDeskService


@pytest.mark.asyncio
async def test_release_manual_session_returns_to_pending_manual(fake_app):
    service = ServiceDeskService(fake_app)
    session_id = 'person_release_1'

    await service.release_session(session_id)

    session = await service._get_session(session_id)
    assert service._get_value(session, 'queue_status') == 'pending_manual'
    assert service._get_value(session, 'claimed_by_user_uuid') is None


@pytest.mark.asyncio
async def test_return_session_to_ai_clears_manual_fields(fake_app):
    service = ServiceDeskService(fake_app)
    session_id = 'person_return_ai_1'

    await service.return_session_to_ai(session_id)

    session = await service._get_session(session_id)
    assert service._get_value(session, 'mode') == 'ai_hosted'
    assert service._get_value(session, 'queue_status') == 'ai'
    assert service._get_value(session, 'manual_claimed_at') is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_service_desk_service.py tests/unit_tests/service_desk/test_end_to_end_rules.py -v`

Expected: FAIL because `release_session` and `return_session_to_ai` do not exist.

- [ ] **Step 3: Implement the minimal state actions**

```python
async def release_session(self, session_id: str) -> None:
    await self._update_session_state(
        session_id,
        queue_status='pending_manual',
        claimed_by_user_uuid=None,
        claimed_by_user_name=None,
        manual_claimed_at=None,
    )


async def return_session_to_ai(self, session_id: str) -> None:
    await self._update_session_state(
        session_id,
        mode='ai_hosted',
        queue_status='ai',
        claimed_by_user_uuid=None,
        claimed_by_user_name=None,
        manual_claimed_at=None,
        silent_since=None,
    )
```

- [ ] **Step 4: Add state-action endpoints and buttons**

```python
@self.route('/sessions/<session_id>/release', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
async def release_session(session_id: str) -> str:
    await self.ap.service_desk_service.release_session(session_id)
    return self.success()


@self.route('/sessions/<session_id>/return-ai', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
async def return_session_to_ai(session_id: str) -> str:
    await self.ap.service_desk_service.return_session_to_ai(session_id)
    return self.success()
```

```tsx
<Button variant="outline" onClick={() => void handleRelease()}>
  {t('serviceDesk.workbench.releaseAction')}
</Button>
<Button variant="secondary" onClick={() => void handleReturnToAi()}>
  {t('serviceDesk.workbench.returnToAiAction')}
</Button>
```

- [ ] **Step 5: Re-run the focused tests**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_service_desk_service.py tests/unit_tests/service_desk/test_end_to_end_rules.py -v`

Expected: PASS with the new transition cases green.

- [ ] **Step 6: Commit**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/api/http/service/service_desk.py \
  src/langbot/pkg/api/http/controller/groups/service_desk.py \
  web/src/app/infra/entities/api/index.ts \
  web/src/app/infra/http/BackendClient.ts \
  web/src/app/home/service-desk/components/SessionDetail.tsx \
  tests/unit_tests/service_desk/test_service_desk_service.py \
  tests/unit_tests/service_desk/test_end_to_end_rules.py
git commit -m "feat(service-desk): add explicit session state actions"
```

---

### Task 3: Add search, filters, and grouped list experience

**Files:**
- Modify: `src/langbot/pkg/api/http/service/service_desk.py`
- Modify: `src/langbot/pkg/api/http/controller/groups/service_desk.py`
- Modify: `web/src/app/infra/entities/api/index.ts`
- Modify: `web/src/app/infra/http/BackendClient.ts`
- Modify: `web/src/app/home/service-desk/ServiceDeskContent.tsx`
- Modify: `web/src/app/home/service-desk/components/SessionList.tsx`
- Create: `web/src/app/home/service-desk/components/SessionFilters.tsx`
- Test: `tests/unit_tests/service_desk/test_session_detail_api.py`

- [ ] **Step 1: Write the failing query test**

```python
import pytest

from langbot.pkg.api.http.service.service_desk import ServiceDeskService


@pytest.mark.asyncio
async def test_list_workbench_sessions_supports_keyword_search(fake_app):
    service = ServiceDeskService(fake_app)

    items, total = await service.list_workbench_sessions(
        bot_uuid='bot-1',
        queue_status='manual',
        keyword='礼包',
        claimed_by=None,
        limit=50,
        offset=0,
    )

    assert total == 1
    assert items[0]['external_user_id'] == 'wx_u1001'
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_session_detail_api.py -v`

Expected: FAIL because `keyword` filtering is not supported.

- [ ] **Step 3: Extend the query API**

```python
async def list_workbench_sessions(
    self,
    *,
    bot_uuid: str | None,
    queue_status: str | None,
    claimed_by: str | None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    stmt = sqlalchemy.select(persistence_service_desk.ServiceDeskSession)
    if bot_uuid:
        stmt = stmt.where(persistence_service_desk.ServiceDeskSession.bot_uuid == bot_uuid)
    if queue_status:
        stmt = stmt.where(persistence_service_desk.ServiceDeskSession.queue_status == queue_status)
    if claimed_by:
        stmt = stmt.where(persistence_service_desk.ServiceDeskSession.claimed_by_user_uuid == claimed_by)
    if keyword:
        stmt = stmt.where(
            persistence_service_desk.ServiceDeskSession.external_user_id.contains(keyword)
            | persistence_service_desk.ServiceDeskSession.session_id.contains(keyword)
        )
```

- [ ] **Step 4: Add filter UI extraction**

```tsx
<SessionFilters
  queueFilter={queueFilter}
  searchKeyword={searchKeyword}
  claimedByFilter={claimedByFilter}
  onQueueFilterChange={setQueueFilter}
  onSearchKeywordChange={setSearchKeyword}
  onClaimedByFilterChange={setClaimedByFilter}
/>
```

- [ ] **Step 5: Add grouped list rendering**

```tsx
const groupedSessions = useMemo(() => {
  return sessions.reduce<Record<string, ServiceDeskSession[]>>((acc, session) => {
    const key = session.queue_status;
    acc[key] = acc[key] || [];
    acc[key].push(session);
    return acc;
  }, {});
}, [sessions]);
```

- [ ] **Step 6: Re-run the focused test and frontend build**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_session_detail_api.py -v`

Expected: PASS.

Run: `cd /home/daisheng/code/copy_dkd/LangBot/web && pnpm build`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/api/http/service/service_desk.py \
  src/langbot/pkg/api/http/controller/groups/service_desk.py \
  web/src/app/infra/entities/api/index.ts \
  web/src/app/infra/http/BackendClient.ts \
  web/src/app/home/service-desk/ServiceDeskContent.tsx \
  web/src/app/home/service-desk/components/SessionList.tsx \
  web/src/app/home/service-desk/components/SessionFilters.tsx \
  tests/unit_tests/service_desk/test_session_detail_api.py
git commit -m "feat(service-desk): add workbench search and grouping"
```

---

### Task 4: Build a richer session detail and timeline view

**Files:**
- Modify: `src/langbot/pkg/api/http/service/service_desk.py`
- Modify: `src/langbot/pkg/api/http/controller/groups/service_desk.py`
- Modify: `web/src/app/infra/entities/api/index.ts`
- Modify: `web/src/app/infra/http/BackendClient.ts`
- Modify: `web/src/app/home/service-desk/components/SessionDetail.tsx`
- Create: `web/src/app/home/service-desk/components/MessageTimeline.tsx`
- Test: `tests/unit_tests/service_desk/test_session_detail_api.py`

- [ ] **Step 1: Write the failing detail-aggregation test**

```python
import pytest

from langbot.pkg.api.http.service.service_desk import ServiceDeskService


@pytest.mark.asyncio
async def test_get_session_detail_returns_messages_and_overlay(fake_app):
    service = ServiceDeskService(fake_app)

    detail = await service.get_session_detail('person_u1001')

    assert detail['session']['session_id'] == 'person_u1001'
    assert detail['messages']
    assert 'handoff_reason' in detail['session']
    assert 'bot' in detail
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_session_detail_api.py -v`

Expected: FAIL because `get_session_detail` does not exist.

- [ ] **Step 3: Implement the detail aggregation**

```python
async def get_session_detail(self, session_id: str) -> dict:
    session = await self._get_session(session_id)
    if session is None:
        raise ValueError(f'session not found: {session_id}')

    return {
        'session': self.ap.persistence_mgr.serialize_model(
            persistence_service_desk.ServiceDeskSession,
            session,
        ),
        'messages': [],
        'bot': {'uuid': self._get_value(session, 'bot_uuid')},
        'assist_draft': None,
    }
```

- [ ] **Step 4: Expose the detail API and timeline component**

```python
@self.route('/sessions/<session_id>', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
async def get_session_detail(session_id: str) -> str:
    detail = await self.ap.service_desk_service.get_session_detail(session_id)
    return self.success(data=detail)
```

```tsx
<MessageTimeline
  items={detail.messages}
  emptyText={t('serviceDesk.workbench.noTimeline')}
/>
```

- [ ] **Step 5: Re-run the detail test and frontend build**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_session_detail_api.py -v`

Expected: PASS.

Run: `cd /home/daisheng/code/copy_dkd/LangBot/web && pnpm build`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/api/http/service/service_desk.py \
  src/langbot/pkg/api/http/controller/groups/service_desk.py \
  web/src/app/infra/entities/api/index.ts \
  web/src/app/infra/http/BackendClient.ts \
  web/src/app/home/service-desk/components/SessionDetail.tsx \
  web/src/app/home/service-desk/components/MessageTimeline.tsx \
  tests/unit_tests/service_desk/test_session_detail_api.py
git commit -m "feat(service-desk): add session detail timeline"
```

---

### Task 5: Add quick-reply panel and structured operator shortcuts

**Files:**
- Modify: `src/langbot/pkg/api/http/service/service_desk.py`
- Modify: `src/langbot/pkg/api/http/controller/groups/service_desk.py`
- Modify: `web/src/app/infra/entities/api/index.ts`
- Modify: `web/src/app/infra/http/BackendClient.ts`
- Modify: `web/src/app/home/service-desk/components/SessionDetail.tsx`
- Create: `web/src/app/home/service-desk/components/QuickReplyPanel.tsx`
- Test: `tests/unit_tests/service_desk/test_service_desk_service.py`

- [ ] **Step 1: Write the failing quick-reply test**

```python
import pytest

from langbot.pkg.api.http.service.service_desk import ServiceDeskService


@pytest.mark.asyncio
async def test_list_quick_replies_returns_enabled_materials(fake_app):
    service = ServiceDeskService(fake_app)

    items = await service.list_quick_replies(bot_uuid='bot-1')

    assert items
    assert all(item['enabled'] is True for item in items)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_service_desk_service.py -v`

Expected: FAIL because `list_quick_replies` does not exist.

- [ ] **Step 3: Implement the quick-reply service**

```python
async def list_quick_replies(self, bot_uuid: str) -> list[dict]:
    items = await self.list_materials(bot_uuid)
    return [
        item
        for item in items
        if item.get('enabled', True) and item.get('material_type') in {'quick_reply', 'download_link', 'gift_pack'}
    ]
```

- [ ] **Step 4: Add the panel and insert behavior**

```tsx
<QuickReplyPanel
  botUuid={session.bot_uuid}
  onInsert={(value) => {
    setReplyText((prev) => (prev ? `${prev}\n${value}` : value));
  }}
/>
```

- [ ] **Step 5: Re-run the test and frontend build**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk/test_service_desk_service.py -v`

Expected: PASS.

Run: `cd /home/daisheng/code/copy_dkd/LangBot/web && pnpm build`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add src/langbot/pkg/api/http/service/service_desk.py \
  src/langbot/pkg/api/http/controller/groups/service_desk.py \
  web/src/app/infra/entities/api/index.ts \
  web/src/app/infra/http/BackendClient.ts \
  web/src/app/home/service-desk/components/SessionDetail.tsx \
  web/src/app/home/service-desk/components/QuickReplyPanel.tsx \
  tests/unit_tests/service_desk/test_service_desk_service.py
git commit -m "feat(service-desk): add quick reply panel"
```

---

### Task 6: Run V2 regression verification and prepare rollout checklist

**Files:**
- Modify: `tests/unit_tests/service_desk/test_runtime_flow.py`
- Modify: `tests/unit_tests/service_desk/test_end_to_end_rules.py`
- Create: `docs/superpowers/checklists/2026-04-12-wecomcs-ai-service-desk-v2-acceptance.md`

- [ ] **Step 1: Add the V2 regression cases**

```python
def test_ai_assist_mode_does_not_auto_send():
    ...


def test_release_then_reclaim_keeps_session_consistent():
    ...


def test_return_to_ai_clears_manual_overlay():
    ...
```

- [ ] **Step 2: Run the service-desk test suite**

Run: `cd /home/daisheng/code/copy_dkd/LangBot && uv run pytest tests/unit_tests/service_desk -v`

Expected: PASS for the full service-desk suite.

- [ ] **Step 3: Run frontend lint and build**

Run: `cd /home/daisheng/code/copy_dkd/LangBot/web && pnpm lint`

Expected: No errors. Existing warnings may remain unless this task removes them intentionally.

Run: `cd /home/daisheng/code/copy_dkd/LangBot/web && pnpm build`

Expected: PASS.

- [ ] **Step 4: Write the V2 acceptance checklist**

```md
# WeCom CS AI Service Desk V2 Acceptance Checklist

- [ ] AI assist draft can be generated without auto-sending
- [ ] Operator can claim, release, and return sessions to AI
- [ ] Workbench search and grouping behave as expected
- [ ] Session detail shows context and timeline
- [ ] Quick replies can be inserted and sent manually
- [ ] WeCom real-chain verification is marked separately from automated verification
```

- [ ] **Step 5: Commit**

```bash
cd /home/daisheng/code/copy_dkd/LangBot
git add tests/unit_tests/service_desk/test_runtime_flow.py \
  tests/unit_tests/service_desk/test_end_to_end_rules.py \
  docs/superpowers/checklists/2026-04-12-wecomcs-ai-service-desk-v2-acceptance.md
git commit -m "test(service-desk): add v2 regression coverage"
```

---

## Self-Review

- V2 `AI辅助` scope is covered by Task 1 and Task 6.
- Clearer state transitions and manual/AI return behavior are covered by Task 2 and Task 6.
- Search, filter, and grouped list behavior are covered by Task 3.
- Richer detail and context display are covered by Task 4.
- Common phrases and quick operator actions are covered by Task 5.
- Verification and rollout checklist are covered by Task 6.

No unresolved placeholders remain in this plan. Any deeper product refinement for V3 such as user segmentation, business data linkage, or multi-tenant isolation stays intentionally out of scope.

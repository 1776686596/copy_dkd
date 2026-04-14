# Local Agent Demo Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把流水线里的内置 Agent 改成适合演示的业务配置页，并让业务字段驱动 system prompt。

**Architecture:** 后端新增一个独立的 local-agent prompt 组装模块，避免直接在 `preproc.py` 中堆逻辑，也绕开测试导入循环。前端保留现有流水线结构，但对 `local-agent` 阶段做定制渲染，只展示业务字段和知识库，把原始 prompt 收进默认关闭的高级配置。

**Tech Stack:** Python、pytest、React、react-hook-form、项目现有 shadcn/ui 组件、YAML/JSON 模板配置

---

### Task 1: 后端 prompt 组装

**Files:**
- Create: `src/langbot/pkg/pipeline/preproc/local_agent_prompt.py`
- Modify: `src/langbot/pkg/pipeline/preproc/preproc.py`
- Test: `tests/unit_tests/pipeline/test_local_agent_prompt.py`

- [ ] **Step 1: 写失败测试并指向独立 helper 模块**

```python
from langbot.pkg.pipeline.preproc.local_agent_prompt import (
    build_local_agent_prompt_config,
)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd LangBot && ./.venv/bin/pytest tests/unit_tests/pipeline/test_local_agent_prompt.py -v`
Expected: FAIL，报 `ModuleNotFoundError` 或 `ImportError`，说明 helper 还未实现

- [ ] **Step 3: 实现最小 helper**

```python
def build_local_agent_prompt_config(local_agent_config: dict) -> list[dict]:
    ...
```

- [ ] **Step 4: 在 `PreProcessor` 中接入 helper**

```python
conversation = await self.ap.sess_mgr.get_conversation(
    query,
    session,
    build_local_agent_prompt_config(query.pipeline_config['ai']['local-agent']),
    query.pipeline_uuid,
    query.bot_uuid,
)
```

- [ ] **Step 5: 重新运行测试确认通过**

Run: `cd LangBot && ./.venv/bin/pytest tests/unit_tests/pipeline/test_local_agent_prompt.py -v`
Expected: PASS

### Task 2: 流水线配置元数据

**Files:**
- Modify: `src/langbot/templates/metadata/pipeline/ai.yaml`
- Modify: `src/langbot/templates/default-pipeline-config.json`

- [ ] **Step 1: 新增业务字段**

```yaml
- name: application-settings
  type: text
- name: application-description
  type: string
- name: opening-intro
  type: text
```

- [ ] **Step 2: 增加高级配置开关并隐藏原始 prompt**

```yaml
- name: show-advanced-prompt
  type: boolean
  default: false

- name: prompt
  show_if:
    field: show-advanced-prompt
    operator: eq
    value: true
```

- [ ] **Step 3: 给默认流水线填入演示用传奇客服配置**

```json
"application-description": "传奇游戏 AI 客服"
```

### Task 3: 流水线前端演示布局

**Files:**
- Modify: `web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx`

- [ ] **Step 1: 让 stage patch 合并已有值**

```tsx
const currentStageValues = currentValues[stageName] || {};
```

- [ ] **Step 2: 为 `local-agent` 做定制渲染**

```tsx
if (formName === 'ai' && stage.name === 'local-agent') {
  return <Card>...</Card>;
}
```

- [ ] **Step 3: 主界面只展示业务字段与知识库**

```tsx
<Textarea />
<Input />
<DynamicFormComponent itemConfigList={knowledgeConfig} ... />
```

- [ ] **Step 4: 用折叠区承载高级 prompt**

```tsx
<Collapsible open={showAdvanced}>
  <CollapsibleContent>...</CollapsibleContent>
</Collapsible>
```

### Task 4: 文案与验证

**Files:**
- Modify: `web/src/i18n/locales/zh-Hans.ts`
- Modify: `web/src/i18n/locales/en-US.ts`

- [ ] **Step 1: 补业务字段文案**

```ts
localAgentApplicationSettings: '应用设定'
```

- [ ] **Step 2: 跑后端测试**

Run: `cd LangBot && ./.venv/bin/pytest tests/unit_tests/pipeline/test_local_agent_prompt.py tests/unit_tests/pipeline/test_local_faq.py tests/unit_tests/knowledge/test_local_faq_backend.py -v`
Expected: PASS

- [ ] **Step 3: 跑前端构建**

Run: `cd LangBot/web && npm run build`
Expected: build success

- [ ] **Step 4: 提交到当前分支**

```bash
git add docs/superpowers/plans/2026-04-14-local-agent-demo-config.md \
  src/langbot/pkg/pipeline/preproc/local_agent_prompt.py \
  src/langbot/pkg/pipeline/preproc/preproc.py \
  src/langbot/templates/metadata/pipeline/ai.yaml \
  src/langbot/templates/default-pipeline-config.json \
  web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx \
  web/src/i18n/locales/zh-Hans.ts \
  web/src/i18n/locales/en-US.ts \
  tests/unit_tests/pipeline/test_local_agent_prompt.py
git commit -m "feat(pipeline): add demo-friendly local agent config"
git push
```

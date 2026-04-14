# Pipeline Local Agent Role Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让流水线页面中的 `local-agent` 直接呈现并可编辑“传奇游戏客服角色设定”，同时保留知识库绑定入口。

**Architecture:** 继续复用现有 `ai.local-agent.prompt` 和 `knowledge-bases` 字段，只调整默认模板与前端展示文案，不新增底层配置结构。前端通过已有动态表单 schema 自动渲染，必要时再补一层轻量说明 UI。

**Tech Stack:** React 19、TypeScript、动态表单 schema、Quart 后端模板资源

---

### Task 1: 更新 local-agent 默认角色模板

**Files:**
- Modify: `src/langbot/templates/default-pipeline-config.json`

- [ ] **Step 1: 写入传奇客服默认 system prompt**

把 `ai.local-agent.prompt[0].content` 从通用助手文案替换为传奇客服模板，保留：

```json
[
  {
    "role": "system",
    "content": "你是【传奇手游】企微专属智能客服。严格优先依据知识库回复；同一问题若存在多个候选答案，选择其中 1 个输出，避免重复。语气活泼亲切，贴近老玩家。围绕老玩家召回、新游推介、版本匹配、下载指引四类场景服务。优先推荐与玩家过往偏好一致的版本，暂不主动推送复古版本。单职业无限刀版本对应御龙无双：https://g.guayou.com/?ct=shouyou&ac=h5&gid=63&member=639；超变版本对应战谷：https://g.guayou.com/?ct=shouyou&ac=h5&gid=68&member=217。若发送下载链接，结尾追加：麻烦老板按区服：XX区 角色名：XXX的格式发送给我。若触发人工介入、高意向深度咨询、下载注册障碍、负面质疑、玩家提交区服角色名、知识库未覆盖等情况，只回复：稍等下哈。严格执行敏感词过滤，输出中将“福利”统一替换为“福～利”。禁止脱离知识库编造答案。"
  }
]
```

- [ ] **Step 2: 运行前端构建确认模板变更不影响编译**

Run: `cd LangBot/web && npm run build`
Expected: `tsc && vite build` 成功

### Task 2: 调整流水线 AI metadata 的标签与说明

**Files:**
- Modify: `src/langbot/templates/metadata/pipeline/ai.yaml`

- [ ] **Step 1: 修改 local-agent prompt 字段文案**

把 `prompt` 的展示信息改成更适合演示的表述：

```yaml
- name: prompt
  label:
    en_US: Customer Service Role
    zh_Hans: 客服角色设定
  description:
    en_US: Edit the system role used by the local agent. For demo use, keep the first system entry and adjust the script in the frontend directly.
    zh_Hans: 这里配置内置 Agent 的 system 角色，可直接在前端修改传奇客服话术。演示时建议仅维护第一条 system 内容。
  type: prompt-editor
  required: true
```

- [ ] **Step 2: 修改 knowledge-bases 字段文案**

强调它与角色设定共同生效：

```yaml
- name: knowledge-bases
  label:
    en_US: Customer Service Knowledge Bases
    zh_Hans: 客服知识库
  description:
    en_US: Bind the FAQ knowledge bases used together with the role script.
    zh_Hans: 绑定和客服角色设定一起生效的知识库，推荐选择本地 FAQ 问答库。
```

- [ ] **Step 3: 保持字段名与类型不变**

确认只改 `label`、`description`、`default`，不改：

```yaml
name: prompt
type: prompt-editor

name: knowledge-bases
type: knowledge-base-multi-selector
```

### Task 3: 在流水线页面增加轻量说明，提升演示感

**Files:**
- Modify: `web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx`

- [ ] **Step 1: 在 local-agent 配置卡片顶部增加说明块**

在 `renderDynamicForms` 里，针对 `formName === 'ai' && stage.name === 'local-agent'`
时，在 `DynamicFormComponent` 前插入一段说明 UI：

```tsx
<div className="rounded-lg border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
  当前页可直接维护传奇游戏客服的角色设定与知识库绑定。模型回复时会同时参考“客服角色设定”和已绑定知识库内容。
</div>
```

- [ ] **Step 2: 保持现有动态表单提交逻辑不变**

不要改动：

```tsx
onSubmit={(values) => {
  handleDynamicFormEmit(formName, stage.name, values);
}}
```

- [ ] **Step 3: 运行前端构建验证页面改动**

Run: `cd LangBot/web && npm run build`
Expected: 构建成功

### Task 4: 验证与提交

**Files:**
- Modify: `src/langbot/templates/default-pipeline-config.json`
- Modify: `src/langbot/templates/metadata/pipeline/ai.yaml`
- Modify: `web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx`

- [ ] **Step 1: 运行最终验证**

Run: `cd LangBot/web && npm run build`
Expected: 构建成功

- [ ] **Step 2: 检查工作区**

Run: `cd LangBot && git status --short --branch`
Expected: 只包含本次相关文件和已知无关锁文件

- [ ] **Step 3: 提交本次改动**

```bash
cd LangBot
git add src/langbot/templates/default-pipeline-config.json src/langbot/templates/metadata/pipeline/ai.yaml web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx docs/superpowers/specs/2026-04-14-pipeline-local-agent-role-editor-design.md docs/superpowers/plans/2026-04-14-pipeline-local-agent-role-editor.md
git commit -m "feat(pipeline): expose local-agent role editor for game客服"
```

- [ ] **Step 4: 推送到当前备份分支**

Run: `cd LangBot && git push`
Expected: 推送到 `copy_dkd/push-copy-dkd-master` 成功

# 流水线本地 Agent 角色设定前端呈现设计

## 目标

在 `Pipeline -> AI 能力 -> local-agent` 中，把当前可编辑的 `prompt`
能力明确呈现为“客服角色设定”，用于明天演示传奇游戏 AI 客服场景。

## 背景

当前项目已经支持通过 `ai.local-agent.prompt` 向模型注入 system prompt，
前端也已有 `prompt-editor` 组件，但页面上的标签和说明偏通用，
不够适合直接演示“传奇游戏客服角色配置 + 知识库绑定”的业务场景。

## 设计决策

### 1. 继续复用 local-agent 的 prompt-editor

不新增新的底层配置字段，仍然以 `ai.local-agent.prompt` 作为唯一角色设定来源。

这样可以保证：

- 后端注入逻辑无需改动；
- 现有流水线保存/加载逻辑无需迁移；
- 前端依然可直接查看、修改、保存。

### 2. 在前端把 prompt 明确展示为“客服角色设定”

通过调整 AI metadata 中 `local-agent.prompt` 的标签、描述和默认内容，
让流水线页面直接把它呈现为可编辑的客服角色卡片。

预期效果：

- 用户进入 `Pipeline -> AI 能力 -> 内置 Agent` 后，
  能直接看到“客服角色设定”而不是抽象的“提示词”；
- 角色内容默认是一版适合传奇游戏客服演示的 system prompt；
- 用户可以在前端直接修改这段内容。

### 3. 默认模板聚焦演示场景

默认模板保留以下约束：

- 老玩家召回/新游推介语气；
- 严格优先知识库；
- 人工转接固定回复“稍等下哈”；
- 敏感词过滤与“福利 -> 福～利”替换；
- 下载链接匹配仅保留单职业无限刀 / 超变；
- 暂不主动推复古版本。

同时压缩为适合 system prompt 执行的长度，避免过长影响模型稳定性。

### 4. 知识库绑定继续使用现有字段

不新增新的“客服知识库”配置结构，继续复用
`ai.local-agent.knowledge-bases` 多知识库选择器。

但在说明文案上会强调：

- 推荐绑定本地 FAQ 知识库；
- 当前角色设定与知识库会共同影响回复。

## 实现范围

- 修改 `default-pipeline-config.json` 中 local-agent 默认 prompt。
- 修改 `metadata/pipeline/ai.yaml` 中 local-agent 的 prompt/knowledge-bases
  标签与说明。
- 如有必要，在 `PipelineFormComponent` 中为 local-agent 增加一段更清晰的
  演示说明文案，但不改变底层数据结构。

## 非目标

- 不新增新的数据库字段；
- 不改动 local-agent 的核心推理逻辑；
- 不实现“模板库”“多行业切换”等扩展功能；
- 不把角色设定移动到 Bot 或客服台页面。

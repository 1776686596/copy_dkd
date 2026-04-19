# 企微私域 AI 自动接待标准版后台设计

## 文档定位

这份设计文档定义的是企微私域客服蓝图中的第 `2` 步能力：

- `AI 自动接待（智能客服）`

本次设计不是路线图里的“Phase 2 工作台优化”，而是流程图中的第二个业务环节。目标是在现有 phase1 最小闭环之上，把 `wecomprivate` 场景的 AI 自动接待升级成一套可后台配置、可运营、可复用的传奇品类接待能力。

这份文档解决的是：

1. `wecomprivate` 场景下，AI 自动接待要提供哪些后台配置
2. 配置应该挂在 `Pipeline` 还是 `Bot / 客服台配置`
3. 运行时如何在欢迎、FAQ、补问、转下一环之间做统一决策
4. 第一版需要新增哪些数据模型、接口和前端配置区

这份文档不是实施清单。具体编码任务拆分放在后续 implementation plan 中。

---

## 一、已确认前提

基于当前对话与已有蓝图，后续实现遵循以下前提：

1. 当前只服务 `wecomprivate`，不把 `wecomweb`、`wecomcs` 一起纳入这一版
2. 这套后台面向传奇品类的多游戏/多版本运营，不追求跨行业通用
3. 不新建“客服 SaaS 通用流程引擎”，但要支持传奇矩阵内复用
4. `bot = 接待入口`，`pipeline = 接待模板`，`bot config = 入口规则覆盖`
5. 第一版采用“后台可配置”的产品形态，不接受仅靠代码或固定规则运行
6. 第一版采用“标准版”范围：
   - 欢迎语、知识库、兜底语可配置
   - 补问字段、补问触发条件可配置
   - 何时继续 AI、何时转后续识别/分流可配置
7. 第一版不新建独立模板中心，不做可视化流程编排器

---

## 二、产品目标与非目标

### 2.1 目标

构建一套只服务 `wecomprivate` 的 AI 自动接待后台，使运营可以在后台完成以下工作：

- 为某个企微私域入口绑定一套传奇接待模板
- 为该入口配置欢迎、FAQ、补问、兜底、转下一环规则
- 让用户在进入私域接待后，系统能按配置完成自动接待闭环
- 让后续识别、分流、人工协作拿到结构化上下文，而不是从零读会话

### 2.2 非目标

本次设计不把以下内容纳入当前实现范围：

- 不做 `wecomweb` / `wecomcs` 通用化接入
- 不做独立模板中心或跨 bot 模板引用系统
- 不做可视化状态机或 BPM 式流程编排
- 不做完整用户分层、复杂风险评分、运营闭环
- 不重构现有 `service_desk` / `Pipeline` 的总体架构

---

## 三、推荐方案

### 方案 A：继续复用现有字段，最小补丁式扩展

核心思路：

- `Pipeline` 继续承载欢迎语、知识库、角色设定
- `ServiceDeskBotConfig` 只再补几个简单字段

优点：

- 改动最小
- 实现最快

缺点：

- AI 自动接待配置和客服台配置会继续混杂
- 后续很难清晰区分“AI 接待规则”和“人工协作规则”

### 方案 B：混合模式下引入明确的 `wecomprivate reception config`

核心思路：

- `Pipeline` 承载通用 AI 内容能力
- `Bot / 客服台配置` 承载 `wecomprivate` 的入口级接待规则
- 新增独立的私域接待配置对象，避免把所有字段硬塞进 `ServiceDeskBotConfig`

优点：

- 配置边界清楚
- 符合产品后台心智
- 适合后续在传奇矩阵中复用

缺点：

- 比最小补丁式实现多一层模型和接口

### 方案 C：新建独立 AI 自动接待配置中心

核心思路：

- 不再依附 `Pipeline` 和 `Bot / 客服台配置`
- 直接做独立模块与独立页面

优点：

- 模块形态最完整

缺点：

- 第一版过重
- 会与现有 `Pipeline` / `service_desk` 配置职责冲突

### 结论

本次采用 `方案 B：Pipeline 放通用接待模板，Bot / 客服台放 wecomprivate 接待规则，并新增明确的私域接待配置对象`。

---

## 四、核心产品模型

### 4.1 入口、模板、规则覆盖

第一版按以下三层模型组织：

- `bot = 接待入口`
  - 对应真实的企微私域入口、二维码入口、接待身份
- `pipeline = 接待模板`
  - 对应某个游戏/版本的 AI 接待模板
- `bot config = 入口规则覆盖`
  - 对应该入口自己的自动接待规则

### 4.2 传奇品类场景下的解释

对于当前业务，推荐使用方式是：

- 一个稳定入口一个 `bot`
- 一款游戏或一个接待方向一套 `pipeline`
- 同一模板可以通过复制后轻量修改，适配不同传奇版本

这意味着：

- 不把“一个版本必须对应一个 bot”写死
- 但要求每个 `bot` 始终绑定一套明确的接待模板

### 4.3 后台配置边界

`Pipeline` 负责“AI 怎么说”：

- 客服角色设定
- 开场欢迎语
- 知识库绑定
- 本地 FAQ 直答能力
- 通用 prompt 级口径控制

`wecomprivate` 的 bot 级配置负责“这个入口怎么接”：

- 是否启用 AI 自动接待
- 未解决轮次阈值
- 兜底回复文案
- 需要补问哪些字段
- 哪些场景触发补问
- 哪些场景转后续识别/分流
- 用户要求人工时是否直接转出

---

## 五、后台配置设计

### 5.1 Pipeline 侧配置

第一版继续复用现有 `Pipeline -> AI -> local-agent` 配置，不新增第二套模板编辑器。

继续使用的字段包括：

- `opening-intro`
- `prompt`
- `knowledge-bases`
- `local-faq-enabled`
- `local-faq-path`
- `local-faq-min-similarity`

这里的定位被明确为：

- `Pipeline` 是传奇接待模板
- 模板决定欢迎语、角色设定和知识来源

### 5.2 Bot / 客服台侧配置

在现有 `BotDeskConfigForm` 中，仅对 `wecomprivate` bot 展示一块新的 `AI 自动接待配置`。

标准版第一版建议包含以下字段：

- `reception_enabled`
  - 是否启用 AI 自动接待
- `welcome_enabled`
  - 是否对欢迎事件发送首轮欢迎
- `fallback_unresolved_count`
  - 连续未解决多少轮后进入兜底/转下一环
- `fallback_reply_text`
  - 达到兜底阈值后的回复文案
- `binding_required_fields`
  - 允许选择：`uid` / `server` / `role_name`
- `binding_trigger_keywords`
  - 命中后触发补问
- `binding_prompt_text`
  - 触发补问时发送的引导文案
- `human_handoff_direct_enabled`
  - 用户要求人工时是否直接进入下一环

### 5.3 继续复用的客服台通用字段

以下字段仍保留在现有 `ServiceDeskBotConfig` 中，不重复造轮子：

- `version_label`
- `handoff_keywords`
- `manual_timeout_seconds`
- `enabled`
- `fallback_unresolved_count`

其中：

- `enabled` 表示整个客服台入口是否启用
- `reception_enabled` 表示该入口是否启用 AI 自动接待
- `fallback_unresolved_count` 在第一版 UI 中被重新明确归类到 `AI 自动接待配置`，但模型层仍可继续沿用现有字段

### 5.4 后台交互约束

为了避免配置割裂，前端需要补 3 类提示：

1. 当前绑定 `pipeline` 的摘要
   - 模板名
   - 欢迎语预览
   - 知识库数量
2. 跳转入口
   - 从 bot 配置页跳到对应 pipeline 编辑页
3. 说明文案
   - 明确告知：
   - `Pipeline` 决定 AI 内容能力
   - `Bot 配置` 决定该入口的接待编排规则

---

## 六、数据模型设计

### 6.1 新增 `WecomPrivateReceptionConfig`

第一版建议新增一张专门面向私域自动接待的表：

- 表名：`wecom_private_reception_configs`

建议字段：

- `bot_uuid`
- `reception_enabled`
- `welcome_enabled`
- `fallback_reply_text`
- `binding_required_fields`
- `binding_trigger_keywords`
- `binding_prompt_text`
- `human_handoff_direct_enabled`
- `created_at`
- `updated_at`

设计目的：

- 避免把 `wecomprivate` 特有接待规则全部塞进 `ServiceDeskBotConfig`
- 让“AI 自动接待配置”成为独立、可读、可扩展的领域对象

### 6.2 补充绑定任务字段

现有 `WecomPrivateBindingTask` 只有：

- `provided_uid`
- `provided_server`

第一版应补充：

- `provided_role_name`

原因：

- 传奇场景下，`角色名` 是高频补问字段
- 如果后台允许配置 `role_name`，数据层必须能完整落库

### 6.3 继续复用的现有模型

第一版继续复用以下模型，不新增额外会话状态表：

- `ServiceDeskSession`
  - 承载当前会话状态
- `WecomPrivateBindingTask`
  - 承载补问/补录状态
- `WecomPrivateRoutingDecision`
  - 承载进入后续识别/分流的决策记录

---

## 七、运行时闭环设计

### 7.1 决策顺序

每次 `wecomprivate` 消息进入时，统一按以下顺序决策：

1. 定位当前 `bot`
2. 读取绑定的 `pipeline`
3. 读取 bot 级 `wecomprivate reception config`
4. 若是欢迎事件且允许欢迎，则发送欢迎语
5. 判断是否命中直接进入下一环的条件
6. 判断是否需要补问字段
7. 若无需转出也无需补问，则继续标准 AI 接待
8. 若连续未解决达到阈值，则发送兜底并转下一环
9. 记录本轮结果与上下文

### 7.2 标准结果类型

第一版统一输出以下 3 种结果：

- `continue_ai`
- `request_binding_fields`
- `route_next_stage`

这样后续阶段可以直接消费标准结果，而不必重新解释 AI 自动接待的中间状态。

### 7.3 状态落地方式

- `continue_ai`
  - 会话维持 AI 托管
- `request_binding_fields`
  - 会话仍在 AI 托管
  - 创建或更新 `WecomPrivateBindingTask`
- `route_next_stage`
  - 记录 `WecomPrivateRoutingDecision`
  - 如果后续识别/分流链路尚未完全实现，第一版允许兼容回退到现有 `pending_manual`

### 7.4 当前阶段的闭环定义

第一版的“AI 自动接待闭环”定义为：

- 用户进入私域接待后，AI 能先接住
- 能回答标准问题
- 必要时能补问传奇业务字段
- 达到条件后明确转给后续识别/分流
- 全过程状态和触发原因都有记录

---

## 八、页面与接口挂载

### 8.1 页面挂载策略

第一版不新增菜单，不做独立模块中心，只在现有页面上扩展：

- `Pipeline` 页面
  - 继续作为接待模板配置页
- `Service Desk / Bot 配置` 页面
  - 新增 `AI 自动接待配置` 卡片
  - 仅在 `wecomprivate` bot 下显示

### 8.2 接口方向

第一版需补齐以下能力：

- 获取 `wecomprivate reception config`
- 更新 `wecomprivate reception config`
- 在 bot 配置页联动展示 pipeline 摘要
- 会话运行时读取 reception config 做统一决策

接口设计应尽量沿用现有 `service_desk` 和 `wecom_private` 风格，不另外发明第三套配置域。

---

## 九、错误处理与边界

### 9.1 错误处理原则

1. 欢迎语发送失败，不阻断后续 AI 接待
2. reception config 缺失时，走保守回退路径，不允许静默乱跑
3. 补问失败不丢上下文，已收集字段必须保留
4. 后续链路未完工时，`route_next_stage` 不能让会话悬空

### 9.2 边界场景

第一版必须明确处理：

- 用户一开始就要求人工
- 用户在补问过程中继续提普通问题
- 用户只补了部分字段
- bot 切换了绑定模板
- bot 没有绑定知识库
- 欢迎事件与普通消息重复到达

### 9.3 第一版不做的复杂能力

- 多层优先级流程编排
- 场景化子流程树
- 复杂规则组合器
- 复杂风控评分

---

## 十、验收标准

### 10.1 配置验收

必须满足：

1. `Pipeline` 可作为传奇接待模板使用
2. `wecomprivate` bot 可在后台看到并保存 AI 自动接待配置
3. 后台能清楚区分“模板内容”和“入口规则”

### 10.2 运行验收

必须满足：

1. 新加好友时，可按配置决定是否发送欢迎语
2. 常规 FAQ 问题可继续 AI 接待
3. 命中补问场景时，可创建/更新 binding task
4. binding task 可记录 `UID / 区服 / 角色名`
5. 命中转出场景时，可记录 routing decision
6. 达到未解决阈值时，可发送兜底并进入下一环
7. 后续识别/分流未完全落地时，可安全回退到现有人工待接管链路

### 10.3 回归验收

必须满足：

1. 不破坏现有 `wecomprivate` phase1 主链路
2. 不影响非 `wecomprivate` bot
3. 前端构建通过
4. `service_desk` / `wecom_private` 相关测试通过

---

## 十一、结论

本次设计的最佳落地方式是：

- 保持 `bot = 接待入口`
- 保持 `pipeline = 传奇接待模板`
- 在 `wecomprivate` 场景下新增独立的接待规则配置
- 让 AI 自动接待形成后台可运营的标准闭环

第一版不追求做成通用客服引擎，而是优先做成：

`面向传奇品类、多游戏/多版本运营的 wecomprivate AI 自动接待后台`

在此基础上，后续才继续展开：

- 用户识别与分层
- 更强的智能分流
- 人工接待与 AI 辅助
- 会后闭环与运营动作

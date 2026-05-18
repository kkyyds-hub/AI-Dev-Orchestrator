# AI-Dev-Orchestrator AI 辅助体验层与前端工作台重构总规划

> 建议仓库路径：`docs/product/AI-Dev-Orchestrator-ai-assisted-ux-roadmap-20260517.md`  
> 规划版本：V1.0  
> 适用阶段：后端真实闭环基本打通后，进入“AI 辅助体验层 + 中文化 + 工作台产品化”阶段  
> 当前核心目标：把 AI-Dev-Orchestrator 从“开发调试台”推进为“面向用户的 AI 项目编排工作台”。

---

## 1. 背景与当前问题

AI-Dev-Orchestrator 当前已经具备一批真实后端闭环能力，包括：

- 项目、任务、运行、Provider、模型路由等基础能力；
- DeepSeek / OpenAI-compatible Provider 的真实调用链路；
- 项目上下文筛选；
- 成功运行后自动生成交付件；
- 自动生成待审批记录；
- 交付件中心、审批中心、任务页、运行页之间的数据闭环；
- provider timeout、fallback mock 污染等关键后端问题已经开始收口。

但是，从实际使用体验看，当前系统仍然存在明显的产品化问题：

1. 页面默认展示大量技术日志、英文字段、内部状态和 prompt 信息。
2. 用户摘要与技术诊断混在一起，导致不懂技术的用户看不懂，懂技术的用户也觉得疲惫。
3. 中英文混杂严重，例如 `Execution`、`Provider fallback`、`prompt contract`、`quality gate`、`chat_completions` 等内部词直接暴露在主界面。
4. 运行结果摘要更像后端拼接日志，而不是面向用户的中文总结。
5. 日志内容没有经过排版，直接铺在详情区域，影响观感和页面层级。
6. 很多配置项仍要求用户自己理解和填写，例如仓库绑定、验证命令、角色配置、技能配置、任务拆解等。
7. AI 已经接入系统，但目前主要用于执行任务，没有充分参与“帮用户理解、生成、配置、总结和审查”的体验层。
8. 页面按钮、入口、空状态、下一步引导仍有不统一、不直观的问题。

因此，下一阶段不能只做普通美化，也不能继续堆功能。应该转向：

> 让 AI-Dev-Orchestrator 具备“AI 辅助体验层”：AI 帮用户生成草案、生成摘要、建议配置、解释结果，用户只需要审核、确认和必要时调整。

---

## 2. 总体产品定位调整

### 2.1 当前状态

当前系统更像：

```text
开发者调试控制台
- 直接展示执行日志
- 直接展示 Provider 细节
- 直接展示 prompt / routing / fallback / quality gate
- 用户需要自己理解大量内部字段
```

### 2.2 目标状态

目标系统应该更像：

```text
AI 项目编排工作台
- 用户表达目标
- AI 帮助生成项目草案、任务拆解、验证建议、仓库建议、技能建议
- 用户审核后确认应用
- 系统执行任务
- AI 用中文总结执行结果、风险、交付物、审批状态和下一步建议
- 技术日志保留，但默认不干扰主界面
```

### 2.3 核心原则

后续设计和开发必须遵守以下原则：

1. **默认给用户看结论，不默认给用户看原始日志。**
2. **用户摘要必须中文化、白话化、结构化。**
3. **技术细节必须保留，但放入“查看技术日志”弹窗。**
4. **AI 可以生成建议和预填配置，但高风险动作必须由用户确认。**
5. **懂技术的用户可以继续深入查看配置和日志；不懂技术的用户可以只看 AI 摘要和下一步建议。**
6. **页面不应靠折叠块堆内容，应通过弹窗、分区、跳转、按钮闭环组织信息。**
7. **所有新功能都要纳入前端中文化、按钮排布、空状态、下一步引导的统一治理。**

---

## 3. 目标用户分层

### 3.1 小白用户 / 非技术用户

这类用户只关心：

- 项目现在做到哪一步？
- 任务有没有完成？
- 结果是否可靠？
- 有什么风险？
- 下一步我应该点什么？
- 是否需要我确认？

他们不应该默认看到：

- raw JSON；
- prompt contract；
- provider receipt；
- chat_completions；
- fallback reason；
- token accounting；
- internal route；
- executor mode；
- 枚举值和内部字段名。

### 3.2 技术用户 / 审查用户

这类用户需要：

- 查看模型调用是否真实；
- 查看失败原因；
- 查看 token / cost；
- 查看质量检查结果；
- 查看 prompt、模型路由、Provider receipt；
- 查看原始日志；
- 复制日志用于排查。

但这些内容不应该铺在默认页面里，而应该通过统一入口查看。

### 3.3 项目负责人 / 审批用户

这类用户需要：

- 项目总览；
- 任务进展；
- 交付件摘要；
- 审批结论；
- 风险和阻塞项；
- AI 给出的白话说明；
- 一键查看详细证据。

---

## 4. 信息展示三层模型

后续所有项目相关页面都应采用三层信息模型。

### 4.1 第一层：用户摘要层

默认展示。要求：

- 全中文；
- 白话；
- 少字段；
- 不展示内部枚举；
- 不展示 JSON；
- 不展示 prompt；
- 明确告诉用户结果、风险和下一步。

示例：

```text
本次任务已由 DeepSeek 成功执行。

完成内容：
1. 已根据任务目标生成执行结果。
2. 已完成当前配置的质量检查。
3. 已生成交付快照，并进入待审批状态。

需要注意：
当前验证方式为模拟验证，不代表代码已经真实编译或运行通过。建议为该项目配置真实验证命令，例如 npm run build。
```

### 4.2 第二层：操作建议层

展示用户接下来应该做什么。

示例：

```text
建议下一步：
1. 查看本次运行生成的交付件。
2. 审批或退回交付件。
3. 如果这是代码类任务，请配置真实验证命令。
```

对应按钮：

```text
[查看交付件] [前往审批] [配置验证方式] [查看技术日志]
```

### 4.3 第三层：技术日志层

通过“查看技术日志”按钮进入弹窗，不在默认页面展开。

技术日志应包含：

- 模型服务调用；
- Provider key；
- 模型名；
- Provider receipt；
- 执行模式；
- fallback 信息；
- prompt key / prompt char count；
- token / cost；
- 验证命令；
- 验证结果；
- 原始 result summary；
- 原始 run log；
- 一键复制。

---

## 5. 日志展示规则

### 5.1 不再默认铺日志

后续页面不应默认显示大片日志文本。例如当前运行页中类似内容：

```text
Execution: OpenAI-compatible provider execution succeeded...
Target deepseek/deepseek-v4-pro via chat_completions...
Prompt task_execution.default@day06.step1...
Verification: Simulated verification succeeded...
```

这些内容应进入日志弹窗，而不是运行摘要主区域。

### 5.2 不使用折叠块作为主方案

折叠块的问题：

- 展开后页面变长；
- 多个折叠块堆叠后仍然像调试页面；
- 信息层级不清晰；
- 用户很难知道哪些内容重要。

因此建议统一使用：

```text
[查看技术日志]
```

点击后打开弹窗。

### 5.3 技术日志弹窗设计要求

日志弹窗应具备：

1. 大尺寸居中弹窗；
2. 顶部显示任务名、运行 ID、状态；
3. 标签页或分组展示：
   - 执行轨迹；
   - 模型调用；
   - 验证结果；
   - 成本与 token；
   - 原始日志；
4. 支持复制当前分组；
5. 支持复制全部日志；
6. 支持关闭；
7. 长 ID 不撑版；
8. JSON 必须格式化；
9. 英文字段应有中文标签；
10. 原始日志可以保留英文，但必须放在“原始日志”分组中。

---

## 6. AI 摘要能力规划

### 6.1 为什么需要 AI 摘要

当前很多摘要是后端拼接出来的，特点是：

- 生硬；
- 中英文混杂；
- 包含内部字段；
- 更像日志，不像总结；
- 不适合用户快速理解。

AI 摘要的作用是：

- 把执行日志转成中文结论；
- 帮用户解释任务完成了什么；
- 提醒用户风险；
- 告诉用户下一步建议；
- 把复杂配置解释成白话。

### 6.2 AI 摘要不能自动无限触发

AI 摘要不能每次页面刷新都调用模型。必须遵守：

```text
按需生成
生成后保存
数据变化后标记过期
用户可手动重新生成
```

原因：

- 控制成本；
- 避免页面加载变慢；
- 避免频繁请求模型；
- 避免摘要内容不可追溯。

### 6.3 AI 摘要类型

后续建议支持以下摘要类型：

| 摘要类型 | 生成对象 | 用途 |
|---|---|---|
| 运行摘要 | run | 解释本次运行做了什么、是否成功、风险是什么 |
| 任务摘要 | task | 汇总任务目标、历史运行、当前状态 |
| 项目摘要 | project | 汇总项目目标、进度、交付件、审批、风险 |
| 交付件摘要 | deliverable | 解释交付件内容、质量、是否建议审批 |
| 审批辅助摘要 | approval | 帮用户判断是否通过、退回、要求修改 |
| 配置说明摘要 | project config | 解释角色、验证、skill、仓库配置 |
| 技术日志解释 | run log | 把日志转换为排查建议 |

### 6.4 AI 摘要输出格式

AI 摘要建议统一为 Markdown，便于展示和保存。

推荐结构：

```markdown
## 一句话结论

## 本次完成内容

## 关键结果

## 风险与注意事项

## 建议下一步

## 技术用户可关注
```

### 6.5 AI 摘要保存策略

建议后端新增摘要记录或复用现有实体字段，保存：

- summary_id；
- project_id；
- task_id；
- run_id；
- deliverable_id；
- summary_type；
- summary_markdown；
- source_version / source_hash；
- generated_by_model；
- provider_receipt_id；
- generated_at；
- stale 标记。

如果暂时不做新表，可以先在已有运行或交付件扩展字段中保存，但不建议长期混在 result_summary 中。

---

## 7. 项目创建 AI 对话规划

### 7.1 当前问题

当前项目创建更像表单流程，用户需要自己理解：

- 项目名称；
- 目标；
- 任务拆解；
- 角色配置；
- 验证方式；
- 仓库绑定；
- 技能配置；
- 风险描述；
- 交付件边界。

这对非技术用户太重。

### 7.2 目标体验

目标体验应为：

```text
用户：我想做一个内部审批系统的前端优化。
AI：我需要确认几个问题：
    1. 是否已有 GitHub 仓库？
    2. 当前主要痛点是什么？
    3. 是否需要自动运行 build？
    4. 是否有验收标准？
用户补充回答。
AI 生成项目草案。
用户审核。
用户点击确认创建。
```

### 7.3 AI 应生成的内容

AI 项目创建助手应生成：

- 项目名称；
- 项目目标；
- 项目范围；
- 不做范围；
- 任务拆解；
- 角色建议；
- 验证方式建议；
- 仓库绑定建议；
- skill 建议；
- 风险和验收标准；
- 初始交付件建议。

### 7.4 用户必须审核

AI 生成的内容不能直接静默应用。必须提供：

```text
[确认创建]
[编辑草案]
[重新生成]
[放弃]
```

### 7.5 AI 项目主管式澄清与规划

本节描述 AI 项目主管（AI Project Director）在项目创建对话中的核心行为规范。AI 项目主管不是被动表单填写器，而是主动的"作战计划生成器"——它通过多轮澄清理解用户意图，判断项目复杂度，并生成一份完整的 **AI 项目主管作战计划**。

#### 7.5.1 AI 项目主管作战计划

AI 项目主管输出的最终产物称为"AI 项目主管作战计划"，至少包含以下内容：

| 计划项 | 说明 |
|---|---|
| 项目目标与范围 | 用户原始目标 + AI 澄清后的精确边界 |
| 复杂度评估 | 简单 / 中等 / 复杂 / 大型多 Agent 协作 |
| 任务拆解 | 任务列表，含每个任务的目标、输入、验收标准、优先级 |
| 任务数量 | 由 AI 根据复杂度生成建议，**不是用户填 max_tasks** |
| Agent 编队 | 每个 Agent 的角色名称、职责描述、上下游协作关系 |
| Agent 数量 | 由 AI 根据任务数量和复杂度生成建议 |
| Skill 绑定方案 | 每个 Agent 应绑定哪些 Skill，为什么 |
| 验证机制建议 | 每个任务或项目整体的验证命令、模板建议 |
| 仓库绑定建议 | 是否需要仓库、主分支、关注目录 |
| 风险与不做范围 | 已知风险、明确不做的事情 |
| 交付件边界 | 每个任务预期产出什么 |

#### 7.5.2 禁止暴露 max_tasks 作为主输入

AI 项目主管入口**严禁**将 `max_tasks`（最大任务数）作为用户主输入字段。原因：

1. 非技术用户不理解应该拆几个任务。
2. 任务数量应由 AI 分析项目目标、复杂度、验收标准后主动建议。
3. 把 `max_tasks` 暴露给用户会让用户误以为"任务越多越好"或"把数字填大 AI 就会做更多事"。
4. `max_tasks` 如果必须作为硬上限存在，它应该是后端安全阀（默认合理值 + 项目级可覆盖），而不是前端第一屏的必填项。

**正确做法**：用户在对话中描述目标 → AI 判断复杂度 → AI 在作战计划中建议"N 个任务"→ 用户审核时可调整（合并、拆分、增减）。

#### 7.5.3 任务数量由 AI 根据复杂度生成

```text
复杂度简单 → 建议 1-3 个任务
复杂度中等 → 建议 3-6 个任务
复杂度复杂 → 建议 6-10 个任务
复杂度大型多 Agent 协作 → 建议 10-20 个任务，须用户逐项确认
```

AI 必须在作战计划中解释为什么建议这个任务数量。用户审核时可以：
- 合并任务；
- 拆分任务；
- 增加/删除任务；
- 调整任务顺序和依赖关系。

#### 7.5.4 Agent 编队与 Skill 绑定由 AI 生成

AI 项目主管在澄清后应输出完整 Agent 编队方案：

```text
推荐 Agent 编队（共 N 个 Agent）：

1. 架构师 Agent
   - 职责：审查整体架构、数据库设计、接口契约
   - 绑定 Skill：review-v5-code-and-risk
   - 协作：向所有下游 Agent 提供架构约束

2. 前端工程师 Agent
   - 职责：实现 UI 组件、页面、状态管理
   - 绑定 Skill：write-v5-web-control-surface
   - 协作：接收架构师的设计约束，交付给审查员

3. 后端工程师 Agent
   - 职责：实现 API、Service、Repository
   - 绑定 Skill：write-v5-runtime-backend
   - 协作：接收架构师的接口契约，交付给测试工程师

4. 测试工程师 Agent
   - 职责：编写和运行测试、验证闭环
   - 绑定 Skill：verify-v5-runtime-and-regression
   - 协作：接收前后端 Agent 的交付件，反馈问题
```

用户审核时可以：
- 增加/删除 Agent；
- 调整 Agent 角色名称和职责描述；
- 更换或增减 Skill 绑定；
- 调整协作关系。

#### 7.5.5 用户确认与编辑

AI 项目主管生成的**全部**内容（任务拆解、Agent 编队、Skill 绑定、验证方案、仓库建议）都必须经过用户审核，不允许静默应用。用户必须能看到：

```text
[确认创建] — 一次性创建项目、任务、Agent、Skill 绑定
[编辑草案] — 进入分步编辑界面逐项调整
[重新生成] — 保留原始目标描述，重新生成作战计划
[放弃]
```

高风险动作（如绑定仓库、配置真实验证命令、apply-local、git write）必须在编辑草案中额外高亮提醒。

#### 7.5.6 创建后可查看与二次编辑

AI 项目主管创建的内容不是一次性快照。创建完成后，用户可以在以下页面查看和二次编辑：

| 内容 | 可查看/编辑的页面 |
|---|---|
| 项目目标、范围、风险、不做范围 | 项目详情页 |
| 任务列表、优先级、验收标准 | 任务页 |
| Agent 角色、职责、协作关系 | 角色页 |
| Skill 绑定 | Skill 页 |
| 验证命令、验证模板 | 验证配置页 |
| 仓库 URL、主分支 | 仓库绑定页 |

用户在任何时候都可以回到 AI 项目主管对话，请求"根据当前项目最新状态重新评估"或"调整作战计划"。

---

## 8. AI 配置助手规划

### 8.1 仓库绑定助手

AI 可帮助用户判断：

- 当前项目是否需要绑定仓库；
- 仓库 URL 是否有效；
- 主分支是什么；
- 是否需要扫描文件；
- 可能的前端/后端目录；
- 应该关注哪些文件。

但最终绑定动作必须由用户确认。

### 8.2 验证机制助手

AI 可根据项目类型建议验证命令：

| 项目类型 | 建议验证 |
|---|---|
| React/Vite | `npm run build` |
| Node.js | `npm test` / `npm run build` |
| Python | `python -m compileall app` / `pytest` |
| 后端 FastAPI | `python -m compileall app` + smoke |
| 文档项目 | 检查文件生成和格式 |

用户确认后应用。

### 8.3 Skill 生成助手

AI 可根据项目长期工作流生成 skill，例如：

- 前端结构治理 skill；
- 按钮闭环审查 skill；
- 后端真实闭环验收 skill；
- 运行摘要生成 skill；
- 日志排查 skill；
- 项目上下文过滤 skill。

生成后用户可跳转到 skill 页面编辑和确认。

### 8.4 角色配置助手

AI 可建议：

- 架构师；
- 前端工程师；
- 后端工程师；
- 测试工程师；
- 审查员；
- 文档工程师。

同时解释每个角色负责什么。

---

## 9. 中文化与术语治理

### 9.1 目标

全站默认显示中文产品语言，避免中英文混杂和内部术语外露。

### 9.2 术语映射建议

| 当前词 | 建议显示 |
|---|---|
| Task | 任务 |
| Run | 运行 |
| Provider | 模型服务 |
| Model | 模型 |
| Fallback | 降级执行 |
| Quality Gate | 质量检查 |
| Execution Summary | 执行摘要 |
| Deliverable | 交付件 |
| Approval | 审批 |
| Prompt Contract | 提示词契约 / 技术提示词信息 |
| Provider Receipt | 模型回执 |
| Token | token / 模型用量 |
| Cost | 成本 |
| Raw Log | 原始日志 |
| Verification | 验证 |
| Smoke | 冒烟测试 |
| Context Package | 上下文包 |
| Change Plan | 变更计划 |
| Change Batch | 变更批次 |

### 9.3 不是所有词都要硬翻译

例如：

- token 可以保留，但需要解释为“模型用量”；
- JSON 可以保留，但默认不展示；
- Git、branch、commit 可以保留，但用户摘要中应解释作用；
- API 可以保留，但不要让普通用户必须理解。

---

## 10. 前端体验治理方向

### 10.1 页面默认状态

每个页面必须回答用户三个问题：

```text
这个页面是做什么的？
我现在看到的是什么状态？
我下一步应该做什么？
```

### 10.2 按钮排布规则

按钮应按优先级排列：

1. 主操作按钮；
2. 次要查看按钮；
3. 技术日志按钮；
4. 危险操作按钮。

示例：

```text
[查看交付件] [前往审批] [生成 AI 摘要] [查看技术日志]
```

危险动作必须明显区分：

```text
[应用到本地] [提交候选] [确认审批]
```

### 10.3 空状态规则

空状态不能只显示“暂无数据”。必须告诉用户原因和下一步。

错误示例：

```text
暂无交付件
```

正确示例：

```text
当前项目还没有交付件。
请先运行一个属于该项目的任务。任务成功后，系统会自动生成交付快照。

[去任务页运行任务]
```

### 10.4 长文本与 ID 展示

- 长 ID 默认截断；
- 鼠标悬停显示完整内容；
- 提供复制按钮；
- 不允许长 ID 撑破布局；
- 长日志必须进弹窗；
- 默认摘要最多展示关键段落。

---

## 11. 阶段实施路线图

### 阶段 1：运行页摘要 + 技术日志弹窗

目标：

- 默认展示中文用户摘要；
- 技术日志不再默认铺在详情区；
- 增加“查看技术日志”弹窗；
- 日志弹窗格式化展示执行、Provider、验证、token、原始日志；
- 将英文内部字段移出默认视图。

验收：
- 运行详情默认不出现大段英文日志；
- mock fallback、provider timeout、真实 provider success 都有中文说明；
- 技术用户可点击按钮查看完整日志；
- 日志弹窗排版清晰，可复制。

> **实施状态：已完成** `[2026-05-17]`
>
> 提交哈希：`9cefbe6`
>
> 修改范围：
> - `apps/web/src/pages/runs/components/RunsTaskDetailSection.tsx` — 移除 raw result_summary，集成摘要卡片与技术日志弹窗
> - `apps/web/src/features/task-detail/components/TaskDetailRuntimeContractSection.tsx` — 新增 `hideRawDiagnosticTexts` 支持，原始诊断文本移入弹窗
> - 新增 `apps/web/src/pages/runs/components/RunUserSummaryCard.tsx` — 中文规则摘要卡片
> - 新增 `apps/web/src/pages/runs/components/RunTechnicalLogModal.tsx` — 技术日志弹窗（8 分区 + 复制能力）
> - 新增 `apps/web/src/pages/runs/lib/runUserSummary.ts` — 规则摘要生成器
> - 新增 `apps/web/src/pages/runs/lib/runTechnicalLog.ts` — 技术日志格式化
>
> 验收结果：
> - 默认不展示 raw result_summary / verification_summary / route_reason 大段英文
> - provider 成功 / timeout / mock / fallback 各有中文说明
> - 模拟验证明确提示"不代表代码真实构建通过"
> - 质量检查拦截明确提示"请查看技术日志定位原因"
> - 技术日志通过弹窗查看，含 8 个分区 + 复制运行 ID / 复制全部
> - 不破坏原有按钮闭环和 data-testid
> - `npm run build` 通过
>
> **阶段 1 返工** `[2026-05-17]`：修正规则摘要误判与技术日志语义过度承诺
> - timeout 判断不再将 failure_category="execution_failed" 等同于超时
> - 真实模型成功增加 provider_receipt_id 必要条件
> - mock/fallback 文案分离，不再合并为"模拟/降级执行"
> - 技术日志"模型名称"改为"模型服务 Key"，不再用 provider_key 填充
> - 执行轨迹不再对所有 succeeded run 声称"已生成交付件""已创建审批记录"
> - "交付件与审批"分区增加免责说明（ConsoleRun 暂不携带 deliverable_id/approval_id）
>
> **阶段 1B** `[2026-05-17]`：摘要卡片视觉风格收口 — 移除 emerald/amber/rose 强彩色状态块，统一为中性灰黑线条式后台风格。

### 阶段 2：AI 运行摘要生成

目标：

- 增加运行摘要生成接口；
- DeepSeek 根据 run、task、verification、deliverable、approval 生成中文 Markdown；
- 生成后保存；
- 前端显示 AI 摘要；
- 支持重新生成。

验收：

- 摘要为中文；
- 不直接暴露 JSON；
- 能区分真实 provider 成功、provider timeout、mock fallback、验证失败；
- 摘要保存后刷新不丢。

> **阶段 2B-R3 实施记录** `[2026-05-18]`
>
> 任务：运行摘要来源文案收口 + 文档回填
>
> 提交哈希：`2f35394`（完整：`2f35394d84375df298f49924d31d74e805c3f924`）
>
> Build 结果：通过（tsc + vite build）
>
> 修改范围：
> - `apps/web/src/pages/runs/components/RunPrimarySummaryCard.tsx` — 主卡片文案收口
> - `apps/web/src/pages/runs/api/runAiSummary.ts` — API 错误消息文案收口
>
> 已完成：
> - 前端已接入保存摘要接口（GET + POST generate + POST regenerate）
> - 当前摘要来源仍为 rule_fallback，不真实调用 DeepSeek/OpenAI
> - 真实 AI 摘要生成仍未接入，保留到阶段 2C
> - 主卡片标题固定为"运行摘要"，不再出现"AI 摘要"/"AI 运行摘要"/"智能摘要"
> - 按钮文案收口：无摘要时"生成运行摘要"，有摘要时"重新生成摘要"，生成中"生成中…"
> - source=rule_fallback 时状态条显示"摘要来源：规则回退 · 尚未调用真实 AI"
> - source=ai 时预留显示"摘要来源：AI 生成 · {model_provider 或 model_name}"
> - 错误/空状态文案统一为"运行摘要服务暂不可用"/"摘要生成失败"/"当前显示本地规则摘要"，不再出现"AI 摘要生成失败"
> - 空状态：active_summary=null 时显示"当前显示本地规则摘要。可以生成一份可保存的运行摘要，刷新页面后仍可查看。"
> - Footer 低调说明："当前阶段的保存摘要由规则回退生成；真实 AI 摘要将在后续阶段接入。"
> - 原始 run 的模型执行与摘要生成方式在 UI 上已明确区分
> - 视觉风格保持中性灰黑线条式，未新增 emerald/amber/rose 大色块和 AI 图标
> - 技术日志弹窗保持不变
> - 未修改后端、不真实调用 AI、不进入阶段 2C
>
> **阶段 2B-R5 实施记录** `[2026-05-18]`
>
> 任务：运行摘要正文技术噪音收口
>
> 提交哈希：`ba8b005`（完整：`ba8b005c8d434739faa5df40649be99f5451f360`）
>
> Build / 测试结果：后端 16 测试通过，前端 build 通过
>
> 修改范围：
> - `runtime/orchestrator/app/services/run_ai_summary_service.py` — `_build_summary_markdown()` 移除完整 source_fingerprint / prompt_hash
>
> 已完成：
> - 默认摘要正文不再展示完整 source_fingerprint / prompt_hash
> - 技术依据章节改为 "摘要依据：运行状态、结果摘要、验证摘要、质量检查、模型服务记录"
> - 调试指纹说明 "已记录，可在前端状态条或技术日志中查看完整值"
> - Markdown 五标题结构保持不变
> - 前端状态条仍保留 8 位短 hash + title 悬停完整值
> - 当前仍为 rule_fallback，不真实调用 AI
> - 真实 DeepSeek 摘要仍保留到 2C
>
> **阶段 2C-A 实施记录** `[2026-05-18]`
>
> 任务：真实 AI 运行摘要后端最小闭环
>
> 提交哈希：`bdfd6ed`（完整：`bdfd6edde8f1ba591e57724d25e7c71887ca14a4`）
>
> Build / 测试结果：后端 28 测试通过，前端 build 通过
>
> 修改范围：
> - `runtime/orchestrator/app/services/openai_provider_executor_service.py` — 新增 `generate_text()` 纯文本生成方法
> - `runtime/orchestrator/app/services/run_ai_summary_service.py` — AI 优先生成 + rule_fallback + Markdown 校验
> - `runtime/orchestrator/app/api/routes/runs.py` — DI 注入 ProviderConfigService
> - `runtime/orchestrator/tests/test_run_ai_summaries.py` — 新增 12 个测试
>
> 已完成：
> - Provider 配置存在时优先尝试真实 AI 生成运行摘要
> - AI 成功时保存 source=ai，含 model_provider / model_name / provider_receipt_id
> - AI 失败/超时/格式不合格/未配置时自动回退 source=rule_fallback
> - GET /ai-summary 不触发 AI，只读 active_summary
> - POST generate/regenerate 优先尝试 AI
> - 前端无需改动，现有 source 展示可区分 AI / 规则回退
> - 不修改 worker/provider 主执行流程
>
> **阶段 2C-A-R1 实施记录** `[2026-05-18]`
>
> 任务：真实 AI 运行摘要后端硬化返工
>
> 提交哈希：`914b404`（完整：`914b404d249185eae75b3046438414aebab14f6e`）
>
> Build / 测试结果：后端 35 测试通过，前端 build 通过
>
> 修改范围：
> - `runtime/orchestrator/app/api/routes/runs.py` — 始终注入 ProviderConfigService
> - `runtime/orchestrator/app/services/run_ai_summary_service.py` — source=ai 使用 AI prompt_hash
> - `runtime/orchestrator/app/services/openai_provider_executor_service.py` — generate_text 传递 provider_key
> - `runtime/orchestrator/tests/test_run_ai_summaries.py` — 新增 7 个测试
>
> 已完成：
> - 修复 env-only provider 配置不触发 AI 的问题
> - source=ai 的 prompt_hash 现在来自实际 AI prompt
> - source=rule_fallback 的 prompt_hash 保持稳定（规则 prompt hash）
> - generate_text 的 provider_key 不再硬编码 openai
> - 前端 UI 仍无需改动
>
> **阶段 2C-A-R2 实施记录** `[2026-05-18]`
>
> 任务：测试补强与文档追溯修正
>
> 提交哈希：`6ed33d2`（完整：`6ed33d231c853dc0f9d37348ec1ac0087cd17ec2`）
>
> Build / 测试结果：后端 35 测试通过，前端 build 通过
>
> 修改范围：
> - `runtime/orchestrator/tests/test_run_ai_summaries.py` — 重写 provider_key/env 测试为真正的 monkeypatch
> - `docs/product/` 3 份 — 修正 2C-A-R1 哈希 + 追加 2C-A-R2 记录
>
> 已完成：
> - 2C-A-R1 哈希修正为 `914b404` 完整哈希
> - provider_key 测试已真正覆盖 _call_provider_text → generate_text 路径
> - env-only/provider_config 测试已真正覆盖 provider_config_service 路径
> - 未真实调用外部 AI
> - 未进入 2C-B
>
> **阶段 2C-B 实施记录** `[2026-05-18]`
>
> 任务：真实 DeepSeek 运行时联调验收
>
> 提交哈希：`8f6f204`（完整：`8f6f204b63922af6905ee3042dfa0f5b2176144e`）
>
> 结论：**Pass** — 真实 DeepSeek 生成 source=ai 运行摘要成功
>
> 运行时验收：
> - Provider：DeepSeek，连通性测试 passed
> - run_id：`fa552a28`，POST /regenerate → source=ai，model_provider=deepseek，receipt 非空
> - 35 tests / build 通过，未暴露 API key

### 阶段 3：项目页 AI 总结按钮

目标：

- 项目页增加“生成项目总结”；
- AI 汇总项目目标、任务、运行、交付件、审批、风险；
- 输出 Markdown；
- 支持重新生成；
- 数据变化后提示摘要可能过期。

验收：

- 小白用户可以通过项目总结理解项目进度；
- 技术用户可继续查看详情；
- 摘要不替代原始数据，只作为解释层。

### 阶段 4：项目创建 AI 对话

目标：

- 新增 AI 项目创建聊天入口；
- 用户通过对话描述项目；
- AI 追问必要信息；
- 生成项目草案；
- 用户审核后创建项目。

验收：

- 用户无需直接填写复杂表单也能生成项目草案；
- 草案内容可编辑；
- 创建前必须确认；
- 不覆盖现有手动创建流程。

### 阶段 5：AI 配置助手

目标：

- 仓库绑定建议；
- 验证命令建议；
- skill 建议；
- 角色配置建议；
- 用户审核后应用。

验收：

- AI 只建议和预填；
- 高风险动作必须用户确认；
- 配置建议可跳转到对应页面编辑。

### 阶段 6：全站中文化与按钮治理

目标：

- 统一术语；
- 替换生涩英文标题；
- 统一按钮顺序；
- 统一空状态；
- 统一日志入口；
- 统一项目上下文提示。

验收：

- 默认界面不再中英文混杂；
- 内部字段不再出现在普通摘要；
- 页面更像正式后台工作台。

---

## 12. 后续子文档建议

本总规划后续应拆成以下子文档，每个子文档对应一个阶段：

1. `AI-Dev-Orchestrator-run-summary-and-log-modal-design-audit.md`
   - 运行页摘要与日志弹窗设计审计。

2. `AI-Dev-Orchestrator-ai-run-summary-backend-design.md`
   - AI 运行摘要后端设计。

3. `AI-Dev-Orchestrator-project-ai-summary-design.md`
   - 项目页 AI 总结按钮设计。

4. `AI-Dev-Orchestrator-ai-project-draft-chat-design.md`
   - AI 项目草案对话设计。

5. `AI-Dev-Orchestrator-ai-configuration-assistant-design.md`
   - 仓库、验证、skill、角色配置助手设计。

6. `AI-Dev-Orchestrator-ui-copywriting-and-terminology-guide.md`
   - 全站中文化与术语治理指南。

7. `AI-Dev-Orchestrator-technical-log-modal-component-spec.md`
   - 技术日志弹窗组件规范。

---

## 13. 明确不做的事情

为避免开发失控，以下内容不在本规划第一轮范围内：

1. 不重建前端项目；
2. 不换技术栈；
3. 不重写后端主流程；
4. 不删除现有技术日志；
5. 不取消技术用户的审查能力；
6. 不让 AI 静默执行高风险配置；
7. 不让页面刷新自动大量调用模型；
8. 不把 mock 结果伪装成真实模型结果；
9. 不把用户摘要和技术日志继续混在一起；
10. 不把所有页面一次性重构。

---

## 14. 总体验收标准

当本规划阶段性完成后，系统应达到：

1. 普通用户进入页面后能看懂当前项目状态；
2. 默认摘要为中文白话；
3. 技术日志通过弹窗查看，排版清晰；
4. DeepSeek 成功、失败、timeout、mock fallback 等状态能清楚区分；
5. 运行成功后能生成交付件和审批；
6. AI 能生成运行摘要和项目总结；
7. AI 能辅助生成项目草案和配置建议；
8. 用户能审核 AI 建议后再应用；
9. 技术用户仍能查看完整日志和原始细节；
10. 全站中英文混杂明显减少；
11. 按钮、入口、空状态、下一步引导更加统一；
12. 页面从“调试台”转向“AI 工作台”。

---

## 15. 第一条建议落地任务

本规划落地的第一条任务建议为：

> 运行页摘要与技术日志弹窗设计审计。

该任务只审计，不急于改代码。审计应回答：

1. 运行页哪些内容是用户摘要？
2. 哪些内容是技术日志？
3. 哪些字段来自后端拼接？
4. 哪些字段需要 AI 摘要？
5. 哪些组件需要改为日志弹窗？
6. 哪些标题需要中文化？
7. 哪些按钮需要重新排布？
8. 哪些空状态需要补下一步引导？
9. 哪些后端字段需要新增保存 AI 摘要？
10. 最小可落地改造阶段怎么切分？

建议后续子文档路径：

```text
docs/product/AI-Dev-Orchestrator-run-summary-and-log-modal-design-audit-20260517.md
```

---

## 16. 总结

AI-Dev-Orchestrator 后续的关键不是继续堆更多调试字段，而是让 AI 真正参与用户体验：

- 帮用户生成项目；
- 帮用户建议配置；
- 帮用户解释运行；
- 帮用户总结项目；
- 帮用户发现风险；
- 帮用户把复杂系统变成可审核、可理解、可操作的工作流。

技术日志、Provider 信息、JSON、prompt、token、cost 仍然重要，但它们应该服务于审查，而不是占据默认界面。

下一阶段应以“运行页摘要 + 技术日志弹窗”为切入口，逐步完成 AI 辅助体验层的产品化改造。

# AI-Dev-Orchestrator 运行页摘要 + 技术日志弹窗设计审计报告

> 建议仓库路径：`docs/product/AI-Dev-Orchestrator-run-summary-log-modal-design-audit-20260517.md`  
> 审计基线：`origin/main` 最新阶段，已完成项目上下文收口、P0 自动交付件、P0 自动审批、DeepSeek live provider timeout/mock fallback 污染修复。  
> 文档目的：作为后续“运行页摘要中文化 + 技术日志弹窗 + AI 摘要能力”开发标准，不直接等同实现指令。后续每个阶段应从本文拆分成更小的 Codex/DeepSeek 指令执行。

---

## 1. 背景与当前进展

AI-Dev-Orchestrator 当前已经不再只是前端页面重排阶段，系统后端真实闭环也已经推进到较关键的状态：

1. **项目上下文已基本收口**
   - 任务页、运行页已接入项目筛选。
   - URL / localStorage 的 `projectId` 状态已稳定。
   - 仓库页、交付物页、审批页、治理页已经按项目上下文进入。
   - 已修复“全部项目视角下强项目子页面误展示最近项目”的问题。

2. **模型服务真实调用链路已打通**
   - DeepSeek 通过 OpenAI-compatible 接口调用。
   - `base_url = https://api.deepseek.com/v1`
   - `model_name = deepseek-v4-pro`
   - 已能看到真实 provider receipt。
   - 已修复 provider timeout 默认 30 秒过短的问题，默认 timeout 提升到 120 秒。

3. **mock fallback 污染已开始治理**
   - live provider timeout / network error 不再静默 fallback 到 `provider_mock` 并显示成功。
   - `fallback_applied=True` 或 `actual_execution_mode=provider_mock` 时，不应生成真实交付件和审批。
   - 这保证后续页面验收不会被“假成功”污染。

4. **项目级页面数据闭环已补齐 P0**
   - 成功 worker run 自动生成交付件。
   - 成功交付件自动生成审批记录。
   - `GET /deliverables/projects/{project_id}` 和 `GET /approvals/projects/{project_id}` 已具备项目级真实数据来源。

但是从用户界面看，运行页仍然有明显问题：

- 运行摘要中夹杂大量英文、内部字段、模型调用细节、prompt contract、fallback 信息。
- 默认页面直接展示技术日志，用户必须自己读长文本判断发生了什么。
- 摘要更像后端拼接日志，不像 AI 为用户生成的中文解释。
- 技术诊断信息和用户结果混在一起，导致懂技术的人也难读，不懂技术的人更难用。
- 日志折叠或内嵌在页面里会拉长页面，破坏后台工作台体验。

因此本阶段应把运行页从“调试页”改造成“用户可理解的运行中心”。

---

## 2. 审计范围

本报告只审计“运行页摘要 + 技术日志弹窗”相关范围。

### 2.1 包含范围

| 范围 | 当前相关位置 | 本文关注点 |
|---|---|---|
| 运行页整体布局 | `apps/web/src/pages/runs/RunsPage.tsx` | 左侧运行列表、右侧运行详情、项目上下文、入口按钮 |
| 运行详情区域 | `apps/web/src/pages/runs/components/RunsTaskDetailSection.tsx` | 默认摘要、任务信息、操作按钮、详情组件挂载 |
| 运行约束详情组件 | `apps/web/src/features/task-detail/components/TaskDetailRuntimeContractSection.tsx` | 运行详情、诊断信息、token/cost、provider 字段 |
| 任务详情接口类型 | `apps/web/src/features/console/types.ts`、`apps/web/src/features/task-detail/types.ts` | 前端可用字段 |
| 后端任务/运行 DTO | `runtime/orchestrator/app/api/routes/tasks.py` | `result_summary`、`verification_summary`、`route_reason` 等字段来源 |
| 执行器摘要生成 | `runtime/orchestrator/app/services/executor_service.py` | provider 成功/失败/fallback 摘要内容 |
| worker 收尾逻辑 | `runtime/orchestrator/app/workers/task_worker.py` | 运行状态、验证结果、交付件/审批触发 |
| 日志服务 | `runtime/orchestrator/app/services/run_logging_service.py` | 后续技术日志弹窗可读取的数据基础 |

### 2.2 不包含范围

本报告不直接要求：

- 重做整站 UI。
- 修改 provider 调用协议。
- 修改 release gate / apply-local / git write。
- 新增复杂权限系统。
- 一次性做完 AI 项目创建对话。
- 一次性做完全站中文化。
- 自动替用户执行高风险配置。

这些内容应拆分为后续子阶段。

---

## 3. 当前运行页实现观察

### 3.1 `RunsPage.tsx`

当前运行页已经具备较好的页面骨架：

- 顶部运行页标题和刷新能力。
- 当前项目选择器。
- 左侧 `RunsListPanel`。
- 右侧 `RunsTaskDetailSection`。
- 通过 `useProjectScope()` 保持项目上下文。
- 通过 `useRunSelection()` 选中当前 run。
- 能够跳转到交付件、项目 drilldown 等页面。

当前布局方向是对的，但存在两个体验问题：

1. **右侧默认详情承载了太多技术内容。**
2. **项目级上下文虽然已收口，但用户仍然要从大量运行日志中理解结果。**

### 3.2 `RunsTaskDetailSection.tsx`

当前右侧详情中：

- Header 显示任务标题、运行状态、失败分类、质量闸门。
- 显示开始时间、结束时间、token、成本。
- 如果 `selectedRun.result_summary` 存在，会直接显示 `result_summary`。
- 下方操作按钮包括返回策略预览、打开运行中心、复制任务 ID、复制运行 ID。
- 继续渲染 `TaskDetailRuntimeContractSection`。

问题：

- `selectedRun.result_summary` 是原始结果摘要，不是面向用户的中文摘要。
- `result_summary` 可能包含英文、provider 字段、prompt key、fallback 信息、内部模型路由信息。
- 当前只做 `line-clamp-2` 截断，没有真正重写为用户可理解内容。
- 操作按钮偏技术化，例如“返回策略预览”对普通用户不清楚。
- 技术日志没有独立入口，诊断内容仍在页面中铺开。

### 3.3 `TaskDetailRuntimeContractSection.tsx`

当前该组件展示：

- 运行详情：任务 ID、运行 ID、供应商、提示词模板、计算来源、供应商回执、token、成本、提示词字符数、计算模式、开始/结束时间。
- 诊断信息：质量闸门、分配评分、验证模式、失败分类。
- 诊断文本：失败分类、验证摘要、分配说明。

问题：

- “运行约束详情”偏内部技术名，不适合普通用户。
- “供应商”“提示词模板”“计算来源”“分配评分”等字段默认展示会造成理解负担。
- 诊断信息当前仍然以 inline 区域展示，后续越加越长。
- 折叠不是最佳方式，折叠后页面仍然承载技术噪音。
- `verification_summary`、`route_reason` 是后端拼接文本，可能继续出现中英文混杂。
- 当前没有“查看技术日志”的弹窗级体验。

---

## 4. 当前核心问题

### 4.1 用户摘要与技术日志混在一起

当前页面把以下内容混在默认区域：

- 执行结果。
- provider 调用路径。
- prompt template。
- 模型名。
- token/cost。
- verification summary。
- route reason。
- fallback reason。
- run id / task id。
- 质量门结果。

这会导致用户无法快速回答三个问题：

1. 这次任务到底完成了吗？
2. 完成了什么？
3. 我下一步应该做什么？

### 4.2 摘要不像 AI 写的摘要

理想摘要应是：

- 全中文。
- 白话。
- 面向用户目标。
- 能区分“真实模型成功”“模拟验证”“降级执行”“失败原因”。
- 有结论、有完成内容、有风险、有下一步建议。

当前摘要更像：

```text
Execution: OpenAI-compatible provider execution succeeded...
Target deepseek/deepseek-v4-pro via chat_completions...
Verification: Simulated verification succeeded...
```

这不应作为默认摘要。

### 4.3 日志观感不足

原始日志如果直接展示，会有这些问题：

- 长英文行撑版。
- JSON 或内部字段破坏阅读节奏。
- 用户很难区分哪些是结论，哪些是诊断。
- 折叠面板仍然占页面空间。
- 多个 run 的日志入口不统一。

日志应该以“弹窗”形式出现，不应该默认铺在运行详情页中。

### 4.4 中英文混合与术语不统一

当前存在以下中英文混合：

| 当前词 | 建议用户侧中文 |
|---|---|
| Run | 运行 |
| Task | 任务 |
| Provider | 模型服务 |
| OpenAI-compatible provider | 兼容接口模型服务 |
| Fallback | 降级执行 |
| provider_mock | 模拟模型 |
| Quality Gate | 质量检查 |
| Token | 模型用量 |
| Prompt Contract | 技术提示词信息 |
| Routing Score | 分配评分 / 调度评分 |
| Verification | 验证 |
| Execution Summary | 执行摘要 |
| Raw Log | 原始日志 |
| Receipt | 模型服务回执 |
| strategy preview | 策略预览 / 执行策略 |
| runtime contract | 运行约束 / 执行配置 |

这些词应建立统一词表，并按“用户可见 / 技术日志 / 原始字段”分层处理。

---

## 5. 目标体验模型

运行页应改为三层信息模型。

```text
第一层：用户摘要
第二层：操作建议
第三层：技术日志弹窗
```

### 5.1 第一层：用户摘要

默认展示，面向所有用户。

内容包括：

- 本次运行结论。
- 模型是否真实执行。
- 完成了什么。
- 是否通过质量检查。
- 是否生成交付件。
- 是否进入审批。
- 风险或注意事项。
- 下一步建议。

示例：

```markdown
本次任务已由 DeepSeek 成功执行。

完成内容：
1. 已根据任务目标生成执行结果。
2. 已记录本次运行的交付快照。
3. 已创建待审批记录，等待用户确认。

需要注意：
当前验证方式为模拟验证，只能说明流程已通过，不代表代码已经真实编译或运行成功。建议为该项目配置真实验证命令，例如 npm run build 或 pytest。
```

### 5.2 第二层：操作建议

用户摘要下方应提供明确按钮，而不是让用户自己猜下一步：

- 查看交付件
- 查看审批
- 生成 AI 总结
- 重新生成摘要
- 配置真实验证
- 查看技术日志
- 复制运行 ID

按钮必须按主次分层：

| 按钮类型 | 示例 |
|---|---|
| 主按钮 | 查看交付件、查看审批 |
| 次按钮 | 重新生成摘要、配置验证 |
| 技术按钮 | 查看技术日志、复制运行 ID |

### 5.3 第三层：技术日志弹窗

技术内容不默认展开。点击“查看技术日志”后打开弹窗。

弹窗包含：

1. 执行轨迹
2. 模型调用
3. 质量检查
4. 用量与成本
5. 交付件/审批链路
6. 原始日志
7. 原始字段

弹窗应支持：

- sticky header。
- 关闭按钮。
- 复制日志。
- 复制运行 ID。
- 复制模型回执。
- 大段文本自动换行。
- JSON 格式化。
- 不撑破页面。
- 不影响主运行页滚动。

---

## 6. 运行页目标信息架构

### 6.1 右侧详情推荐结构

```text
RunUserSummaryHeader
  - 任务标题
  - 运行状态
  - 模型执行状态
  - 质量检查状态
  - 交付件 / 审批状态

RunUserSummaryCard
  - 中文摘要
  - 完成内容
  - 注意事项
  - 下一步建议

RunActionBar
  - 查看交付件
  - 查看审批
  - 生成/重新生成 AI 摘要
  - 配置真实验证
  - 查看技术日志

RunMetadataStrip
  - 开始时间
  - 结束时间
  - 模型服务
  - 模型用量
  - 成本

RunTechnicalLogModal
  - 技术日志弹窗
```

### 6.2 默认页面不应显示

默认页面不应直接展示：

- `prompt_template_key`
- `provider_receipt_id`
- `route_reason` 原文
- `verification_summary` 原文
- `fallback_reason_category`
- 原始 JSON
- prompt contract
- strategy decision JSON
- raw provider summary
- 大段英文技术日志

这些应移动到技术日志弹窗。

---

## 7. 技术日志弹窗设计标准

### 7.1 入口

运行详情默认区域提供按钮：

```text
[查看技术日志]
```

按钮位置：

- 与“查看交付件”“查看审批”并列。
- 视觉优先级低于业务动作。
- 适合技术用户点击排查。

### 7.2 弹窗布局

```text
┌───────────────────────────────────────────────┐
│ 技术日志 · 运行详情                            │
│ 任务：xxx                                      │
│ 运行：run_id                                   │
│ [复制全部] [复制运行 ID] [关闭]                │
├───────────────────────────────────────────────┤
│ 状态概览                                      │
│ 执行轨迹                                      │
│ 模型调用                                      │
│ 质量检查                                      │
│ 用量成本                                      │
│ 交付件与审批                                  │
│ 原始日志                                      │
│ 原始字段                                      │
└───────────────────────────────────────────────┘
```

### 7.3 弹窗分区

#### A. 状态概览

展示：

- 运行状态
- 执行模式
- 是否真实模型执行
- 是否发生降级
- 质量检查是否通过
- 失败分类
- 开始 / 结束时间

#### B. 执行轨迹

展示用户可理解的流程：

```text
1. 已领取任务
2. 已构建提示词
3. 已调用 DeepSeek
4. 已收到模型回执
5. 已完成验证
6. 已生成交付件
7. 已创建审批记录
```

如果失败：

```text
1. 已领取任务
2. 调用 DeepSeek 超时
3. 本次运行已标记失败
4. 未生成交付件和审批
```

#### C. 模型调用

展示：

- 模型服务：DeepSeek
- 模型名称：deepseek-v4-pro
- 接口类型：OpenAI-compatible
- 请求超时：120 秒
- 模型回执：存在 / 不存在
- 是否降级：是 / 否

#### D. 质量检查

展示：

- 验证方式：模拟验证 / 命令验证 / 模板验证
- 质量检查结果：通过 / 拦截 / 未配置
- 验证摘要：格式化展示，不直接铺英文。
- 建议：如果是模拟验证，提示用户配置真实验证命令。

#### E. 用量成本

展示：

- 输入 token
- 输出 token
- 总 token
- 估算成本
- 计费来源

这里可以保留 token，但要用中文说明：“模型用量”。

#### F. 交付件与审批

展示：

- 是否生成交付件。
- 是否创建审批。
- 交付件 ID。
- 审批状态。
- 跳转按钮。

#### G. 原始日志

展示真正的原始日志，但必须：

- 使用 monospace。
- 自动换行。
- 可复制。
- 高度限制滚动。
- 不撑破页面。

#### H. 原始字段

展示 JSON 或字段表，仅供调试。

必须明确标记：

```text
以下内容为系统调试字段，普通用户无需关注。
```

---

## 8. 用户摘要生成策略

运行摘要分两个阶段实现。

### 8.1 第一阶段：规则摘要

先不调用 AI，基于现有字段生成中文摘要。

输入字段：

- `selectedRun.status`
- `selectedRun.result_summary`
- `selectedRun.failure_category`
- `selectedRun.quality_gate_passed`
- `selectedRun.verification_mode`
- `selectedRun.verification_summary`
- `selectedRun.provider_key`
- `selectedRun.model_name`
- `selectedRun.provider_receipt_id`
- `selectedRun.fallback_applied`（如果前端已有）
- `selectedRun.actual_execution_mode`（如果前端已有）
- 是否存在交付件
- 是否存在审批

规则示例：

| 条件 | 用户摘要 |
|---|---|
| provider 成功 + 质量检查通过 | “本次任务已由模型服务成功执行，并通过当前质量检查。” |
| provider timeout | “本次模型调用超时，任务未完成。请稍后重试或提高超时时间。” |
| provider_mock | “本次为模拟执行结果，不能作为真实交付依据。” |
| verification_mode=simulate | “当前验证方式为模拟验证，建议配置真实验证命令。” |
| quality_gate_passed=false | “本次运行被质量检查拦截，请查看技术日志定位原因。” |

### 8.2 第二阶段：AI 摘要

后续接入 AI 摘要能力。

推荐模式：

```text
用户点击“生成 AI 摘要”
↓
后端读取 run/task/project/deliverable/approval 信息
↓
调用 DeepSeek 生成中文 Markdown
↓
保存摘要
↓
前端展示
```

AI 摘要要求：

- 全中文。
- 不输出 JSON。
- 不输出英文内部字段。
- 不输出 prompt contract。
- 不输出模型路由细节，除非用户选择“技术摘要”。
- 必须包含：
  - 本次任务目标
  - 执行结果
  - 验证结果
  - 风险提醒
  - 下一步建议

### 8.3 摘要保存与过期策略

AI 摘要不能每次刷新都生成。

建议：

- 没有摘要时显示“生成 AI 摘要”。
- 已有摘要时显示摘要。
- 运行数据变化后标记“摘要可能已过期”。
- 用户点击“重新生成摘要”才再次调用模型。
- 保存字段可后续设计为：
  - `run_user_summary`
  - `run_summary_generated_at`
  - `run_summary_source`
  - `run_summary_stale`

---

## 9. 日志处理规则

### 9.1 不允许默认展示原始英文长日志

默认摘要中不得出现：

- `Execution:`
- `OpenAI-compatible provider`
- `provider_mock`
- `prompt_contract`
- `chat_completions`
- `fallback_applied`
- `routing_score_breakdown`
- 原始 JSON

除非是在技术日志弹窗中。

### 9.2 日志需要格式化

技术日志弹窗中也不能一股脑原样铺文本。应进行基本格式化：

| 原始字段 | 展示方式 |
|---|---|
| provider_key=deepseek | 模型服务：DeepSeek |
| model_name=deepseek-v4-pro | 模型：deepseek-v4-pro |
| provider_receipt_id | 模型回执：已生成，支持复制 |
| fallback_applied=True | 降级执行：是 |
| verification_mode=simulate | 验证方式：模拟验证 |
| quality_gate_passed=True | 质量检查：通过 |
| token_accounting_mode=provider_reported | 用量统计：模型服务返回 |

### 9.3 原始日志保留但降级

原始日志仍然重要，但只能作为弹窗内最后部分：

```text
原始日志
以下为系统原始日志，主要供排查问题使用。
```

---

## 10. 中文化标准

### 10.1 中文优先原则

所有用户默认可见内容必须中文优先。

允许保留英文的情况：

- 模型名称：`deepseek-v4-pro`
- 技术 ID：`run_id`、`task_id`
- 命令：`npm run build`
- 文件路径
- API 路径
- token

其余内部词汇尽量中文化。

### 10.2 术语表

| 技术词 | 用户侧中文 | 技术日志中可用 |
|---|---|---|
| task | 任务 | task_id |
| run | 运行 | run_id |
| provider | 模型服务 | provider_key |
| model | 模型 | model_name |
| fallback | 降级执行 | fallback_applied |
| provider_mock | 模拟模型 | provider_mock |
| quality gate | 质量检查 | quality_gate_passed |
| verification | 验证 | verification_mode |
| prompt | 提示词 | prompt_template_key |
| contract | 技术约束 | prompt contract |
| token | 模型用量 | token |
| receipt | 模型回执 | provider_receipt_id |
| route | 分配 / 调度 | route_reason |
| cost | 估算成本 | estimated_cost |
| deliverable | 交付件 | deliverable_id |
| approval | 审批 | approval_id |

### 10.3 标题替换建议

| 当前标题 | 建议标题 |
|---|---|
| 运行约束详情 | 技术执行信息 |
| 诊断信息 | 技术诊断 |
| 分配评分 | 调度评分 |
| 供应商 | 模型服务 |
| 提示词模板 | 提示词模板 |
| 计算来源 | 用量统计来源 |
| 供应商回执 | 模型服务回执 |
| 质量闸门 | 质量检查 |
| 打开运行中心 | 查看运行详情 |
| 返回策略预览 | 查看执行策略 |
| 查看上下文 | 查看任务上下文 |

---

## 11. 建议开发阶段

### 阶段 1：运行页默认摘要与技术日志分层

目标：

- 不调用 AI。
- 前端基于现有字段生成中文规则摘要。
- 原始 `result_summary` 不再默认直接展示。
- 技术字段移动到“查看技术日志”弹窗。
- `TaskDetailRuntimeContractSection` 不再默认铺开全部诊断。
- 技术日志弹窗初版完成。

建议修改：

- `apps/web/src/pages/runs/components/RunsTaskDetailSection.tsx`
- `apps/web/src/features/task-detail/components/TaskDetailRuntimeContractSection.tsx`
- 新增：
  - `apps/web/src/pages/runs/components/RunUserSummaryCard.tsx`
  - `apps/web/src/pages/runs/components/RunTechnicalLogModal.tsx`
  - `apps/web/src/pages/runs/lib/runUserSummary.ts`
  - `apps/web/src/pages/runs/lib/runTechnicalLog.ts`

验收：

- 默认右侧详情中不再出现大段英文 provider summary。
- 用户能看到中文摘要。
- 技术日志只能通过按钮弹窗查看。
- 原始日志在弹窗中格式化显示。
- build 通过。

### 阶段 2：技术日志弹窗完善

目标：

- 日志弹窗增加分区。
- 支持复制全部、复制运行 ID、复制模型回执。
- 日志自动换行。
- JSON 格式化。
- 支持错误态、timeout、mock fallback 显示。

验收：

- provider 成功、provider timeout、provider_mock、verification failed 都能清楚显示。
- 日志不撑破页面。
- 不再用折叠块承载主要日志。

### 阶段 3：AI 运行摘要生成

目标：

- 后端新增 AI 摘要生成能力。
- 由用户点击触发，不自动刷新触发。
- 摘要保存。
- 支持重新生成。
- 支持摘要过期提示。

建议新增后端能力：

- `POST /runs/{run_id}/user-summary`
- `GET /runs/{run_id}/user-summary`

或者复用已有任务详情接口扩展字段，但不建议一开始大改 DTO。

验收：

- AI 生成全中文 Markdown 摘要。
- 不输出 JSON。
- 不输出英文 prompt contract。
- 不输出过度技术字段。
- 摘要能保存并重新打开。
- DeepSeek timeout 时清楚失败，不 fallback mock 伪造摘要。

### 阶段 4：交付件 / 审批联动摘要

目标：

运行摘要中显示：

- 是否生成交付件。
- 交付件标题。
- 是否创建审批。
- 审批状态。
- 用户下一步应点击哪个按钮。

验收：

- 成功 run 后摘要提示“已生成交付件并进入审批”。
- 失败 run 后摘要提示“未生成交付件和审批”。
- mock fallback 不显示为真实交付。

### 阶段 5：全站中文化与按钮治理

目标：

- 运行页、任务页、交付物页、审批页标题和按钮统一中文。
- 生涩内部词汇降级到技术日志。
- 用户默认路径清楚。
- 技术用户仍能查看细节。

---

## 12. 后续开发标准

### 12.1 每次只做一个阶段

不要一次性做完 AI 摘要、日志弹窗、全站中文化。

推荐顺序：

1. 运行页规则摘要 + 技术日志弹窗。
2. 技术日志弹窗完善。
3. AI 运行摘要生成。
4. 项目页 AI 总结。
5. 项目创建 AI 对话。
6. AI 配置助手。
7. 全站中文化收口。

### 12.2 不要破坏真实闭环

任何前端显示改造不得破坏：

- provider live execution。
- timeout 不 fallback mock 成功。
- 自动交付件。
- 自动审批。
- 项目上下文。
- run/task 路由。
- existing API paths。

### 12.3 不要隐藏问题

如果运行失败，应直接告诉用户失败，而不是包装成成功。

如果是模拟验证，应明确提示：

```text
当前为模拟验证，不代表代码真实构建通过。
```

如果是 mock 执行，应明确提示：

```text
本次为模拟模型执行，不能作为真实交付依据。
```

如果是 DeepSeek timeout，应明确提示：

```text
模型服务请求超时，本次未完成。请稍后重试或检查网络/服务状态。
```

### 12.4 用户摘要必须可解释

用户摘要不能只是“任务已完成”。

必须至少说明：

- 谁执行的。
- 完成什么。
- 验证是否可信。
- 有什么风险。
- 下一步做什么。

---

## 13. 第一阶段建议实现指令摘要

后续可以从本文拆出第一条 Codex 指令，目标如下：

```text
请基于当前 origin/main 实现“运行页用户摘要 + 技术日志弹窗”第一阶段。

目标：
1. 在运行详情右侧新增中文用户摘要卡片。
2. 默认不再直接展示 raw result_summary / verification_summary / route_reason 长文本。
3. 新增“查看技术日志”按钮。
4. 点击后打开格式化技术日志弹窗。
5. 弹窗包含执行轨迹、模型调用、质量检查、用量成本、原始日志/字段。
6. 不调用 AI，先用现有字段生成规则摘要。
7. 不改后端、不改 API、不改数据库。
8. 不破坏项目上下文、运行跳转、交付件/审批跳转。
9. apps/web build 通过。
```

---

## 14. 验收标准总表

| 验收项 | 标准 |
|---|---|
| 默认摘要 | 中文、白话、无大段英文内部字段 |
| 技术日志 | 通过弹窗查看，不默认铺开 |
| 原始日志 | 弹窗内格式化，支持复制 |
| provider 成功 | 显示真实模型成功 |
| provider timeout | 显示模型服务超时，不伪装成功 |
| provider_mock | 明确显示模拟执行，不作为真实交付依据 |
| 模拟验证 | 明确提示模拟验证不等于真实构建通过 |
| 交付件 | 成功 run 后能跳转查看 |
| 审批 | 成功 run 后能跳转查看 pending approval |
| 中文化 | 默认用户界面中文优先 |
| 技术字段 | 降级到技术日志弹窗 |
| 页面布局 | 不再被长日志撑坏 |
| build | 前端 build 通过 |
| 真实闭环 | 不破坏后端 P0 数据闭环 |

---

## 15. 结论

运行页下一步不应该继续堆字段，也不应该只做颜色和间距美化。真正目标是：

```text
把运行页从“开发调试页”改成“AI 执行结果工作台”。
```

具体来说：

- 用户默认看到中文结果摘要。
- 用户知道下一步该做什么。
- 技术信息进入日志弹窗。
- 原始日志保留但不干扰主界面。
- AI 摘要后续按需生成并保存。
- 懂技术的用户可以深入查看，不懂技术的用户也能完成审核。

这份报告作为后续开发标准，后续每个子阶段必须围绕”用户摘要 / 操作建议 / 技术日志弹窗”三层模型推进。

---

## 16. 阶段实施记录

### 阶段 1：运行页规则摘要 + 技术日志弹窗第一阶段

**实施日期**：2026-05-17
**提交哈希**：`9cefbe6`
**Build 结果**：通过（tsc + vite build，3.14s）

#### 已实现的审计建议

| 审计建议 | 实现情况 |
|---|---|
| 默认展示中文用户摘要（规则摘要，不调用 AI） | 已实现 - `RunUserSummaryCard` + `runUserSummary.ts` |
| 默认不展示大段英文 raw result_summary | 已实现 - 从 header 移除 line-clamp-2 原始文本 |
| 新增”查看技术日志”按钮 | 已实现 - 按钮在操作栏中，data-testid=`open-tech-log-modal` |
| 技术日志弹窗含 8 个分区 | 已实现 - 状态概览/执行轨迹/模型调用/质量检查/用量成本/交付件与审批（含免责说明）/原始摘要/原始字段 |
| 弹窗支持复制运行 ID、复制全部日志 | 已实现 - 弹窗 header 含复制全部 + 复制运行 ID 按钮 |
| 长 ID 自动换行、不撑破页面 | 已实现 - break-all + truncate + max-h-96 overflow-y-auto |
| raw result_summary / verification_summary / route_reason 移入弹窗 | 已实现 - 进入弹窗”原始摘要”+”原始字段”分区 |
| provider 真实成功有中文说明 | 已实现 - “模型服务 DeepSeek 已真实执行成功”（需满足 receipt_id 存在等条件） |
| provider timeout 有中文说明 | 已实现 - “模型请求超时，本次未完成或需要重试”（仅由文本关键字判定） |
| mock 执行明确标记 | 已实现 - “模拟模型执行，不能作为真实交付依据” |
| fallback 执行明确标记 | 已实现 - “发生降级执行，不能作为真实交付依据” |
| 模拟验证明确提示 | 已实现 - “当前为模拟验证，不代表代码真实构建通过” |
| 质量检查拦截提示 | 已实现 - “本次运行被质量检查拦截，请查看技术日志定位原因” |
| TaskDetailRuntimeContractSection 诊断文本分层 | 已实现 - `hideRawDiagnosticTexts` prop，默认页不展示原始长文本 |
| 不破坏现有按钮闭环 | 已验证 - 策略预览/运行中心/复制任务ID/复制运行ID 保持不变 |
| 不破坏现有 data-testid | 已验证 - 原有 testid 全部保留，新增按钮补 testid |

#### 暂未实现的审计建议

| 建议 | 原因 | 后续阶段 |
|---|---|---|
| AI 摘要生成（调用 DeepSeek 生成中文 Markdown） | 阶段 1 目标仅为规则摘要 | 阶段 2 |
| 摘要保存与过期策略 | 需要后端支持 | 阶段 2 |
| 交付件/审批 ID 实时展示（需接口支持） | 当前 `ConsoleRun` 不含 deliverable_id/approval_id | 阶段 4 |
| 弹窗内交付件/审批跳转按钮 | 前端暂未持有 deliverable_id/approval_id 字段 | 阶段 4 |
| 全站中文化 | 仅完成运行页摘要中文化 | 阶段 6 |
| 术语统一（Provider→模型服务等全站替换） | 仅运行页范围内替换 | 阶段 6 |

#### 后续待做

1. **阶段 2**：接入 AI 摘要生成后端接口，支持”生成 AI 摘要”按钮
2. **阶段 2**：摘要保存、过期标记、重新生成
3. **阶段 4**：弹窗内增加交付件/审批 ID 展示与跳转入口
4. **阶段 6**：全站术语统一、按钮治理、空状态引导

#### 修改文件清单

- `apps/web/src/pages/runs/lib/runUserSummary.ts` — 新增
- `apps/web/src/pages/runs/lib/runTechnicalLog.ts` — 新增
- `apps/web/src/pages/runs/components/RunUserSummaryCard.tsx` — 新增
- `apps/web/src/pages/runs/components/RunTechnicalLogModal.tsx` — 新增
- `apps/web/src/pages/runs/components/RunsTaskDetailSection.tsx` — 修改
- `apps/web/src/features/task-detail/components/TaskDetailRuntimeContractSection.tsx` — 修改

### 阶段 1 返工：修正规则摘要误判与技术日志语义过度承诺

**返工日期**：2026-05-17
**返工提交哈希**：`95d4bd3`

#### 修正内容

| 问题 | 修正 |
|---|---|
| timeout 误判 - failure_category="execution_failed" 被当作 timeout | timeout 仅由 result_summary/verification_summary/route_reason 中明确包含 timeout/timed out/超时 判定 |
| 真实模型成功缺少 provider_receipt_id 检查 | 新增 receipt_id 必要条件；无 receipt 时显示"运行已完成，但未确认模型服务回执" |
| mock/fallback 文案混淆 - "模拟 / 降级执行"合并描述 | mock 与 fallback 分别说明，各有独立 warning |
| 技术日志"模型名称"字段用 provider_key 填充 | 改为"模型服务 Key：{provider_key}" + "模型名称：未记录（ConsoleRun 暂不携带 model_name 字段）" |
| 执行轨迹对所有 succeeded run 声称"已生成交付件""已创建审批记录" | 改为条件表述："运行成功。若后端自动交付件/审批闭环已生效，请前往交付件页和审批页确认。" |
| "交付件与审批"分区暗示已持有 deliverable_id/approval_id | 新增免责说明："当前运行记录未携带交付件 / 审批 ID（ConsoleRun 暂不包含 deliverable_id / approval_id 字段）。请到交付件页或审批页按项目查看后端自动生成结果。" |
| 文档回填中"模拟/降级执行"合并表述 | 已拆分为 mock 和 fallback 各自独立的已实现条目 |

### 阶段 1B：摘要卡片视觉风格收口

**日期**：2026-05-17

阶段 1B 已完成摘要卡片视觉收口：移除 RunUserSummaryCard 中所有 emerald/amber/rose 强彩色状态块，统一为中性灰黑线条式后台风格。执行模式 badge、警告区域、状态标签均改为 zinc 灰阶 + 细边框，不再使用彩色语义色。信息层级保留，结论/完成内容/注意事项/建议下一步分区不变。

### 阶段 2B-R3：运行摘要来源文案收口

**日期**：2026-05-18
**提交哈希**：`2f35394`（完整：`2f35394d84375df298f49924d31d74e805c3f924`）
**Build 结果**：通过（tsc + vite build）

#### 已实现

| 项目 | 说明 |
|---|---|
| 运行页摘要卡片 | 当前只展示一张"运行摘要"主卡片（`RunPrimarySummaryCard`） |
| 单卡片模式 | AI 成功摘要和规则兜底不会双卡片并列，只展示一张主卡片 |
| 文案收口 | 已从"AI 摘要"/"AI 摘要已保存"/"生成 AI 摘要"收口为"运行摘要 / 摘要来源" |
| source=rule_fallback 展示 | 明确显示"摘要来源：规则回退 · 尚未调用真实 AI" |
| source=ai 预留 | 显示"摘要来源：AI 生成 · {model_provider 或 model_name}"，2C 阶段启用 |
| 按钮文案 | "生成运行摘要"/"重新生成摘要"/"生成中…"，不再使用"生成 AI 摘要" |
| 错误/空状态文案 | 统一展示"运行摘要服务暂不可用"/"摘要生成失败"/"当前显示本地规则摘要" |
| 任务执行与摘要生成区分 | 原始 run 的模型执行来源和摘要生成来源在 UI 上明确区分 |
| 技术日志弹窗 | 保持不变，仍可打开/关闭/复制 |
| 视觉风格 | 保持中性灰黑线条式（border-[#333333]/bg-[#0f0f0f]/text-zinc-*），无强彩色/醒目 AI 图标/发光/渐变 |
| Footer 说明 | "当前阶段的保存摘要由规则回退生成；真实 AI 摘要将在后续阶段接入。" |

#### 修改文件清单

- `apps/web/src/pages/runs/components/RunPrimarySummaryCard.tsx` — 修改
- `apps/web/src/pages/runs/api/runAiSummary.ts` — 修改

### 阶段 2B-R5：运行摘要正文技术噪音收口

**日期**：2026-05-18
**提交哈希**：`ba8b005`（完整：`ba8b005c8d434739faa5df40649be99f5451f360`）
**Build / 测试结果**：后端 16 测试通过，前端 build 通过

#### 已实现

| 项目 | 说明 |
|---|---|
| 摘要正文技术噪音收口 | 默认摘要正文不再展示完整 source_fingerprint / prompt_hash |
| 技术依据章节 | 改为 "摘要依据：运行状态、结果摘要、验证摘要、质量检查、模型服务记录" + "调试指纹：已记录，可在前端状态条或技术日志中查看完整值" |
| Markdown 五标题 | 保持不变（运行结论/已完成内容/风险与注意事项/下一步建议/技术依据） |
| 前端状态条 | 仍保留 8 位短 hash + title 悬停完整值 |
| 规则回退 | 当前仍为 rule_fallback，不真实调用 AI |
| 技术日志弹窗 | 保持不变 |

#### 修改文件清单

- `runtime/orchestrator/app/services/run_ai_summary_service.py` — 修改

### 阶段 2C-A：真实 AI 摘要后端最小闭环

**日期**：2026-05-18
**提交哈希**：`bdfd6ed`（完整：`bdfd6edde8f1ba591e57724d25e7c71887ca14a4`）
**Build / 测试结果**：后端 28 测试通过，前端 build 通过

#### 已实现

| 项目 | 说明 |
|---|---|
| AI 优先生成 | Provider 配置存在时优先尝试真实 AI 生成，成功则 source=ai |
| 规则回退兜底 | AI 失败/超时/未配置/格式不合格时自动回退 source=rule_fallback |
| GET 只读 | GET 不触发 AI，只返回 active_summary |
| POST 触发生成 | POST generate / regenerate 优先尝试 AI |
| Markdown 校验 | 校验五标题、无代码块包裹、无 JSON、非空、长度上限 |
| 前端无改动 | 现有 RunPrimarySummaryCard 无需修改，根据 source 字段自动区分展示 |
| 不改 worker | worker/provider 主执行流程不变 |

#### 修改文件清单

- `runtime/orchestrator/app/services/openai_provider_executor_service.py` — 新增 generate_text()
- `runtime/orchestrator/app/services/run_ai_summary_service.py` — AI 优先 + fallback + 校验
- `runtime/orchestrator/app/api/routes/runs.py` — DI 注入
- `runtime/orchestrator/tests/test_run_ai_summaries.py` — 新增 12 个测试

### 阶段 2C-A-R1：Provider/env/prompt_hash/provider_key 硬化

**日期**：2026-05-18
**提交哈希**：`914b404`（完整：`914b404d249185eae75b3046438414aebab14f6e`）
**Build / 测试结果**：后端 35 测试通过，前端 build 通过

#### 已实现

| 项目 | 说明 |
|---|---|
| ProviderConfigService 注入 | 始终注入，不再依赖配置文件存在 |
| env-only provider | 仅环境变量配 api_key 也能触发 AI |
| AI prompt_hash | source=ai 使用实际 AI prompt hash，与规则 fallback 区分 |
| rule_fallback prompt_hash | 保持稳定，使用规则 prompt hash |
| generate_text provider_key | 不再硬编码 openai，传递 detected_provider_type |
| 前端无改动 | 现有 UI 无需修改 |

#### 修改文件清单

- `runtime/orchestrator/app/api/routes/runs.py` — 修改
- `runtime/orchestrator/app/services/run_ai_summary_service.py` — 修改
- `runtime/orchestrator/app/services/openai_provider_executor_service.py` — 修改
- `runtime/orchestrator/tests/test_run_ai_summaries.py` — 新增 7 个测试

### 阶段 2C-A-R2：测试补强与文档追溯修正

**日期**：2026-05-18
**提交哈希**：`976d1a2`
**Build / 测试结果**：后端 35 测试通过，前端 build 通过

#### 已实现

| 项目 | 说明 |
|---|---|
| 文档哈希修正 | 2C-A-R1 哈希从 `915f0a9` 修正为 `914b404` 完整哈希 |
| provider_key 测试 | 已真正 monkeypatch generate_text，覆盖 _call_provider_text 路径 |
| env-only 测试 | 不再用 ai_text_generator，真正走 provider_config_service + generate_text |
| 无 config fallback | 保留并确认 |

#### 修改文件清单

- `runtime/orchestrator/tests/test_run_ai_summaries.py` — 重写 2 个测试
- `docs/product/` 3 份 — 修正哈希 + 追加记录

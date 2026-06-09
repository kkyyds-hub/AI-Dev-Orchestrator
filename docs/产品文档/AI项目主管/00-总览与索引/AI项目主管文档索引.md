# AI 项目主管文档索引

> **生成日期**: 2026-06-07
> **整理前基准**: `a4fea97b2b2ad8fa1a9b53308687306ffe9c2adb`（P4 final gate in ledger）
> **文档目录治理 R1**: `fbb1518ab1405148ecbeea465491180e1644ed33`
> **本文档 R1-Fix**: 以下新增第 6、7 节；修复旧路径引用

**当前状态**: 文档目录治理 R1: Pass；P5: Pass；P6: Pass；P7-A 至 P7-D: Pass；P7-E/F/G/H/I/J Final scoped gate: Pass；P7 Final Gate: Pass（Project Director Conversation Hub + Governance total closure）；P8-A: Pass（Executor Config Discovery ledger + current-state audit）；P8-B: Pass（ExecutorProfile / DiscoveryResult contract freeze）；P8-C: Pass（safe discovery service 最小实现）；P8-D: Pass（read-only API + backend readback）；P8-E: Pass（launch preview contract + preview-only API）；P8-Final: Pass（targeted evidence + P8 Gate）；P8 Executor Config Discovery: Pass；P9-A: Pass（Controlled Runtime ledger + current-state audit + safety boundary）；P9-B: Pass（ExecutorRuntimeSession / RuntimeState / RuntimeEvent 纯 domain contract）；P9-C: Pass（RuntimeSafetyGate / LaunchRequest / LaunchApproval 纯 domain contract）；P9-D: Pass（ControlledRuntimeService skeleton + FakeExecutorAdapter + in-memory event recorder）；P9-E: Pass（read-only runtime API + fake launch request preview API）；P9-F: Pass（frontend read-only fake runtime readback）；P9-G: Pass（fake-only dry-run E2E evidence）；P9-H: Pass（real executor pilot gate design；still default off）；P9-Final: Pass（targeted evidence + P9 scoped gate）；P9 scoped closure: Pass（fake dry-run + pilot gate design）；P9 real executor launch: Not started；GitWrite-A: Pass（产品运行时 Git 写闭环 ledger + current-state audit + safety boundary）；GitWrite-B: Pass（pure domain contract only）；GitWrite-C: Pass（dry-run preview service）；GitWrite-D: Pass（read-only API + approval readback）；GitWrite-E: Pass（frontend readback panel）；GitWrite-F: Pass（disabled adapter seam）；GitWrite-G: Pass（fake adapter evidence；fake only）；GitWrite-Final: Not started；GitWrite implementation: Partial（GitWrite-B/C/D/E/F/G complete through fake evidence only；no real adapter/write）；产品运行时 Git 写操作: Not started；AI Project Director 总闭环: Partial

---

## 1. 文档目录结构

```
docs/产品文档/AI项目主管/
  00-总览与索引/          ← 本文档所在
  01-总规划与路线/         ← P1-P7 路线、差距分析、执行台账
  02-页面与产品基线/       ← 页面信息架构、闭环流程、验收清单
  03-P1-P3运行生命周期/    ← P1 工作树、P2 工作区上下文、P3 运行生命周期
  04-P4交付预览与人工确认/  ← P4 Git Delivery + Human Approval Gate 全链路
  05-P5失败回流/           ← P5 已完成（Pass）
  06-P6智能体调度/         ← P6 已完成（Pass）
  07-P7主管对话与治理/     ← P7 Final Gate: Pass（Project Director Conversation Hub + Governance total closure）
  08-历史验证与证据/       ← 历史阶段验证文档（工作台/Worker/失败/治理/工作树）
  09-历史归档/            ← 已冻结的历史文档（审计/freeze/gap）
  10-P8执行器配置发现/     ← P8-A/B/C/D/E/Final: Pass；P8 Executor Config Discovery: Pass；P9: Not started
  11-P9受控运行时与执行器调度/ ← P9-A/B/C/D/E/F/G/H/Final: Pass；P9 scoped closure: Pass；P9 real executor launch: Not started
  12-产品运行时Git写闭环/ ← GitWrite-A/B: Pass；GitWrite implementation: Partial（pure domain contract only；no write）
```

---

## 2. 各目录用途

### 00-总览与索引

当前文档索引。所有进入 AI 项目主管文档区的人应先查看此文件。

### 01-总规划与路线

P1-P7 路线校准文档、理想差距分析报告、执行计划台账。P8/P9 外部执行器路线也已纳入。

**关键入口**：
- [P1-P7参考规划复用说明书](../01-总规划与路线/P1-P7参考规划复用说明书.md) — 总路线校准，后续指令必须遵守
- [P8-P9外部执行器配置与运行时规划](../01-总规划与路线/P8-P9外部执行器配置与运行时规划-20260607.md) — P8 Executor Config + P9 Controlled Runtime 路线
- [AI项目主管理想差距分析-P1后-20260605](../01-总规划与路线/差距分析/AI项目主管理想差距分析-P1后-20260605.md) — 差距报告

### 02-页面与产品基线

产品页面职责与布局设计、闭环流程、验收清单。

**关键入口**：
- [页面信息架构-20260518](../02-页面与产品基线/页面信息架构-20260518.md) — 最高产品基线
- [闭环流程-20260518](../02-页面与产品基线/闭环流程-20260518.md)
- [闭环验收清单-20260518](../02-页面与产品基线/闭环验收清单-20260518.md)

### 03-P1-P3运行生命周期

P1 Coding Session + Worktree Lifecycle、P2 Worker Context + Runtime Safe Execution、P3 Runtime Lifecycle Evidence + Event Audit。

### 04-P4交付预览与人工确认

P4 Git Delivery Preview + Human Approval Gate 的完整链路文档。

**关键入口**：
- [P4交付预览与人工确认总账-20260607](../04-P4交付预览与人工确认/P4交付预览与人工确认总账-20260607.md) — P4 阶段唯一总账，所有 P4 证据统一追加至此

### 05-P5失败回流

P5 Failure Recovery / 失败回流。**已完成（Pass）。**

**关键入口**：
- [P5失败回流总账与阶段设计-20260607](../05-P5失败回流/P5失败回流总账与阶段设计-20260607.md) — P5 阶段唯一总账，所有 P5 证据统一追加至此

### 06-P6智能体调度

P6 Agent Orchestration / AI 主管调度。**已完成（Pass）。**（P6 scoped gate：结构化调度建议/audit timeline/response 只读透传/前端只读展示，不含自动派发/retry/Git 写/P7。）

**关键入口**：
- [P6智能体调度总账与阶段设计-20260607](../06-P6智能体调度/P6智能体调度总账与阶段设计-20260607.md) — P6 阶段唯一总账，所有 P6 证据统一追加至此

### 07-P7主管对话与治理

P7 Final Gate: Pass。Project Director Conversation Hub + Governance total closure。

**关键入口**：
- [P7主管对话与治理总账与阶段设计-20260607](../07-P7主管对话与治理/P7主管对话与治理总账与阶段设计-20260607.md) — P7 阶段唯一总账，所有 P7 证据统一追加至此
- [P7对话中枢设计-20260603](../07-P7主管对话与治理/P7对话中枢设计-20260603.md) — 历史 Stage 7-B0 设计基线（不删除）
- [P7对话中枢审计-20260603](../07-P7主管对话与治理/P7对话中枢审计-20260603.md) — 历史 Stage 7-B 审计基线（不删除）

### 10-P8执行器配置发现

P8 Executor Config Discovery 已完成（Pass）。P8-A/B/C/D/E/Final 全部 Pass。Registry / Readback / Launch Preview 全部完成。P9 Controlled Runtime 仍 Not started。

**关键入口**：
- [P8执行器配置发现总账与阶段设计-20260608](../10-P8执行器配置发现/P8执行器配置发现总账与阶段设计-20260608.md) — P8 阶段唯一总账，所有 P8 证据统一追加至此

### 11-P9受控运行时与执行器调度

P9-A 至 P9-Final 全部 Pass。P9 scoped closure: Pass（fake dry-run + pilot gate design）。P9 real executor launch 仍 Not started。产品运行时 Git 写操作 仍 Not started。AI Project Director 总闭环 仍 Partial。

**关键入口**：
- [P9受控运行时与执行器调度总账与阶段设计-20260608](../11-P9受控运行时与执行器调度/P9受控运行时与执行器调度总账与阶段设计-20260608.md) — P9 阶段唯一总账，所有 P9 证据统一追加至此

### 12-产品运行时Git写闭环

GitWrite-A Ledger + Current-State Audit 已完成（Pass）。GitWrite-B pure domain contract 已完成（Pass）。GitWrite-C/D/E/F/G/Final 仍 Not started。**GitWrite implementation: Partial（GitWrite-B pure domain contract only；no write）。**

**关键入口**：
- [Git写闭环总账与阶段设计-20260608](../12-产品运行时Git写闭环/Git写闭环总账与阶段设计-20260608.md) — GitWrite 阶段唯一总账

### 08-历史验证与证据

历史阶段（P1-P3 期间及更早）的验证文档。

子目录：
- 工作台链路/ — 工作台会话、目标确认、计划生成、任务创建
- Worker运行/ — 任务派发、Worker 运行、Provider、运行证据
- 失败闭环/ — 失败收口、审批、交付物、仓库证据
- 治理中心/ — 角色、技能、成本、总门、全站按钮
- 阶段审计/ — Phase1/Phase2 验证、Stage4/Stage6/Stage7
- 工作树/ — P1 工作树创建/清理/预检验证

### 09-历史归档

已冻结的历史文档：审计报告、后端闭环缺口冻结、Stage 审计。

---

## 3. P4 当前状态

| 子阶段 | 内容 | Gate |
|--------|------|------|
| P4-B | Git Diff Dry-run evidence | Pass |
| P4-C | Git Operation Dry-run Preview | Pass |
| P4-D | Delivery Gate Evidence | Pass |
| P4-E2 | 前端只读展示 | Pass |
| P4-F1 | Human Approval Gate 纯域模型 | Pass |
| P4-F2-A | WorkerRunResult / WorkerRunOnceResponse 只读透传骨架 | Pass |
| P4-F2-B | Human Approval API 设计 | Pass |
| P4-F2-C0 | Evidence Snapshot Source | Pass |
| P4-F2-C | Approval API | Pass |
| P4-F2-D | Approval Audit / AgentMessage | Pass |
| P4-F3 | Frontend Confirmation Entry | Pass |
| P4-F4 | Human Approval E2E Closure / Minimal Verification | Pass |
| **P4 Final Gate** | **Pass** | — |
| P5 | Failure Recovery | **Pass** |
| P6 | Agent Orchestration | **Pass**（scoped：调度建议/audit/只读透传/前端展示，不含自动派发/retry/Git 写） |
| P7-A | Conversation Hub + Governance Ledger + Stage Design | **Pass** |
| P7-B | Current-state audit / contract freeze | **Pass** |
| P7-C | Conversation/ConversationList contract | **Pass** |
| P7-D | DirectorInbox / cross-page intake contract | **Pass** |
| P7-E Final | ConversationRouter + DirectorContextAssembler governance scoped gate | **Pass** |
| P7-F Final | UserChallenge / Intervention scoped closure | **Pass** |
| P7-G Final | PlanRevision / DirectorActionProposal / ProposalApproval scoped closure | **Pass** |
| P7-H Final | Conversation-to-Task / Conversation-to-Plan scoped closure | **Pass** |
| P7-I Final | Workbench multi-conversation hub frontend scoped closure | **Pass** |
| P7-J Final | targeted evidence + UAT seed scoped closure | **Pass** |
| **P7 Final Gate** | Project Director Conversation Hub + Governance total closure | **Pass** |
| **P8-A** | Executor Config Discovery ledger + current-state audit + safety boundary | **Pass** |
| **P8-B** | ExecutorProfile / DiscoveryResult contract freeze | **Pass** |
| **P8-C** | safe discovery service 最小实现 | **Pass** |
| **P8-D** | read-only API + backend readback | **Pass** |
| **P8-E** | Launch preview contract + preview-only API | **Pass** |
| **P8-Final** | targeted evidence + P8 Gate | **Pass** |
| **P8 Executor Config Discovery** | Registry + Discovery + API + Launch Preview | **Pass** |
| **P9-A** | Controlled Runtime ledger + current-state audit + safety boundary | **Pass** |
| **P9-B** | ExecutorRuntimeSession / RuntimeState / RuntimeEvent 纯 domain contract | **Pass** |
| **P9-C** | RuntimeSafetyGate / LaunchRequest / LaunchApproval 纯 domain contract | **Pass** |
| **P9-D** | ControlledRuntimeService skeleton + FakeExecutorAdapter + in-memory event recorder | **Pass** |
| **P9-E** | read-only runtime API + fake launch request preview API | **Pass** |
| **P9-F** | frontend read-only fake runtime readback | **Pass** |
| **P9-G** | fake-only dry-run E2E evidence | **Pass** |
| **P9-H** | real executor pilot gate design（still default off） | **Pass** |
| **P9-Final** | targeted evidence + P9 scoped gate | **Pass** |
| **P9 scoped closure** | P9-A/B/C/D/E/F/G/H/Final 全部 Pass；fake dry-run + pilot gate design | **Pass** |
| **P9 real executor launch** | 真实 Codex / Claude Code / DeepSeek executor launch | **Not started** |
| **GitWrite-A** | 产品运行时 Git 写闭环 ledger + current-state audit + safety boundary | **Pass** |
| **GitWrite-B** | GitWriteIntent / GitWritePreview / GitWriteApproval pure domain contract | **Pass** |
| **GitWrite-C** | dry-run preview service | **Pass** |
| **GitWrite-D** | read-only API + approval readback | **Pass** |
| **GitWrite-E** | frontend readback panel；no write | **Pass** |
| **GitWrite-F** | disabled adapter seam；no write | **Pass** |
| **GitWrite-G** | fake adapter evidence + readback helper；fake only；no real write | **Pass** |
| **GitWrite-Final** | targeted evidence + scoped gate | **Not started** |
| **GitWrite implementation** | GitWrite-B/C/D/E/F/G complete through fake evidence only；no real adapter/write | **Partial** |
| **产品运行时 Git 写操作** | 产品内部 git add/commit/push/PR/merge/branch/delete/reset/checkout/rebase/stash/tag/CI 自动触发 | **Not started** |
| **AI Project Director 总闭环** | — | **Partial** |

---

## 4. 文档治理规则

从 P4 ledger 建立时起，执行以下规则：

| 场景 | 文档策略 |
|------|---------|
| 总路线 / 产品基线 / 阶段重排 | 可新建文档 |
| 高风险新设计（需对齐多个模块） | 可新建设计文档 |
| 普通实现（Bug fix / feature / 小功能） | **不新建 closure 文档** |
| 小修正 / R1 / R2 / R3 | **不新建文档，只追加到阶段 ledger** |
| 阶段内证据记录 | **统一追加到阶段 ledger** |
| 大阶段完成 | **只写一份总 closure（可在 ledger 内做 Final Gate）**，除非用户明确要求独立 closure |
| 后续给 Codex / DeepSeek 的任务指令 | **必须遵守本规则，不得要求新建零散 closure 文档** |

---

## 5. 历史文档保留原则

| 规则 | 说明 |
|------|------|
| 不删除历史文档 | 所有文档通过 `git mv` 迁移，保留 git 历史 |
| 不改历史 Gate 结论 | 文档正文中的 Gate 结论保持原样，不因目录整理而修改 |
| 不改历史正文内容 | 仅修复因迁移导致的文件路径引用，不改语义 |
| 只做归类、改名、链接修复 | 本文档整理的范围 |

---

## 6. 旧路径引用清单 / 处理原则

### 6.1 已修复的引用

以下活跃文档中的关键交叉引用已迁移到新路径：

| 文档 | 修复范围 |
|------|---------|
| P1-P7参考规划复用说明书 | 产品基线、前置文档链接 |
| P4 交付预览与人工确认总账 | 产品基线、路线文档、附录 A 文档索引 |
| P4-F1 / P4-F2-A / P4-F2-B / P4-F2-C / P4-F2-C0 / P4-F2-D / P4-F3 各阶段文档 | 产品基线、路线文档引用 |

### 6.2 历史冻结文档

历史验证文档（08-历史验证与证据）和历史归档文档（09-历史归档）内部的交叉引用可能仍指向旧的英文文件路径（`docs/product/ai-project-director/...`）。这些是冻结证据：

- **不改正文内容** — Gate 结论、证据记录保持原样。
- **不强行批量替换** — 避免大规模修改历史文档引入意外错误。
- **可通过目录结构推断** — 从旧英文文件名可映射到新中文文件名，对应关系见各目录。

### 6.3 外部目录引用

`docs/product/project-summary/` 下的文件不在本次治理范围。后续如需要，可单独做 R2。

### 6.4 新文档引用规则

从本文档生效起，后续所有任务指令、新文档、设计文档、closure 文档中引用 AI 项目主管文档路径时，**必须使用新路径**：

```text
docs/产品文档/AI项目主管/<分类目录>/<中文文件名>.md
```

严禁在新建文档中使用旧路径 `docs/product/ai-project-director/...`。

---

## 7. 后续文档治理优先级

| 优先级 | 任务 | 说明 |
|--------|------|------|
| 🔴 本次 | R1-Fix：更新索引 + 旧路径处理原则 | 本文档 |
| 🟡 R2（可选） | 整理 `docs/product/project-summary/` 下的外部引用 | 将其中指向旧 AI 项目主管文档的路径更新为新路径 |
| 🟡 R3（可选） | 为历史冻结文档生成旧路径到新路径的映射表 | 便于人工查阅，不修改历史正文 |
| ⚪ 不推荐 | 再大规模重命名 | 除非用户明确要求，否则不再做目录级 reorg |

---

## 附录：文档迁移日期

本次目录整理日期：2026-06-07。
旧路径：`docs/product/ai-project-director/`
新路径：`docs/产品文档/AI项目主管/`

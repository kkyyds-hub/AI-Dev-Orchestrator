# AI 项目主管文档索引

> **生成日期**: 2026-06-07  
> **远端基准**: `origin/main` = `a4fea97b2b2ad8fa1a9b53308687306ffe9c2adb`  
> **状态**: AI Project Director 总闭环: Partial

---

## 1. 文档目录结构

```
docs/产品文档/AI项目主管/
  00-总览与索引/          ← 本文档所在
  01-总规划与路线/         ← P1-P7 路线、差距分析、执行台账
  02-页面与产品基线/       ← 页面信息架构、闭环流程、验收清单
  03-P1-P3运行生命周期/    ← P1 工作树、P2 工作区上下文、P3 运行生命周期
  04-P4交付预览与人工确认/  ← P4 Git Delivery + Human Approval Gate 全链路
  05-P5失败回流/           ← 尚未开始
  06-P6智能体调度/         ← 尚未开始
  07-P7主管对话与治理/     ← 尚未开始（对话中枢设计文档已迁移至此）
  08-历史验证与证据/       ← 历史阶段验证文档（工作台/Worker/失败/治理/工作树）
  09-历史归档/            ← 已冻结的历史文档（审计/freeze/gap）
```

---

## 2. 各目录用途

### 00-总览与索引

当前文档索引。所有进入 AI 项目主管文档区的人应先查看此文件。

### 01-总规划与路线

P1-P7 路线校准文档、理想差距分析报告、执行计划台账。

**关键入口**：
- [P1-P7参考规划复用说明书](../01-总规划与路线/P1-P7参考规划复用说明书.md) — 总路线校准，后续指令必须遵守
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

尚未开始。P5 Failure Recovery / 失败回流。

### 06-P6智能体调度

尚未开始。P6 Agent Orchestration / AI 主管调度。

### 07-P7主管对话与治理

尚未开始。P7 Project Director Conversation Hub + Governance。对话中枢设计文档已迁移至此目录。

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
| P5 | Failure Recovery | **Not started** |
| P6 | Agent Orchestration | **Not started** |
| P7 | Project Director Conversation Hub + Governance | **Not started** |
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

## 6. 已知限制

### 6.1 历史文档交叉引用

历史验证文档（08-历史验证与证据）和历史归档文档（09-历史归档）内部的交叉引用可能仍指向旧的英文文件路径（`docs/product/ai-project-director/...`）。这些是冻结证据，不修改正文内容。可通过目录结构推断对应文档位置。

### 6.2 外部引用

`docs/product/project-summary/` 下的文件不在本次整理范围内，其中可能包含指向旧 AI 项目主管文档路径的引用。

---

## 附录：文档迁移日期

本次目录整理日期：2026-06-07。  
旧路径：`docs/product/ai-project-director/`  
新路径：`docs/产品文档/AI项目主管/`

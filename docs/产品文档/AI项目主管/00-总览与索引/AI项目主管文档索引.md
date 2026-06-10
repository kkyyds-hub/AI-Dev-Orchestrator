# AI 项目主管文档索引

> **生成日期**: 2026-06-07（原始）；DOC-CLEAN-A 大清理: 2026-06-10
> **整理前基准**: `a4fea97b2b2ad8fa1a9b53308687306ffe9c2adb`（P4 final gate in ledger）
> **DOC-CLEAN-A 基准**: `4ea372289e0385ed1e3627df99f4c9282f3952a2`（docs: add P9 real executor readback validation guide）
> **DOC-CLEAN-A 结果**: 从 120 文件减至 14 文件；删除 08/09 全部历史验证与归档；删除所有小阶段独立子文档，统一回填主 ledger；删除已被主 ledger 汇总的 P9-REL-G/H 独立证据文档

**当前状态**: P1-P7 Final Gate: Pass；P8 Executor Config Discovery: Pass；P9 scoped closure: Pass（fake dry-run + pilot gate design）；P9-REL-A~H: Pass（Real Executor Launch ledger 含 read-only API + frontend readback + pre-pilot readiness evidence + manual validation guide）；P9-RGWP-A~I: Pass；P9-RGWP-Pilot: Not started；P9-REL-Pilot: Not started；P9-REL-H actual manual validation: Not executed / waiting for user；P9 real executor launch: Not started；产品运行时 Git 写操作: Not started；GitWrite scoped closure: Scoped Pass to fake-only；AI Project Director 总闭环: Partial

---

## 1. 文档目录结构

```
docs/产品文档/AI项目主管/
  00-总览与索引/          ← 本文档所在
  01-总规划与路线/         ← P1-P7 路线校准
  02-页面与产品基线/       ← 页面信息架构、闭环流程、验收清单
  04-P4交付预览与人工确认/  ← P4 主 ledgers（子阶段文档已清理，结论在主 ledger）
  05-P5失败回流/           ← P5 主 ledger
  06-P6智能体调度/         ← P6 主 ledger
  07-P7主管对话与治理/     ← P7 主 ledger
  10-P8执行器配置发现/     ← P8 主 ledger
  11-P9受控运行时与执行器调度/ ← P9 主 ledgers + P9-REL + P9-RGWP
  12-产品运行时Git写闭环/ ← GitWrite 主 ledger
```

**已删除的目录**: `03-P1-P3运行生命周期/`（子阶段设计文档，已完成的 P1-P3 无独立 ledger，无需保留）、`08-历史验证与证据/`（40+ 早期验证文档）、`09-历史归档/`（7 份冻结审计）

---

## 2. 主入口（仅存文档）

### 01-总规划与路线
- [P1-P7参考规划复用说明书](../01-总规划与路线/P1-P7参考规划复用说明书.md) — 总路线校准，后续指令必须遵守

### 02-页面与产品基线
- [页面信息架构-20260518](../02-页面与产品基线/页面信息架构-20260518.md) — 最高产品基线
- [闭环流程-20260518](../02-页面与产品基线/闭环流程-20260518.md)
- [闭环验收清单-20260518](../02-页面与产品基线/闭环验收清单-20260518.md)

### 04-P4交付预览与人工确认
- [P4交付预览与人工确认总账-20260607](../04-P4交付预览与人工确认/P4交付预览与人工确认总账-20260607.md) — P4 唯一总账（14 份子阶段文档已删，结论在此）

### 05-P5失败回流
- [P5失败回流总账与阶段设计-20260607](../05-P5失败回流/P5失败回流总账与阶段设计-20260607.md) — P5 唯一总账

### 06-P6智能体调度
- [P6智能体调度总账与阶段设计-20260607](../06-P6智能体调度/P6智能体调度总账与阶段设计-20260607.md) — P6 唯一总账（子文档已删）

### 07-P7主管对话与治理
- [P7主管对话与治理总账与阶段设计-20260607](../07-P7主管对话与治理/P7主管对话与治理总账与阶段设计-20260607.md) — P7 唯一总账（子阶段设计文档已删）

### 10-P8执行器配置发现
- [P8执行器配置发现总账与阶段设计-20260608](../10-P8执行器配置发现/P8执行器配置发现总账与阶段设计-20260608.md) — P8 唯一总账

### 11-P9受控运行时与执行器调度
- [P9受控运行时与执行器调度总账与阶段设计-20260608](../11-P9受控运行时与执行器调度/P9受控运行时与执行器调度总账与阶段设计-20260608.md) — P9 唯一总账（P9-A ~ P9-Final）
- [P9真实执行器Git写试点总账与阶段设计-20260609](../11-P9受控运行时与执行器调度/P9真实执行器Git写试点总账与阶段设计-20260609.md) — P9-RGWP 试点阶段总账
- [P9-REL真实执行器接入总账与阶段设计-20260610](../11-P9受控运行时与执行器调度/P9-REL真实执行器接入总账与阶段设计-20260610.md) — P9-REL 唯一总账（含 P9-REL-G readiness evidence + P9-REL-H validation guide 的摘要；G/H 独立文档已删）

### 12-产品运行时Git写闭环
- [Git写闭环总账与阶段设计-20260608](../12-产品运行时Git写闭环/Git写闭环总账与阶段设计-20260608.md) — GitWrite 唯一总账

---

## 3. 全阶段 Gate 状态

| 阶段 | Gate | 备注 |
|------|------|------|
| P1-P3 | **Pass** | 运行生命周期完成 |
| P4 Final Gate | **Pass** | Git Delivery + Human Approval Gate |
| P5 | **Pass** | 失败回流 |
| P6 | **Pass** | 智能体调度（scoped） |
| P7 Final Gate | **Pass** | Conversation Hub + Governance total closure |
| P8 Final Gate | **Pass** | Executor Config Discovery |
| P9 scoped closure | **Pass** | fake dry-run + pilot gate design |
| P9-REL-A~H | **Pass** | Real Executor Launch ledger 全链（P9-REL-H actual manual validation: Not executed / waiting for user） |
| P9-RGWP-A~I | **Pass** | 真实 Git 写试点 preflight 链 |
| P9-RGWP-Pilot | **Not started** | |
| P9-REL-Pilot | **Not started** | |
| P9 real executor launch | **Not started** | |
| 产品运行时 Git 写操作 | **Not started** | |
| GitWrite scoped closure | **Scoped Pass** | fake-only |
| **AI Project Director 总闭环** | **Partial** | |

---

## 4. 文档治理规则（DOC-CLEAN-A 起生效）

| 场景 | 文档策略 |
|------|---------|
| 总路线 / 产品基线 / 阶段重排 | 可新建文档 |
| 高风险新设计（需对齐多个模块） | 可新建设计文档 |
| 普通实现（Bug fix / feature / 小功能） | **不新建 closure 文档** |
| 小修正 / R1 / R2 / R3 | **不新建文档，只追加到阶段 ledger** |
| 阶段内证据记录 | **统一追加到阶段 ledger** |
| 大阶段完成 | **只写一份总 closure（可在 ledger 内做 Final Gate）**，除非用户明确要求独立 closure |
| 小阶段 evidence / verification / validation guide | **直接回填到主 ledger 的对应子阶段段**，不得另建独立文档 |
| 人工验证环节 | **验证指引+结果回填主 ledger**，不另建验证文档（除非用户明确要求） |
| 文档大清理 | 每次大阶段结束后 / 文档超过 25 个文件时，执行一次类似 DOC-CLEAN-A 的清理 |
| 后续给 Codex / DeepSeek 的任务指令 | **必须遵守本规则，不得要求新建零散 closure 文档** |

---

## 5. DOC-CLEAN-A 清理记录

| 项目 | 值 |
|------|-----|
| 清理前文件数 | 120 |
| 清理后文件数 | 14 |
| 删除文件数 | 106 |
| 删除目录 | `03-P1-P3运行生命周期/`（12 文件）、`08-历史验证与证据/`（64 文件）、`09-历史归档/`（7 文件） |
| 删除独立子阶段文档 | P4 子阶段（15 文件）、P6 子文档（1 文件）、P7 子文档（3 文件） |
| 删除早期规划文档 | P8-P9 规划、差距分析、执行台账（3 文件） |
| 删除 standalone evidence | P9-REL-G / P9-REL-H 独立文档（2 文件，内容已汇入 P9-REL 主 ledger 8K/8L 段） |
| 删除垃圾文件 | `.DS_Store`（2 文件） |

---

## 附录：旧路径引用说明

历史验证文档（08-历史验证与证据）和历史归档文档（09-历史归档）已在 DOC-CLEAN-A 中删除。这些目录中的文档如有被代码/README 引用的，请更新引用至对应的主 ledger。

新文档引用必须使用 `docs/产品文档/AI项目主管/<分类目录>/<中文文件名>.md` 格式。

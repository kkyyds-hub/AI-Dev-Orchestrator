# Coding Session Git Delivery Lifecycle P4-F1 Human Approval Gate 纯域模型收口

> **文档类型**: P4-F1 阶段收口审计 + Gate 证据  
> **生成日期**: 2026-06-06  
> **远端基准**: `origin/main` = `07a32a3ec32819b6fdccba61c844c76d0f1abe07`  
> **主产品基线**: `docs/product/ai-project-director/page-information-architecture-20260518.md`  
> **前置文档**: `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4e2-closure-and-p4f-human-approval-gate-design-20260606.md`  
> **边界**: 本轮只做 P4-F1 收口复核与文档回填；不改 Python 业务代码、不改 API、不改 Worker、不改前端、不改数据库 / migration、不写 AgentMessage、不实现 approval API、不实现确认按钮、不实现产品运行时 `git add` / `git commit` / `git push` / PR。  
> **状态**: P4-F1 Closure: Pass；P4-F2: Not started；AI Project Director 总闭环: Partial

---

## 0. 本轮范围

本轮目标是对已提交到 GitHub `origin/main` 的 P4-F1 纯域模型做只读复核，并补齐阶段收口证据。

本轮只确认以下事项：

1. `origin/main` 已包含 P4-F1 两个文件。
2. P4-F1 实现符合“纯域模型”边界。
3. P4-F1 targeted tests 通过。
4. P4-C / P4-D / P4-F1 相邻 targeted regression 通过。
5. P4-F2 后端只读透传仍未开始。
6. AI Project Director 总闭环仍为 Partial。

本轮明确不做：

| 项目 | 状态 |
|------|------|
| Python 业务代码修补 | 未做 |
| Worker 接入 | 未做 |
| API schema 接入 | 未做 |
| 前端确认入口 | 未做 |
| 数据库 / migration | 未做 |
| AgentMessage 写入 | 未做 |
| approval API | 未做 |
| 产品运行时 Git 写操作 | 未做 |
| PR / merge / CI 触发能力 | 未做 |

---

## 1. 远端提交确认

只读核验命令：

```bash
git ls-remote origin refs/heads/main
git rev-parse origin/main
git show --name-only --format='%H%n%s' origin/main --
```

核验结果：

| 项目 | 结果 |
|------|------|
| `origin/main` hash | `07a32a3ec32819b6fdccba61c844c76d0f1abe07` |
| commit message | `Implement P4-F1 human approval gate domain model` |
| commit 文件 1 | `runtime/orchestrator/app/domain/human_approval_gate.py` |
| commit 文件 2 | `runtime/orchestrator/tests/test_human_approval_gate.py` |

结论：GitHub `origin/main` 已包含 P4-F1 纯域模型与 targeted tests。

---

## 2. 主产品基线映射

主产品基线文件：

```text
docs/product/ai-project-director/page-information-architecture-20260518.md
```

相关产品定位：

| 基线机制 | P4-F1 映射 |
|----------|------------|
| 成果中心承接交付物与审批 | P4-F1 只产生 human approval evidence，不直接管理成果库 |
| 审批页是用户对 AI 产出进行人工 Gate 决策的地方 | `HumanApprovalRecord` 表达一次显式用户确认事实 |
| 所有高风险放行动作必须说明后果并保留证据 | `DeliveryHumanApprovalResult` 输出 `reason_code`、`summary_cn`、`blocking_reasons`、`approval_confirmation_fingerprint` |
| 页面分工清楚，不让运行页/仓库页承担审批决策 | P4-F1 未接 Worker、API、前端；后续 P4-F2/P4-F3 仍需单独设计和实现 |

P4-F1 与产品基线一致：它只建立人工确认 Gate 的域层证据，不把确认等同于代码已写入仓库。

---

## 3. P4-F1 实现复核

### 3.1 文件清单

| 文件 | 用途 | 状态 |
|------|------|------|
| `runtime/orchestrator/app/domain/human_approval_gate.py` | P4-F1 纯域模型与 builder | Pass |
| `runtime/orchestrator/tests/test_human_approval_gate.py` | P4-F1 targeted tests | Pass |

### 3.2 纯域模型边界

`human_approval_gate.py` 文件头明确声明：

- 不运行 Git 命令。
- 不调用 TaskWorker。
- 不写 AgentMessage rows。
- 不暴露 API schemas。
- 不修改数据库表。
- 不查询 repository。
- 不执行 `git add` / `git commit` / `git push` / PR。
- 只把已有 P4-C/P4-D evidence 与显式用户确认事实评估为 human approval gate evidence。

复核结果：代码引用范围只出现在 domain 文件和对应 test 文件内，未接入以下路径：

| 路径/层级 | 复核结果 |
|-----------|----------|
| `runtime/orchestrator/app/api` | 未引用 P4-F1 |
| `runtime/orchestrator/app/workers` | 未引用 P4-F1 |
| `runtime/orchestrator/app/services` | 未引用 P4-F1 |
| `runtime/orchestrator/app/repositories` | 未引用 P4-F1 |
| `apps/` | 未引用 P4-F1 |

结论：P4-F1 当前是纯 domain + test，没有产品运行时接入。

### 3.3 核心模型

| 模型 | 责任 | 复核结论 |
|------|------|----------|
| `HumanApprovalGateScope` | 固定确认范围枚举，仅允许 `git_add_commit_preview` | Pass |
| `HumanApprovalGateAction` | 固定确认动作枚举，仅允许 `approve_git_add_commit_preview` | Pass |
| `HumanApprovalGateSafetyFlags` | P4-F 安全标志，不允许写 Git 或允许写仓库 | Pass |
| `HumanApprovalRecord` | 可审计用户确认记录，含 actor、scope、request id、时间、过期、fingerprint、applied/revoked | Pass |
| `DeliveryHumanApprovalResult` | P4-F gate 评估结果，包含 ready/reason/blocking/evidence 对齐字段 | Pass |
| `HumanApprovalGateBuilder.evaluate()` | 从 P4-C/P4-D evidence + 显式用户确认事实评估 P4-F evidence | Pass |

### 3.4 Safety Flags 复核

P4-F1 强制拒绝以下 forbidden flags 为 True：

```text
runs_git
runs_write_git
git_add_triggered
git_commit_triggered
git_push_triggered
pr_opened
ci_triggered
execution_enabled
operation_applied
gate_allows_write
```

P4-F1 ready 时允许：

| flag | ready=True 值 | 含义 |
|------|---------------|------|
| `approval_granted` | `True` | 仅表示用户已确认提交预览 |
| `gate_allows_next_guardrail` | `True` | 仅允许进入下一阶段写入前 guardrail |
| `gate_allows_write` | `False` | 不授权写仓库 |
| `runs_write_git` | `False` | 不执行写 Git |
| `git_add_triggered` | `False` | 不执行 `git add` |
| `git_commit_triggered` | `False` | 不执行 `git commit` |
| `git_push_triggered` | `False` | 不执行 `git push` |
| `pr_opened` | `False` | 不创建 PR |

结论：P4-F1 将“用户确认”与“写仓库授权”明确分离。

---

## 4. Targeted Tests 证据

### 4.1 P4-F1 单阶段测试

命令：

```bash
cd runtime/orchestrator
python -m pytest tests/test_human_approval_gate.py -q
```

结果：

```text
30 passed in 0.08s
```

覆盖范围：

| 覆盖项 | 状态 |
|--------|------|
| ready=True 输出 `HumanApprovalRecord` | Pass |
| `approval_id` 缺失时生成稳定 ID | Pass |
| gate evidence missing | Pass |
| gate not ready | Pass |
| operation preview missing / not ready | Pass |
| unsupported approval action | Pass |
| actor missing | Pass |
| approval scope missing / unsupported / mismatch | Pass |
| request id missing | Pass |
| timestamp / expiry missing | Pass |
| expired approval | Pass |
| approval already applied | Pass |
| approval revoked | Pass |
| confirmation missing | Pass |
| changed files mismatch | Pass |
| commit message mismatch | Pass |
| write already triggered | Pass |
| forbidden safety flags 强制校验 | Pass |
| ready contract inconsistent rejected | Pass |
| 与 P4-D safety flag 分离 | Pass |

### 4.2 P4-C / P4-D / P4-F1 相邻 targeted regression

命令：

```bash
cd runtime/orchestrator
python -m pytest tests/test_human_approval_gate.py tests/test_git_operation_dry_run.py tests/test_delivery_gate_evidence.py -q
```

结果：

```text
49 passed in 0.09s
```

结论：P4-F1 未破坏现有 P4-C operation dry-run 与 P4-D delivery gate evidence 纯域证据链。

---

## 5. P4-F1 Gate 结论

| Gate | 结论 | 证据 |
|------|------|------|
| `origin/main` 包含 P4-F1 两个文件 | Pass | commit `07a32a3ec32819b6fdccba61c844c76d0f1abe07` |
| P4-F1 纯域模型存在 | Pass | `human_approval_gate.py` |
| P4-F1 targeted tests 存在 | Pass | `test_human_approval_gate.py` |
| ready=True 可形成审计型 `HumanApprovalRecord` | Pass | `test_evaluate_ready_human_approval_gate_outputs_auditable_record` |
| ready=True 不表示写仓库 | Pass | `gate_allows_write=False`，写 Git flags 全 False |
| P4-F1 阻断 reason 覆盖 | Pass | `test_evaluate_blocked_reason_code_coverage` |
| safety flags 强制拒绝写操作 | Pass | `test_human_approval_gate_safety_flags_reject_forbidden_true_flags` |
| P4-F1 未接 Worker | Pass | app/workers 无引用 |
| P4-F1 未接 API | Pass | app/api 无引用 |
| P4-F1 未接前端 | Pass | apps 无引用 |
| P4-F1 未写 AgentMessage | Pass | 无 service / repository 接入 |
| P4-F1 未实现产品运行时 Git 写操作 | Pass | 仅 domain/test，无 runtime write path |
| **P4-F1 Closure** | **Pass** | targeted tests 通过 |

---

## 6. P4-F2 状态

P4-F2 定义为“后端只读透传”，包括但不限于：

- TaskWorker 成功路径基于用户确认记录生成 `delivery_human_approval_*` 或 `human_approval_gate_*` 字段。
- WorkerRunResult / WorkerRunOnceResponse 透传。
- blocked / failed path 保持 None。

当前复核结果：

| 能力 | 状态 |
|------|------|
| WorkerRunResult 新增 P4-F 字段 | Not started |
| WorkerRunOnceResponse 新增 P4-F 字段 | Not started |
| TaskWorker 调用 `HumanApprovalGateBuilder` | Not started |
| P4-F evidence API 透传 | Not started |
| P4-F blocked / failed path 集成测试 | Not started |

结论：**P4-F2 仍为 Not started**。

---

## 7. 后续仍 Not started 清单

| # | 能力 | 状态 |
|---|------|------|
| 1 | P4-F2 Worker / API 只读透传 | Not started |
| 2 | P4-F3 前端确认入口 | Not started |
| 3 | approval evidence API | Not started |
| 4 | AgentMessage approval event 写入 | Not started |
| 5 | 产品运行时 `git add` | Not started |
| 6 | 产品运行时 `git commit` | Not started |
| 7 | 产品运行时 `git push` | Not started |
| 8 | PR 创建 | Not started |
| 9 | CI / review / merge | Not started |
| 10 | AI Project Director 总闭环 Pass | Not started |

---

## 8. AI Project Director 总闭环结论

P4-F1 已完成 Human Approval Gate 的纯域模型与测试，但 AI Project Director 总闭环仍未完成，因为：

1. P4-F2 后端只读透传未开始。
2. P4-F3 前端确认入口未开始。
3. approval API 未开始。
4. 真实 Git 写入前 guardrail / feature flag 阶段未开始。
5. 产品运行时 `git add` / `git commit` / `git push` / PR 均未实现。

因此：

| 项目 | 结论 |
|------|------|
| P4-F1 | Pass |
| P4-F2 | Not started |
| AI Project Director 总闭环 | Partial |

---

## 9. 本轮收口声明

本轮只做文档与证据收口。

| 声明 | 结论 |
|------|------|
| 是否修改 Python 业务代码 | 否 |
| 是否修改测试代码 | 否 |
| 是否修改 API | 否 |
| 是否修改 Worker | 否 |
| 是否修改前端 | 否 |
| 是否修改数据库 / migration | 否 |
| 是否写 AgentMessage | 否 |
| 是否新增 approval API | 否 |
| 是否新增确认按钮 | 否 |
| 是否实现产品运行时 Git 写操作 | 否 |
| 是否只新增 closure 文档 | 是 |

开发流程中的文档提交不代表 AI-Dev-Orchestrator 产品运行时具备 Git 写操作能力。

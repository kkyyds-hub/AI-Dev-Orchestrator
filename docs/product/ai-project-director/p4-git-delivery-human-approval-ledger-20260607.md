# P4 Git Delivery + Human Approval Ledger

> **文档类型**: P4 阶段总账
> **生成日期**: 2026-06-07
> **远端基准**: `origin/main` = `1119a59c37842f32159111619824888ac1db2e88`
> **路线文档**: `docs/product/ai-project-director/p1-p7参考规划复用说明书.md`
> **主产品基线**: `docs/product/ai-project-director/page-information-architecture-20260518.md`
> **状态**: P4: Pass；P5: Not started；AI Project Director 总闭环: Partial

---

## 1. 文档目的

本文档是 P4 阶段（Git Delivery Preview + Human Approval Gate）的唯一总账。

### 1.1 治理规则

为遏制 P4 阶段的文档膨胀，从本文档生效起执行以下规则：

| 场景 | 文档策略 |
|------|---------|
| 总路线 / 产品基线 / 阶段重排 | 可新建文档 |
| 高风险新设计（需对齐多个模块） | 可新建设计文档 |
| 普通实现（Bug fix / feature / 小功能） | **不新建 closure 文档** |
| 小修正 / R1 / R2 / R3 | **不新建文档，只追加到本 ledger** |
| 阶段内证据记录 | **统一追加到本 ledger** |
| 大阶段完成 | **只写一份总 closure** |
| 后续给 Codex / DeepSeek 的任务指令 | **必须遵守本规则，不得要求新建零散 closure 文档** |

### 1.2 已有文档保留

P4-F1 到 P4-F3 之间已创建的 design / closure 文档全部保留，不删除。但 P4-F3 之后的普通实现不再新增独立 closure 文档，统一记录在本 ledger。

---

## 2. P4 当前总体状态

| 子阶段 | 内容 | Gate | 关键 commit |
|--------|------|------|------------|
| P4-B | Git Diff Dry-run evidence | Pass | — |
| P4-C | Git Operation Dry-run Preview | Pass | — |
| P4-D | Delivery Gate Evidence | Pass | — |
| P4-E2 | 前端只读展示 | Pass | — |
| P4-F1 | Human Approval Gate 纯域模型 | Pass | `07a32a3` |
| P4-F2-A | WorkerRunResult / WorkerRunOnceResponse 只读透传骨架 | Pass | `814beea` (R1 fix) |
| P4-F2-B | Human Approval API 设计 | Pass | `bbbec99` |
| P4-F2-C0 | Evidence Snapshot Source | Pass | `a0b8ffb` (fix) |
| P4-F2-C | Approval API (`POST /approvals/delivery-human-approval`) | Pass | `4dabb0c` (actor seam) |
| P4-F2-D | Approval Audit / AgentMessage 写入 | Pass | `f01bec6` (semantics fix) |
| P4-F3 | Frontend Confirmation Entry | **Pass** | `cc207cf` |
| P4-F4 | Human Approval E2E Closure / Minimal Verification | **Pass** | 本轮 ledger commit |
| **P4 Final Gate Closure via Ledger** | 阶段总收口 | **Pass** | 本轮 ledger commit |
| P5 | Failure Recovery | **Not started** | — |
| 产品运行时 git add / commit / push / PR | — | **Not started** | — |
| **AI Project Director 总闭环** | — | **Partial** | — |

---

## 3. P4-F3 Frontend Confirmation Entry 记录

### 3.1 提交

| 项目 | 值 |
|------|-----|
| commit hash | `cc207cf4b48d419e4db1d5db822d237b66fa5da9` |
| commit message | `feat: add P4-F3 delivery confirmation entry` |
| 修改文件 | `WorkerDeliveryGateEvidenceCard.tsx`、`WorkerHumanApprovalConfirmDialog.tsx`、`api.ts`、`types.ts` |

### 3.2 实现摘要

| # | 实现项 | 文件 |
|---|--------|------|
| 1 | 在 `WorkerDeliveryGateEvidenceCard` 内新增确认入口区域（"用户确认入口"卡片 + 按钮） | `WorkerDeliveryGateEvidenceCard.tsx` |
| 2 | 确认入口位于"操作安全标记"区域下方 | 同上 |
| 3 | 新增 `WorkerHumanApprovalConfirmDialog` 确认弹窗组件 | `WorkerHumanApprovalConfirmDialog.tsx` |
| 4 | 弹窗展示提交预览内容（提交说明、文件列表、预览动作、工作区、分支、证据来源） | 同上 |
| 5 | 弹窗要求用户勾选确认声明复选框："我确认提交预览内容，可进入下一阶段安全检查。" | 同上 |
| 6 | 新增 `DeliveryHumanApprovalRequest` / `DeliveryHumanApprovalResponse` 前端类型 | `types.ts` |
| 7 | 新增 `evaluateDeliveryHumanApproval()` API client + `DeliveryHumanApprovalHttpError` 错误类 | `api.ts` |
| 8 | 新增 `DeliveryHumanApprovalRecordedCard` 组件展示已有确认状态 | `WorkerDeliveryGateEvidenceCard.tsx` |
| 9 | 新增 14 个 `HUMAN_APPROVAL_REASON_LABELS` 中文映射 | 同上 |

### 3.3 安全设计确认

| 检查项 | 状态 |
|--------|------|
| Request body 不传 `approval_actor_id` | ✅ `DeliveryHumanApprovalRequest` 类型中无此字段 |
| Request body 不传 `approval_actor_display_name` | ✅ 同上 |
| 不传 Git credential | ✅ 无此类字段 |
| 不传完整 diff | ✅ 只传 `expected_changed_files` 文件名列表 |
| `confirmation_text` 不写 localStorage / sessionStorage / URL / console | ✅ 前端常量 `DELIVERY_HUMAN_APPROVAL_CONFIRMATION_TEXT` 仅作为 API request body 一次性传递 |

---

## 4. P4-F3 UI 最低可用性记录

### 4.1 可用性检查清单

| 检查项 | 结果 |
|--------|------|
| 按钮在卡片文档流内，不使用危险绝对定位 | ✅ 按钮在 `DeliveryGateEvidenceCard` 内部正常流中 |
| 按钮文案 | ✅ "确认进入下一阶段安全检查" |
| 按钮旁说明 | ✅ "这只是确认进入下一阶段，尚未执行提交或推送。" |
| 弹窗使用 `max-h-[90vh]` + `overflow-auto` 约束 | ✅ 不撑出视口 |
| `changedFiles` 列表有 `max-h-40` + `overflow-auto` 内部滚动 | ✅ |
| 能看到 | ✅ |
| 能点到 | ✅ |
| 能读懂 | ✅ 中文文案 + 文件列表 + 明确说明 |
| 能返回结果 | ✅ ready=True / ready=False / HTTP error 三种路径 |
| 不误导用户 | ✅ "尚未执行提交或推送"多处展示 |

### 4.2 当前不追求

- 最终视觉美化
- 动画 / 过渡效果
- 响应式精确适配（移动端可用但不优化）

---

## 5. P4-F3 显示条件

确认入口只有在以下条件**全部满足**时才渲染：

| # | 条件 | 代码证据 |
|---|------|---------|
| 1 | `run_id` 存在 | `!props.run_id` → return null |
| 2 | `git_operation_dry_run_ready === true` | `buildConfirmationPreview()` 检查 |
| 3 | `delivery_gate_evidence_ready === true` | 同上 |
| 4 | `delivery_gate_evidence_gate_allows_user_confirmation === true` | 同上 |
| 5 | `delivery_gate_evidence_gate_allows_write === false` | 同上 |
| 6 | `proposed_operation === "git_add_commit"` | 同上 |
| 7 | `changedFilesCount > 0` + `changedFiles.length > 0` | 同上 |
| 8 | `proposedCommitMessage.trim().length > 0` | 同上 |
| 9 | 当前没有 ready=True 的本地 `approvalResult` | `approvalResult === null` |

---

## 6. P4-F3 Response 处理

### 6.1 ready=True

| UI 行为 | 实现 |
|---------|------|
| 关闭弹窗 | `setConfirmDialogOpen(false)` |
| 保存 `approvalResult` | `setApprovalResult(result)` |
| 展示确认状态卡片 | `<DeliveryHumanApprovalRecordedCard approval={approvalResult} />` |
| 展示 `approval_id` / `approved_by_display_name` / `approval_created_at` / `approval_expires_at` | 卡片内 4 个 `GateInfo` |
| 展示"尚未执行提交或推送" | 卡片内 `"尚未执行提交或推送。"` |

### 6.2 ready=False

| UI 行为 | 实现 |
|---------|------|
| 弹窗保持打开 | 不关闭 |
| 展示原因 | `setConfirmationError(buildReadyFalseMessage(result))` |
| `reason_code` 中文映射 | `HUMAN_APPROVAL_REASON_LABELS` (14 个) + `blocking_reasons` |

### 6.3 HTTP 409 / 404

| 场景 | 实现 |
|------|------|
| 409 (snapshot 缺失/无效) | `"交付前证据缺失或已失效，请重新运行交付前检查。"` |
| 404 (run 不存在) | `"运行记录不存在，请确认当前运行是否有效。"` |
| 其他 HTTP 错误 | `DeliveryHumanApprovalHttpError` 的 `message` |

---

## 7. 禁止文案记录

P4-F3 实现中进行了静态检查，以下文案**未出现**在代码中：

```text
审批已通过
已完成审批
已授权写入
可以提交代码
代码已提交
代码已推送
提交成功
推送成功
PR 已创建
合并请求已创建
自动提交成功
可合并
交付完成
AI 已完成交付
已执行提交
```

实际使用的安全文案：

| 位置 | 文案 |
|------|------|
| 按钮 | 确认进入下一阶段安全检查 |
| 按钮说明 | 这只是确认进入下一阶段，尚未执行提交或推送。 |
| 弹窗标题 | 确认提交预览 |
| 弹窗说明 | 确认后不会立即提交代码。系统只会记录你的确认，并进入下一阶段写入前安全检查。当前不会执行 git add、git commit、git push 或创建 PR。 |
| 确认声明 | 我确认提交预览内容，可进入下一阶段安全检查。 |
| 成功卡片 | 用户确认记录已生成，可进入下一阶段写入前安全检查。当前仍未执行提交或推送。 |
| 成功卡片副文 | 尚未执行提交或推送。 |
| ready=False 主文 | 当前不满足用户确认条件。 |

---

## 8. 验证记录

| 检查项 | 命令 | 结果 |
|--------|------|------|
| 前端 build | `cd apps/web && npm run build` | **passed** |
| git diff --check | `git diff --check` | **passed** |
| Vite chunk size warning | — | 非阻断 |

---

## 9. 已知限制

| # | 限制 | 说明 |
|---|------|------|
| 1 | 确认状态保存在前端本地 `approvalResult` state | 刷新页面后确认状态丢失；是否能从 AgentMessage 恢复确认状态，仍待后续 UAT 数据集或独立回读阶段验证 |
| 2 | 真实链路不易手动走到 P4-F3 入口 | 需要完整 Worker 运行成功 + P4-C/P4-D evidence 全部生成 + delivery gate 通过；当前缺少一键测试数据 |
| 3 | 确认入口随 `WorkerDeliveryGateEvidenceCard` 复用 | `ManualRunResultSection` 与 `WorkerPoolResultSection` 均复用该组件；本轮未新增独立页面 |
| 4 | 未做前端 UAT Seed Dataset | 后续 P7 或 P7 后应做 Frontend UAT Seed Dataset，让每个页面、每个状态都有可验收测试数据 |

---

## 10. 后续执行顺序

```text
1. P5 Failure Recovery
2. P6 Agent Orchestration
3. P7 Project Director Conversation Hub + Governance
4. P7 后统一 Frontend UAT Seed Dataset + 页面体验优化
```

---

## 11. Gate 结论

| Gate | 结论 | 证据 |
|------|------|------|
| `origin/main` HEAD 确认 | Pass | `1119a59c37842f32159111619824888ac1db2e88` |
| P4 Ledger 创建 | Pass | 本文档 |
| P4-F3 Frontend Confirmation Entry | Pass | commit `cc207cf` + build passed |
| P4-F4 Human Approval E2E Closure / Minimal Verification | Pass | 本 ledger 第 13 节 |
| P4 Final Gate Closure via Ledger | Pass | 本 ledger 第 14 节 |
| 产品运行时 git add / commit / push / PR | Not started | — |
| **AI Project Director 总闭环** | **Partial** | P7 完成前不得写 Pass |

---

## 12. 本轮收口声明

| 声明 | 结论 |
|------|------|
| 是否修改前端代码 | 否 |
| 是否修改后端代码 | 否 |
| 是否修改测试代码 | 否 |
| 是否修改数据库 / migration | 否 |
| 是否写 AgentMessage | 否 |
| 是否新增 P4-F3 closure 文档 | 否（统一记录在本 ledger） |
| 是否只新增/更新 P4 ledger | 是 |
| 是否实现产品运行时 Git 写操作 | 否 |

---

## 13. P4-F4 Human Approval E2E Closure / Minimal Verification 记录

### 13.1 范围

| 项目 | 结论 |
|------|------|
| 后端最小 E2E targeted test | 已补强 |
| 前端必要小修 | 已完成：确认声明改为后端可识别的显式确认语义 |
| P4 ledger | 已追加 |
| 新增 P4-F4 closure 文档 | 否 |
| DB / migration / Worker / P4-C / P4-D builder | 未修改 |
| 产品运行时 Git 写操作 | 未实现、未触发 |

### 13.2 修改文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `runtime/orchestrator/tests/test_delivery_human_approval_api.py` | 后端 targeted test | 新增 `test_p4f4_minimal_e2e_records_frontend_confirmation_audit_without_git_writes` |
| `apps/web/src/features/task-actions/WorkerHumanApprovalConfirmDialog.tsx` | 前端必要小修 | 固定确认声明从“我确认当前提交预览内容...”改为“我确认提交预览内容...”，匹配后端 `_confirmation_is_explicit()` |
| `docs/product/ai-project-director/p4-git-delivery-human-approval-ledger-20260607.md` | P4 ledger | 追加本节 P4-F4 证据 |

### 13.3 最小 E2E 覆盖

新增 targeted test 覆盖以下链路：

```text
Run + AgentSession seed
  → delivery_evidence_snapshot 写入 run log
  → POST /approvals/delivery-human-approval
  → DeliveryHumanApprovalResponse ready=True
  → AgentMessage delivery_human_approval_recorded 写入
  → confirmation_text 不保存、不回显
  → Git write flags 全部 False
```

### 13.4 AgentMessage audit event 验证

| 检查项 | 结果 |
|--------|------|
| `event_type == "delivery_human_approval_recorded"` | ✅ |
| `role == SYSTEM` | ✅ |
| `message_type == TIMELINE` | ✅ |
| `content_summary` 使用确认记录语义 | ✅ |
| `content_detail.approval_client_request_id` 与请求一致 | ✅ |
| `content_detail.approval_confirmation_fingerprint` 与 response 一致 | ✅ |
| `approval_confirmation_text` 不在 `content_detail` | ✅ |

### 13.5 confirmation_text 安全

| 检查项 | 结果 |
|--------|------|
| response 不回显固定确认声明 | ✅ |
| AgentMessage `content_summary` 不包含固定确认声明 | ✅ |
| AgentMessage `content_detail` 不包含固定确认声明 | ✅ |
| `content_detail` 不包含 `approval_confirmation_text` 字段 | ✅ |

### 13.6 Git write flags

新增 P4-F4 test 同时验证 response `safety_flags` 与 AgentMessage `content_detail`：

| flag | 结果 |
|------|------|
| `runs_write_git` | `False` |
| `git_add_triggered` | `False` |
| `git_commit_triggered` | `False` |
| `git_push_triggered` | `False` |
| `pr_opened` | `False` |
| `ci_triggered` | `False` |
| `execution_enabled` | `False` |
| `operation_applied` | `False` |
| `gate_allows_write` | `False` |
| `gate_allows_next_guardrail` | `True` |

### 13.7 验证命令

| 检查项 | 命令 | 结果 |
|--------|------|------|
| 后端 P4-F4 targeted API / audit test | `runtime/orchestrator/.venv/bin/pytest runtime/orchestrator/tests/test_delivery_human_approval_api.py -q` | **10 passed** |
| 后端 human approval gate + API 回归 | `runtime/orchestrator/.venv/bin/pytest runtime/orchestrator/tests/test_human_approval_gate.py runtime/orchestrator/tests/test_delivery_human_approval_api.py -q` | **40 passed** |
| 前端 build | `cd apps/web && npm run build` | **passed** |
| Vite chunk size warning | — | 非阻断 |

### 13.8 Gate 结论

| Gate | 结论 |
|------|------|
| P4-F4 Human Approval E2E Closure / Minimal Verification | **Pass** |
| P4 总收口 | **Pass** |
| 产品运行时 git add / commit / push / PR | **Not started** |
| AI Project Director 总闭环 | **Partial** |

---

## 14. P4 Final Gate Closure via Ledger

### 14.1 范围声明

本节是 P4 阶段总收口记录。按本 ledger 的治理规则，本轮**不新增 P4 final closure 文档**，只更新 P4 ledger。

| 项目 | 结论 |
|------|------|
| 是否只更新 P4 ledger | 是 |
| 是否新增 P4 final closure 文档 | 否 |
| 是否改代码 / 测试 / 前端 / 后端 / DB / AgentMessage | 否 |
| 是否实现产品运行时 Git 写操作 | 否 |
| P4 Final Gate | Pass |
| P5 | Not started |
| AI Project Director 总闭环 | Partial |

### 14.2 P4 完成能力

P4 阶段已完成以下能力闭环：

| 能力 | 状态 | 证据 |
|------|------|------|
| Git Diff Dry-run evidence | Pass | P4-B |
| Git Operation Dry-run Preview | Pass | P4-C |
| Delivery Gate Evidence | Pass | P4-D |
| 前端只读展示 | Pass | P4-E2 |
| Human Approval Gate 纯域模型 | Pass | P4-F1 |
| WorkerRunResult / WorkerRunOnceResponse 只读透传骨架 | Pass | P4-F2-A |
| Human Approval API 设计与实现 | Pass | P4-F2-B / P4-F2-C |
| Evidence Snapshot Source | Pass | P4-F2-C0 |
| Approval Audit / AgentMessage 写入 | Pass | P4-F2-D |
| Frontend Confirmation Entry | Pass | P4-F3 |
| Human Approval minimal E2E verification | Pass | P4-F4 |

P4 的完成语义是：

```text
系统可以展示 Git 交付预览、交付前检查证据和用户确认入口；
用户确认后，系统会记录确认事实与 AgentMessage audit event；
该确认只允许进入下一阶段写入前安全检查；
当前仍不会执行 git add、git commit、git push 或创建 PR。
```

### 14.3 P4 明确未完成 / 明确不做

| 项目 | 状态 | 说明 |
|------|------|------|
| 产品运行时 git add | Not started | P4 只做预览、确认和审计 |
| 产品运行时 git commit | Not started | 不在 P4 范围 |
| 产品运行时 git push | Not started | 不在 P4 范围 |
| 产品运行时 PR / merge | Not started | 不在 P4 范围 |
| repository reset / checkout / switch / stash / rebase / tag | Not started | 不在 P4 范围 |
| P5 Failure Recovery | Not started | 下一阶段 |
| P6 Agent Orchestration | Not started | 后续阶段 |
| P7 Project Director Conversation Hub + Governance | Not started | 后续阶段 |
| AI Project Director 总闭环 | Partial | P7 完成前不得写 Pass |

### 14.4 测试证据

P4 Final Gate 复用 P4-F4 的最小 E2E 与回归证据：

| 检查项 | 命令 | 结果 |
|--------|------|------|
| 后端 P4-F4 targeted API / audit test | `runtime/orchestrator/.venv/bin/pytest runtime/orchestrator/tests/test_delivery_human_approval_api.py -q` | **10 passed** |
| 后端 human approval gate + API 回归 | `runtime/orchestrator/.venv/bin/pytest runtime/orchestrator/tests/test_human_approval_gate.py runtime/orchestrator/tests/test_delivery_human_approval_api.py -q` | **40 passed** |
| 前端 build | `cd apps/web && npm run build` | **passed** |
| git diff --check | `git diff --check` | **passed** |

### 14.5 安全边界

| 边界 | 结论 |
|------|------|
| `confirmation_text` | 不保存、不回显；只保存 fingerprint |
| AgentMessage audit event | 记录确认事实，不表达审批通过、授权写入或交付完成 |
| Git write flags | `runs_write_git` / `git_add_triggered` / `git_commit_triggered` / `git_push_triggered` / `pr_opened` / `operation_applied` 均保持 False |
| 前端确认入口 | 只调用 `POST /approvals/delivery-human-approval`，不传 actor，不传 Git credential，不传完整 diff |
| 产品运行时 Git 写操作 | 未实现、未触发 |

### 14.6 已知限制

| 限制 | 说明 |
|------|------|
| 前端确认状态仍主要依赖本地 `approvalResult` state | 刷新后是否从 AgentMessage 恢复确认状态，留到后续 UAT 数据集或独立回读阶段 |
| 缺少一键 UAT Seed Dataset | 真实 UI 人工验收仍需要稳定样例数据 |
| P4 不包含真实写入 | 真实 Git 写入如未来需要，必须在后续阶段另行设计并保持独立 guardrail |

### 14.7 下一阶段

P4 Final Gate 通过后，下一阶段进入：

```text
P5 Failure Recovery
```

P5 当前状态：**Not started**。

### 14.8 Final Gate 结论

| Gate | 结论 |
|------|------|
| P4 Final Gate Closure via Ledger | **Pass** |
| P5 | **Not started** |
| AI Project Director 总闭环 | **Partial** |

---

## 附录 A：P4 已有文档索引

以下文档已创建并保留，不删除：

| 文档 | 路径 | 类型 |
|------|------|------|
| P4-E2 + P4-F Design | `coding-session-git-delivery-lifecycle-p4e2-closure-and-p4f-human-approval-gate-design-20260606.md` | Design |
| P4-F1 Closure | `coding-session-git-delivery-lifecycle-p4f1-closure-20260606.md` | Closure |
| P4-F2-A Closure | `coding-session-git-delivery-lifecycle-p4f2a-closure-20260606.md` | Closure |
| P4-F2-B Design | `coding-session-git-delivery-lifecycle-p4f2b-human-approval-api-design-20260606.md` | Design |
| P4-F2-C0 Closure | `coding-session-git-delivery-lifecycle-p4f2c0-closure-20260607.md` | Closure |
| P4-F2-C Closure | `coding-session-git-delivery-lifecycle-p4f2c-closure-20260607.md` | Closure |
| P4-F2-D Design | `coding-session-git-delivery-lifecycle-p4f2d-approval-audit-agentmessage-design-20260607.md` | Design |
| P4-F2-D Closure | `coding-session-git-delivery-lifecycle-p4f2d-closure-20260607.md` | Closure |
| P4-F3 Design | `coding-session-git-delivery-lifecycle-p4f3-frontend-confirmation-entry-design-20260607.md` | Design |
| **P4 Ledger** | **`p4-git-delivery-human-approval-ledger-20260607.md`** | **Ledger（本文档）** |

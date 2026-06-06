# Coding Session Git Delivery Lifecycle P4-B3 收口 + P4-E 前端只读展示设计

> **文档类型**: P4-B3 阶段收口审计 + P4-E 前端只读展示设计
> **生成日期**: 2026-06-06
> **基准 commit**: `aa86ec740ff90297a25e626a0329b32cede189f5`
> **参考项目**: ComposioHQ Agent Orchestrator (`c3eeecb`)
> **前置文档**:
> - `.kkr/skills/ai-project-director-command-governance/SKILL.md`
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4a-design-20260606.md`
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4b2-closure-and-p4b3-event-audit-design-20260606.md`
> **边界**: 收口审计 + 前端设计，不改业务代码、不改前端组件、不实现 git add/commit/push/PR
> **状态**: P4-B3 Closure: Pass；P4-E Design: Design only；AI Project Director 总闭环 Partial

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator 后端

| 文件 | 用途 |
|------|------|
| `runtime/orchestrator/app/domain/delivery_event.py` | P4-B3 DeliveryEventSchema + DeliveryEventBuilder — 3 种事件 + SafetyFlags 强制校验 |
| `runtime/orchestrator/app/services/delivery_event_audit_service.py` | P4-B3 DeliveryEventAuditService — AgentMessage 写入 |
| `runtime/orchestrator/app/services/git_diff_dry_run_runner.py` | P4-B1 GitDiffDryRunRunner — 只读 diff/status 采集 |
| `runtime/orchestrator/app/workers/task_worker.py` | WorkerRunResult P4-B2 evidence + P4-B3 审计调用 |
| `runtime/orchestrator/app/api/routes/workers.py` | WorkerRunOnceResponse P4-B2 evidence 透传 |
| `runtime/orchestrator/tests/test_delivery_event_builder.py` | P4-B3 builder tests |
| `runtime/orchestrator/tests/test_delivery_event_audit_service.py` | P4-B3 audit service SQLite tests |
| `runtime/orchestrator/tests/test_worker_workspace_readonly_validation.py` | P2/P3 regression baseline |

### AI-Dev-Orchestrator 前端

| 文件 | 用途 |
|------|------|
| `apps/web/src/features/agents/types.ts` | AgentSessionSnapshot + AgentTimelineMessage 类型 |
| `apps/web/src/features/agents/components/AgentRuntimeGateEventPanel.tsx` | P3-D4 运行时门禁面板 — P4-E 复用模式 |
| `apps/web/src/features/agents/components/AgentThreadControlGrid.tsx` | 左侧栏组合 — P4-E 新增位置 |
| `apps/web/src/features/task-actions/types.ts` | WorkerRunOnceResponse 类型 |
| `apps/web/src/app/sections/ManualRunResultSection.tsx` | Worker 响应展示 |
| `apps/web/src/app/sections/WorkerPoolResultSection.tsx` | Worker pool 响应展示 |

### Agent Orchestrator 参考

| 文件 | 参考要点 |
|------|---------|
| `README.md` | spawn → workspace → runtime → agent → PR → cleanup |
| `packages/core/src/types.ts` | session/runtime/PR 分轴；evidence/event/snapshot 分离 |
| `packages/core/src/session-manager.ts` | recordActivityEvent() 审计；CleanupStack |
| `packages/core/src/lifecycle-state.ts` | CanonicalSessionLifecycle 三元组推导 |
| `packages/core/src/lifecycle-manager.ts` | 前端展示只表达真实状态，不提前显示未实现能力 |

---

## 1. P4-B3 真实状态收口

### 1.1 DeliveryEventBuilder — PASS

文件：`runtime/orchestrator/app/domain/delivery_event.py`

核心实现：

| 组件 | 说明 |
|------|------|
| `DeliveryEventType` | 3 个枚举值：`DIFF_DRY_RUN_COLLECTED`、`DIFF_DRY_RUN_SKIPPED`、`DIFF_DRY_RUN_FAILED` |
| `DeliveryEventState` | 5 个 delivery 状态：`NONE`、`DIFF_DIRTY`、`DIFF_CLEAN`、`DIFF_SKIPPED`、`DIFF_FAILED` |
| `DeliveryEventSafetyFlags` | 8 个安全标志 + `validate_p4b3_read_only_boundary()` 强制拒绝任何写操作标志为 True |
| `DeliveryEventSchema` | Pydantic 域模型，18 个字段 + `to_content_detail_json()` |
| `DeliveryEventBuilder.from_diff_dry_run_result()` | 从 `GitDiffDryRunResult` 映射 safety flags，不硬编码 |
| `P4B3_FORBIDDEN_TRUE_SAFETY_FLAGS` | 7 个禁止为 True 的标志：`runs_write_git`、`git_add_triggered`、`git_commit_triggered`、`git_push_triggered`、`pr_opened`、`ci_triggered`、`execution_enabled` |

safety flags 强制校验：如果任何 forbidden flag 为 True，`DeliveryEventSafetyFlags` 模型 validator 直接抛出 `ValueError`，拒绝构造事件。

### 1.2 DeliveryEventAuditService — PASS

文件：`runtime/orchestrator/app/services/delivery_event_audit_service.py`

- `record_diff_dry_run_event()` — 接收 `AgentSession` + `GitDiffDryRunResult` → 调用 `DeliveryEventBuilder` → 写入 AgentMessage
- AgentMessage 写入参数：`role=SYSTEM`、`message_type=TIMELINE`、`event_type=delivery_diff_dry_run_*`、`note_event_type=None`、`content_summary=summary_cn`（中文）、`content_detail=JSON`

### 1.3 TaskWorker AgentMessage timeline 接入 — PASS

文件：`runtime/orchestrator/app/workers/task_worker.py`

- `TaskWorker` 构造函数已注入 `DeliveryEventAuditService`
- executor 成功后 → `DeliveryEventAuditService.record_diff_dry_run_event()` 被调用
- blocked / failed path → 不写 delivery event（设计决定）
- `GitDiffDryRunResult.safety_flags` 直接映射到事件 safety_flags，不硬编码

### 1.4 P4-B3-R1 SafetyFlags 强制校验 — PASS

- `DeliveryEventSafetyFlags.validate_p4b3_read_only_boundary()` 确保任何写操作标志为 True 时拒绝构造
- 7 个 forbidden flags 全部覆盖
- `runs_git` 不在 forbidden 列表中——它可以是 True（只读）或 False（skipped/pre-git failed）

### 1.5 Gate

| Gate | 结论 |
|------|------|
| P4-B3 DeliveryEventBuilder | **Pass** |
| P4-B3 DeliveryEventAuditService | **Pass** |
| P4-B3 TaskWorker AgentMessage timeline 接入 | **Pass** |
| P4-B3-R1 SafetyFlags 强制校验 | **Pass** |
| AgentMessage delivery event 写入 | **Pass**（仅限 `delivery_diff_dry_run_*` 三类） |
| git add / commit / push | **Not started** |
| PR 创建 | **Not started** |
| **AI Project Director 总闭环** | **Partial** |

---

## 2. 当前已完成 Delivery evidence 链路

从 P4-B1 到 P4-B3 的完整证据链路：

```
1. GitDiffDryRunRunner.collect()     — 只读 git diff/status 采集 (P4-B1)
    ↓
2. WorkerRunResult evidence 字段     — 28 个 git_diff_dry_run_* 字段 (P4-B2)
    ↓
3. WorkerRunOnceResponse API 透传    — 前端可读取 (P4-B2)
    ↓
4. DeliveryEventBuilder              — 规范化事件 + SafetyFlags 强制校验 (P4-B3)
    ↓
5. DeliveryEventAuditService         — 写入 AgentMessage timeline (P4-B3)
    ↓
6. AgentMessage 持久化               — 永久审计记录 (P4-B3)
```

**关键安全边界**：
- 成功路径 → write delivery diff event
- blocked / failed path → 不写（不产生无效审计记录）
- SafetyFlags 强制拒绝任何写操作标志为 True
- `runs_git` 从 `GitDiffDryRunResult` 映射，不硬编码

---

## 3. 当前仍 Not started 清单

| # | 能力 | 说明 |
|---|------|------|
| 1 | 前端 delivery evidence 只读展示 | 无 diff evidence 面板或 timeline 面板 |
| 2 | Delivery snapshot 派生 | 无 delivery lifecycle 状态快照 |
| 3 | Delivery gate (D1–D5) | 无交付门禁链 |
| 4 | Human approval API | 无审批 API |
| 5 | git add | 未实现 |
| 6 | git commit | 未实现 |
| 7 | git push | 未实现 |
| 8 | PR 创建 | 未实现 |
| 9 | CI / review / merge | 未实现 |
| 10 | CleanupStack rollback | 未实现 |
| 11 | AI Project Director 总闭环 Pass | 仍为 Partial |

---

## 4. P4-E 前端只读展示设计

### 4.1 目标

P4-E 的目标是让用户在工作台或 Agent 线程页面**只读查看**本次 Worker 执行产生的代码改动预览。展示内容必须来自当前已完成的 evidence 链路，不能跨边界。

### 4.2 允许展示的数据来源

| 来源 | 数据 | 格式 |
|------|------|------|
| WorkerRunOnceResponse | `git_diff_dry_run_*` 19 个字段 | API JSON |
| AgentMessage timeline | `delivery_diff_dry_run_collected` | `event_type` + `content_summary` + `content_detail` JSON |
| AgentMessage timeline | `delivery_diff_dry_run_skipped` | 同上 |
| AgentMessage timeline | `delivery_diff_dry_run_failed` | 同上 |

### 4.3 建议的前端组件架构

推荐新增两个组件，复用现有模式：

#### AgentDeliveryDiffEventPanel.tsx（新组件）

- 参考：`AgentRuntimeGateEventPanel.tsx` 的筛选 + 解析 + 中文展示模式
- 位置：`apps/web/src/features/agents/components/AgentDeliveryDiffEventPanel.tsx`
- 集成：在 `AgentThreadControlGrid.tsx` 左侧栏中，`AgentRuntimeGateEventPanel` 下一个位置
- 功能：从 `timelineMessages` 中筛选 `event_type = delivery_diff_dry_run_*` 的事件，只读展示

#### WorkerGitDiffDryRunEvidenceCard.tsx（新组件）

- 参考：`WorkerRuntimeLaunchGateEvidenceCard.tsx` 的 evidence 卡片模式
- 位置：`apps/web/src/features/task-actions/WorkerGitDiffDryRunEvidenceCard.tsx`
- 集成：在 `ManualRunResultSection.tsx` 中，`WorkerRuntimeLaunchGateEvidenceCard` 下一个位置
- 功能：从 `WorkerRunOnceResponse` 中读取 `git_diff_dry_run_*` 字段，只读展示

也可选择只做其中一个，或复用现有 `AgentRuntimeGateEventPanel` 的模式扩展。

---

## 5. 前端应读取的字段清单

### 5.1 从 WorkerRunOnceResponse 读取

| 字段 | 中文标签 | 说明 |
|------|---------|------|
| `git_diff_dry_run_ready` | 代码改动预览是否就绪 | true/false → 是/否 |
| `git_diff_dry_run_source` | 检测来源 | 不直接展示英文值 |
| `git_diff_dry_run_reason_code` | 未就绪原因 | 映射中文 |
| `git_diff_dry_run_has_changes` | 是否有改动 | true/false → 是/否 |
| `git_diff_dry_run_changed_files_count` | 改动文件数量 | 数字 |
| `git_diff_dry_run_changed_files` | 改动文件列表 | 文件名列表 |
| `git_diff_dry_run_added_files` | 新增文件 | 文件名列表 |
| `git_diff_dry_run_modified_files` | 修改文件 | 文件名列表 |
| `git_diff_dry_run_deleted_files` | 删除文件 | 文件名列表 |
| `git_diff_dry_run_renamed_files` | 重命名文件 | 文件名列表 |
| `git_diff_dry_run_status_summary_cn` | 改动摘要 | 中文（可直接展示） |
| `git_diff_dry_run_runs_git` | 是否执行了只读 Git 检查 | true/false → 已执行/未执行 |
| `git_diff_dry_run_runs_write_git` | 是否执行了提交或推送 | true/false → 是/否（必须为否） |
| `git_diff_dry_run_git_add_triggered` | 是否已加入待提交区 | true/false → 是/否（必须为否） |
| `git_diff_dry_run_git_commit_triggered` | 是否已生成本地提交 | true/false → 是/否（必须为否） |
| `git_diff_dry_run_git_push_triggered` | 是否已推送到远程仓库 | true/false → 是/否（必须为否） |
| `git_diff_dry_run_pr_opened` | 是否已创建代码合并请求 | true/false → 是/否（必须为否） |
| `git_diff_dry_run_ci_triggered` | 是否已触发自动检查 | true/false → 是/否（必须为否） |
| `git_diff_dry_run_execution_enabled` | 是否已开启真实提交 | true/false → 是/否（必须为否） |

### 5.2 从 AgentMessage timeline 读取

通过 `AgentTimelineMessage.event_type` 筛选：

| event_type | 中文标签 |
|-----------|---------|
| `delivery_diff_dry_run_collected` | 代码改动预览已完成 |
| `delivery_diff_dry_run_skipped` | 代码改动预览已跳过 |
| `delivery_diff_dry_run_failed` | 代码改动预览失败 |

从 `content_detail` JSON 解析后，可展示 `summary_cn`、`changed_files_count`、`status_summary_cn` 和 safety flags。

---

## 6. 用户可见中文规范

### 6.1 核心原则

所有展示给用户看的主文案必须是简单中文。禁止直接把英文枚举作为主文案。禁止把 `true`/`false` 直接显示。

### 6.2 event_type → 中文映射

| event_type | 中文展示 |
|-----------|---------|
| `delivery_diff_dry_run_collected` | 代码改动预览已完成 |
| `delivery_diff_dry_run_skipped` | 代码改动预览已跳过 |
| `delivery_diff_dry_run_failed` | 代码改动预览失败 |

### 6.3 safety flag → 中文映射

| 字段 | true 展示 | false 展示 |
|------|---------|----------|
| `runs_git` | 已执行只读 Git 检查 | 未执行 Git 检查 |
| `runs_write_git` | — （P4-E 阶段永远为否） | 未执行提交或推送等写操作 |
| `git_add_triggered` | — （P4-E 阶段永远为否） | 未加入待提交区 |
| `git_commit_triggered` | — （P4-E 阶段永远为否） | 未生成本地提交 |
| `git_push_triggered` | — （P4-E 阶段永远为否） | 未推送到远程仓库 |
| `pr_opened` | — （P4-E 阶段永远为否） | 未创建代码合并请求 |
| `ci_triggered` | — （P4-E 阶段永远为否） | 未触发自动检查 |
| `execution_enabled` | — （P4-E 阶段永远为否） | 未开启真实提交 |

### 6.4 状态描述 → 中文

| 状态 | 中文文案 |
|------|---------|
| 改动预览有变更 | 代码改动预览已完成：检测到 X 个文件变更。注意：改动只是预览结果，尚未被提交或推送。 |
| 改动预览无变更 | 本次执行未产生代码改动。 |
| 改动预览跳过 | 代码改动预览已跳过：当前没有可检查的工作区。 |
| 改动预览失败（pre-git） | 代码改动预览失败：当前工作区不可用，未运行 Git 检查。 |
| 改动预览失败（git-command） | 代码改动预览失败：Git 只读检查未完成。 |

---

## 7. 前端禁止文案

在功能未实现前，任何页面**严禁**显示以下文案：

| 禁止文案 | 原因 |
|---------|------|
| 代码已提交 | git commit 未实现 |
| 代码已推送 | git push 未实现 |
| 合并请求已创建 | PR 未实现 |
| 自动提交成功 | git commit 不是自动的，且未实现 |
| AI 已完成交付 | Delivery Axis 未闭环 |
| 交付完成 | 同上 |
| PR 已准备 | PR 未实现 |
| 提交成功 | 无 git commit 能力 |
| 推送成功 | 无 git push 能力 |
| 可合并 | merge 未实现 |

---

## 8. 展示边界

### 8.1 前端可以说的内容

- "代码改动预览已完成"
- "检测到 X 个文件变更"
- "改动只是预览结果，尚未被提交或推送"
- "本次执行未产生代码改动"
- "代码改动预览失败"
- "代码改动预览已跳过"
- "未执行提交或推送等写操作"
- "这是只读审计事件，不表示代码已交付"

### 8.2 前端不能说的内容

- "代码已交付"
- "任务已完成交付"
- "AI 已提交代码"
- "PR 已创建"
- "可合并"
- "等待审批合并"
- "CI 检查中"

---

## 9. P4-E 不建议做的事

| # | 不建议 | 说明 |
|---|--------|------|
| 1 | 不做 "提交代码" / "推送代码" 按钮 | git add/commit/push 未实现 |
| 2 | 不做 "创建合并请求" 按钮 | PR 未实现 |
| 3 | 不做 "同意提交" / "驳回" 按钮 | human approval 未实现 |
| 4 | 不做 delivery gate 状态展示 | delivery gate 未实现 |
| 5 | 不做 CI / review / merge 展示 | CI/review/merge 未实现 |
| 6 | 不改后端 API | P4-E 只新增前端只读组件 |
| 7 | 不改数据库 | 不新增表或字段 |
| 8 | 不把总闭环写成 Pass | AI Project Director 总闭环仍为 Partial |

---

## Gate 结论

| Gate | 结论 |
|------|------|
| P4-B3 DeliveryEventBuilder | **Pass** |
| P4-B3 DeliveryEventAuditService | **Pass** |
| P4-B3 TaskWorker AgentMessage timeline 接入 | **Pass** |
| P4-B3-R1 SafetyFlags 强制校验 | **Pass** |
| AgentMessage delivery event 写入（三类） | **Pass** |
| P4-E Frontend Delivery Evidence Design | **Design only** |
| 前端 delivery evidence 展示 | **Not started** |
| git add / commit / push | **Not started** |
| PR 创建 | **Not started** |
| CI / review / merge | **Not started** |
| **AI Project Director 总闭环** | **Partial** |

P4-B3 完成了 Delivery event/audit 从 Builder 到 AuditService 到 TaskWorker AgentMessage 接入的完整闭环——3 种 diff dry-run 事件、SafetyFlags 强制校验拒绝任何写操作标志、blocked/failed path 不写无效审计记录。

P4-E 定义了前端只读展示的设计边界——两个建议组件（`AgentDeliveryDiffEventPanel` + `WorkerGitDiffDryRunEvidenceCard`）、19 个前端应读取的字段、事件类型中文化、safety flags 中文化、禁止误导文案清单。后续交给 Codex 实现时，必须严格遵守 "前端只能展示已有 evidence，不能说代码已提交/已推送/已交付"。

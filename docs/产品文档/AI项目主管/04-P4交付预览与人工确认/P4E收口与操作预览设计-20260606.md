# Coding Session Git Delivery Lifecycle P4-E 收口 + P4-C Operation Dry-run Contract 设计

> **文档类型**: P4-E 阶段收口审计 + P4-C Git Operation Dry-run Contract 设计
> **生成日期**: 2026-06-06
> **基准 commit**: `30098945360844171a621b0a1efbc67ccb0c6b40`
> **参考项目**: ComposioHQ Agent Orchestrator (`c3eeecb`)
> **前置文档**:
> - `.kkr/skills/ai-project-director-command-governance/SKILL.md`
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4a-design-20260606.md`
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4b2-closure-and-p4b3-event-audit-design-20260606.md`
> - `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4b3-closure-and-p4e-frontend-design-20260606.md`
> **边界**: P4-E 收口审计 + P4-C 纯合同设计，不改 Python 代码、不改 TypeScript 组件、不改 API schema、不改数据库 migration、不运行全量测试、不启动服务
> **状态**: P4-E Closure: Pass；P4-C Design: Design only；AI Project Director 总闭环 Partial

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator 后端

| 文件 | 用途 |
|------|------|
| `runtime/orchestrator/app/services/git_diff_dry_run_runner.py` | P4-B1 GitDiffDryRunRunner — deny-by-default 只读 diff/status runner（593 行） |
| `runtime/orchestrator/app/domain/delivery_event.py` | P4-B3 DeliveryEventSchema + DeliveryEventBuilder — 3 种事件 + SafetyFlags 强制校验（402 行） |
| `runtime/orchestrator/app/services/delivery_event_audit_service.py` | P4-B3 DeliveryEventAuditService — AgentMessage 写入（77 行） |
| `runtime/orchestrator/app/workers/task_worker.py` | WorkerRunResult P4-B2 evidence 28 字段 + P4-B3 审计调用（L215–L241） |
| `runtime/orchestrator/app/api/routes/workers.py` | WorkerRunOnceResponse P4-B2 evidence 透传 |

### AI-Dev-Orchestrator 前端

| 文件 | 用途 |
|------|------|
| `apps/web/src/features/task-actions/WorkerGitDiffDryRunEvidenceCard.tsx` | Worker 单次结果 diff evidence 只读展示卡片（423 行） |
| `apps/web/src/features/agents/components/AgentDeliveryDiffEventPanel.tsx` | Agent timeline delivery diff event 只读展示面板（390 行） |
| `apps/web/src/app/sections/ManualRunResultSection.tsx` | 手动执行结果区 — 集成 WorkerGitDiffDryRunEvidenceCard（L117） |
| `apps/web/src/app/sections/WorkerPoolResultSection.tsx` | 批量 Worker 结果区 — 集成 WorkerGitDiffDryRunEvidenceCard（L52） |
| `apps/web/src/features/agents/components/AgentThreadControlGrid.tsx` | 左侧栏组合 — 集成 AgentDeliveryDiffEventPanel |
| `apps/web/src/features/task-actions/types.ts` | WorkerRunOnceResponse 类型 — 包含 git_diff_dry_run_* 字段 |
| `apps/web/src/features/agents/types.ts` | AgentSessionSnapshot + AgentTimelineMessage 类型 |

### Agent Orchestrator 参考

| 文件 | 参考要点 |
|------|---------|
| `README.md` | spawn → workspace.create → runtime.create → agent → PR → cleanup 完整生命周期 |
| `packages/core/src/types.ts` | session/runtime/PR 分轴建模；`CanonicalPRState/Reason`；SCM 接口抽象 |
| `packages/core/src/session-manager.ts` | CleanupStack LIFO undo；recordActivityEvent() 审计模式 |
| `packages/core/src/lifecycle-state.ts` | CanonicalSessionLifecycle 三元组联合推导 |
| `packages/core/src/lifecycle-manager.ts` | 状态探测与事件分离；reaction engine |
| `packages/core/src/cleanup-stack.ts` | LIFO undo — 成功时 dismiss，失败时 runAll |
| `packages/plugins/workspace-worktree/src/index.ts` | workspacePath seam；`destroy()` 不删 branch |

---

## 1. P4-E 真实状态收口

### 1.1 WorkerGitDiffDryRunEvidenceCard — PASS

文件：`apps/web/src/features/task-actions/WorkerGitDiffDryRunEvidenceCard.tsx`（423 行）

核心实现：

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 组件存在且完整 | **Pass** | 423 行 TypeScript，包含 props 定义、状态判断、摘要展示、文件分类列表、safety flags 面板 |
| hasGitDiffDryRunEvidence 守卫 | **Pass** | L279–L293：检查 ready / has_changes / changed_files / added_files / modified_files / deleted_files / renamed_files / status_summary_cn / reason_code 任意非空才渲染 |
| 用户可见中文标题 | **Pass** | "代码改动预览"、"检测到改动"、"没有改动"、"预览未完成"、"未记录" |
| 中文摘要文案 | **Pass** | "改动只是预览结果，尚未被提交或推送"（L222、L307、L310、L313） |
| 拒绝只读免责声明 | **Pass** | L221–L223："这里只展示只读检查结果，不会加入待提交区、生成本地提交、推送远程仓库或创建代码合并请求。" |
| 安全标记面板 | **Pass** | L260–L274：8 个 safety flags 全中文标签（"只读代码检查"、"提交或推送等写操作"、"加入待提交区"、"生成本地提交"、"推送远程仓库"、"创建代码合并请求"、"触发自动检查"、"开启真实提交"） |
| safety flags false 中文展示 | **Pass** | formatForbiddenFlag 函数：false→"未执行提交或推送等写操作"等中文；true→"安全标记异常"（红色 danger tone） |
| 文件数量展示 | **Pass** | "X 个" 格式 |
| 文件分类展示 | **Pass** | 5 组：全部改动文件、新增文件、修改文件、删除文件、重命名文件 |
| reason_code 中文化 | **Pass** | REASON_LABELS 映射 8 种原因码到中文 |
| source 中文化 | **Pass** | localizeSource："智能体工作区只读检查" |
| boolean 中文化 | **Pass** | formatBoolean：true→"是"、false→"否"、null/undefined→"未记录" |
| 禁止文案未出现 | **Pass** | 全文无"代码已提交"、"代码已推送"、"合并请求已创建"、"自动提交成功"、"AI 已完成交付"、"交付完成"、"PR 已准备"、"提交成功"、"推送成功"、"可合并" |
| git add / commit / push / PR 按钮 | **Pass（Not started）** | 无任何提交/推送/PR 按钮 |

### 1.2 AgentDeliveryDiffEventPanel — PASS

文件：`apps/web/src/features/agents/components/AgentDeliveryDiffEventPanel.tsx`（390 行）

核心实现：

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 组件存在且完整 | **Pass** | 390 行 TypeScript，包含事件筛选、JSON 解析、detail 展示、safety flags 展示 |
| 无事件时 return null | **Pass** | L81–L83：`if (!deliveryDiffMessages.length) { return null; }` |
| 事件筛选精确 | **Pass** | isDeliveryDiffEvent（L233–L238）：使用 DELIVERY_DIFF_EVENT_LABELS 的三类事件精确匹配 |
| 最多展示 3 条 | **Pass** | L79：`.slice(0, 3)` |
| event_type 中文化 | **Pass** | DELIVERY_DIFF_EVENT_LABELS："代码改动预览已完成"、"代码改动预览已跳过"、"代码改动预览失败" |
| delivery state 中文化 | **Pass** | STATE_LABELS："未开始"、"检测到代码改动"、"没有代码改动"、"已跳过改动预览"、"改动预览失败" |
| reason_code 中文化 | **Pass** | REASON_LABELS 映射 8 种原因码到中文 |
| safety flags 中文化 | **Pass** | SAFETY_FLAG_LABELS + FORBIDDEN_FALSE_TEXT："未执行提交或推送等写操作"等 |
| "只读审计，未交付" Badge | **Pass** | L164：`<StatusBadge label="只读审计，未交付" tone="info" />` |
| 标题免责声明 | **Pass** | L95–L97："这里只展示审计结果，不加入待提交区、不生成本地提交、不推送远程仓库，也不创建代码合并请求。" |
| content_detail JSON 解析容错 | **Pass** | parseDeliveryDiffDetail 处理 empty/invalid/ok 三种状态 |
| 禁止文案未出现 | **Pass** | 全文无任何禁止文案 |
| git add / commit / push / PR 按钮 | **Pass（Not started）** | 无任何提交/推送/PR 按钮 |

### 1.3 ManualRunResultSection 接入 — PASS

文件：`apps/web/src/app/sections/ManualRunResultSection.tsx`

| 检查项 | 状态 | 证据 |
|--------|------|------|
| WorkerGitDiffDryRunEvidenceCard 已导入 | **Pass** | L2：`import { WorkerGitDiffDryRunEvidenceCard } from "..."` |
| 已集成到渲染树 | **Pass** | L116–L118：`{!props.isError && props.data ? (<WorkerGitDiffDryRunEvidenceCard {...props.data} />) : null}` |
| 位置正确 | **Pass** | 在 WorkerRuntimeLaunchGateEvidenceCard（L114）之后、WorkerProviderPromptTokenCard（L121）之前 |

### 1.4 WorkerPoolResultSection 接入 — PASS

文件：`apps/web/src/app/sections/WorkerPoolResultSection.tsx`

| 检查项 | 状态 | 证据 |
|--------|------|------|
| WorkerGitDiffDryRunEvidenceCard 已导入 | **Pass** | L2 |
| 已集成到每个 Worker 结果卡片内 | **Pass** | L52：`<WorkerGitDiffDryRunEvidenceCard {...result} />` |
| 位置正确 | **Pass** | 在 WorkerRuntimeLaunchGateEvidenceCard（L51）之后 |

### 1.5 P4-E Gate

| Gate | 结论 |
|------|------|
| WorkerGitDiffDryRunEvidenceCard 只读展示 | **Pass** |
| AgentDeliveryDiffEventPanel 只读展示 | **Pass** |
| 无事件 return null | **Pass** |
| ManualRunResultSection 接入 | **Pass** |
| WorkerPoolResultSection 接入 | **Pass** |
| 用户可见中文 | **Pass** |
| 禁止文案未出现 | **Pass** |
| git add / commit / push / PR 按钮 | **Not started（正确）** |
| **P4-E Closure** | **Pass** |
| **AI Project Director 总闭环** | **Partial** |

---

## 2. 当前已完成 Delivery evidence 链路

从 P4-B1 到 P4-E 的完整只读证据链路：

```
1. GitDiffDryRunRunner.collect()           — 只读 git diff/status 采集 (P4-B1)
      │   7 种 allowlisted 命令形状
      │   deny-by-default，拒绝所有 mutates_repository=True 的命令
      │   runs_git=True（只读），runs_write_git=False
      ▼
2. WorkerRunResult evidence 字段           — 28 个 git_diff_dry_run_* 字段 (P4-B2)
      │   基础状态 4 + 改动统计 7 + 摘要/预览 4 + 命令审计 4 + 安全标志 9
      ▼
3. WorkerRunOnceResponse API 透传         — 前端可读取 (P4-B2)
      │   /api/workers/run-once response DTO
      ▼
4. DeliveryEventBuilder                    — 规范化事件 + SafetyFlags 强制校验 (P4-B3)
      │   3 种事件：collected / skipped / failed
      │   7 个 forbidden=true flags 拒绝构造
      │   runs_git 从 GitDiffDryRunResult 映射，不硬编码
      ▼
5. DeliveryEventAuditService               — 写入 AgentMessage timeline (P4-B3)
      │   role=SYSTEM, message_type=TIMELINE
      │   content_summary=中文，content_detail=JSON
      ▼
6. AgentMessage 持久化                     — 永久审计记录 (P4-B3)
      │
      ▼
7. 前端 Worker evidence 只读展示           — WorkerGitDiffDryRunEvidenceCard (P4-E)
      │   ManualRunResultSection + WorkerPoolResultSection
      │   文件分类 + 中文摘要 + safety flags 面板
      ▼
8. 前端 Agent timeline delivery event 只读展示 — AgentDeliveryDiffEventPanel (P4-E)
          AgentThreadControlGrid 左侧栏
          事件筛选 + detail 解析 + "只读审计，未交付" Badge
```

**关键安全边界（全链路强制执行）**：

| 安全标志 | 全链路值 | 说明 |
|---------|---------|------|
| `runs_write_git` | **False** | 所有阶段不执行 Git 写操作 |
| `git_add_triggered` | **False** | git add 未触发 |
| `git_commit_triggered` | **False** | git commit 未触发 |
| `git_push_triggered` | **False** | git push 未触发 |
| `pr_opened` | **False** | PR 未创建 |
| `ci_triggered` | **False** | CI 未触发 |
| `execution_enabled` | **False** | 真实 Git 写入执行未开启 |

---

## 3. 当前仍 Not started 清单

| # | 能力 | 说明 |
|---|------|------|
| 1 | Git operation dry-run API / service | 无"如果未来用户确认提交，将准备执行哪些动作"的预览能力 |
| 2 | Delivery gate (D1–D5) | 无交付门禁链 |
| 3 | Human approval API | 无审批 API |
| 4 | git add | 未实现 |
| 5 | git commit | 未实现 |
| 6 | git push | 未实现 |
| 7 | PR 创建 | 未实现 |
| 8 | CI / review / merge | 未实现 |
| 9 | CleanupStack rollback | 未实现 |
| 10 | AI Project Director 总闭环 Pass | 仍为 Partial |

---

## 4. P4-C Git Operation Dry-run Contract 设计目标

### 4.1 P4-C 定位

P4-C 是 P4-E（前端只读展示收口）和 P4-D（真实 git add/commit 实现）之间的**纯合同设计阶段**。

P4-C 的目标是设计 **GitOperationDryRunResult**——一个让系统能预览"如果未来用户确认提交，将准备执行哪些动作"的 dry-run contract。P4-C 不执行任何产品运行时 Git 写操作，不实现任何 service 代码，不接前端。

### 4.2 P4-C 明确不做的事情

P4-C 严格禁止以下所有产品运行时 Git 写操作：

| # | 禁止操作 | 对应 Git 命令 | 说明 |
|---|---------|-------------|------|
| 1 | git add | `git add <paths>` | 不加入暂存区 |
| 2 | git commit | `git commit -m "..."` | 不创建本地提交 |
| 3 | git push | `git push origin <branch>` | 不推送到远程 |
| 4 | PR 创建 | `gh pr create` / GitHub API | 不创建 Pull Request |
| 5 | merge | `git merge` / `gh pr merge` | 不合并分支 |
| 6 | branch delete | `git branch -d/-D <branch>` | 不删除分支 |
| 7 | reset | `git reset [--soft/--hard]` | 不重置 HEAD |
| 8 | checkout | `git checkout <branch>` | 不切换分支 |
| 9 | switch | `git switch <branch>` | 不切换分支 |
| 10 | stash | `git stash [pop/apply]` | 不暂存/恢复工作区 |
| 11 | rebase | `git rebase` | 不变基 |
| 12 | tag | `git tag` | 不打标签 |

### 4.3 P4-C 与 P4-B 的关键区别

| 维度 | P4-B（Git Diff Dry-run） | P4-C（Git Operation Dry-run） |
|------|--------------------------|------------------------------|
| 执行了什么 | 执行了只读 git diff/status 命令 | 不执行任何 git 命令 |
| 产出了什么 | 实际 diff evidence（changed_files 等） | 提案级别的 operation plan（如果执行，会做什么） |
| 依赖什么 | worktree 路径存在 + git 可用 | AgentSession 已绑定 worktree + diff evidence ready + has_changes=true |
| 用户看到什么 | "检测到 3 个文件变更" | "已生成提交预览：如果确认，将提交 3 个文件到分支 X" |
| 安全标志 | runs_git=True（只读），runs_write_git=False | runs_git=False（不执行），runs_write_git=False |

---

## 5. P4-C Operation Dry-run 输入条件

### 5.1 必须满足的前置条件

P4-C 的 GitOperationDryRunResult 必须在以下条件**全部满足**时才能产生 `ready=True` 的结果：

| # | 条件 | 来源 | 说明 |
|---|------|------|------|
| C1 | AgentSession 已绑定 worktree | P1 | `workspace_path` 非空，`workspace_type` 为 worktree |
| C2 | Git diff dry-run evidence ready | P4-B1/B2 | `GitDiffDryRunResult.ready=True` |
| C3 | has_changes=true | P4-B1/B2 | `GitDiffDryRunResult.has_changes=True` |
| C4 | changed_files_count > 0 | P4-B1/B2 | 至少有一个文件变更 |
| C5 | runs_write_git=false | P4-B1/B2 | 确保没有写操作已发生 |
| C6 | git_add_triggered=false | P4-B1/B2 | 确保 add 未触发 |
| C7 | git_commit_triggered=false | P4-B1/B2 | 确保 commit 未触发 |
| C8 | git_push_triggered=false | P4-B1/B2 | 确保 push 未触发 |
| C9 | pr_opened=false | P4-B1/B2 | 确保 PR 未创建 |
| C10 | human approval 尚未发生 | 未来 P4-F | approval 状态为 none 或 pending |
| C11 | feature flag 未开启真实写操作 | 未来 P4-G | `delivery_git_write_enabled=false` |

### 5.2 条件不满足时的行为

当任一条件不满足时，`GitOperationDryRunResult` 应返回对应 `reason_code` 并设置 `ready=False`：

| 不满足条件 | reason_code | summary_cn |
|-----------|-------------|-----------|
| worktree 不可用 | `worktree_unavailable` | 当前工作区不可用，无法生成提交预览。 |
| diff evidence 未就绪 | `diff_evidence_not_ready` | 代码改动预览未就绪，无法生成提交预览。 |
| 无改动 | `no_changes` | 当前没有可提交的代码改动。 |
| 写操作已触发 | `write_already_triggered` | 检测到写操作已触发，无法再次生成提交预览。 |
| feature flag 未开启 | `feature_flag_disabled` | 提交功能尚未开启。 |

---

## 6. P4-C 建议 dry-run 输出字段

### 6.1 GitOperationDryRunResult 数据结构

```python
@dataclass(slots=True, frozen=True)
class GitOperationDryRunResult:
    """Preview of planned Git operations — NO git write commands are executed.

    P4-C defines this contract.  The result describes what WOULD happen if the
    user confirms, but the system does NOT perform git add, git commit, git push,
    open a PR, merge, delete a branch, or run any other mutating Git command.
    """

    # --- 基础状态 ---
    ready: bool
    source: str                     # "git_operation_dry_run"
    reason_code: str | None         # 未就绪原因码

    # --- 关联标识 ---
    session_id: str
    project_id: str
    task_id: str
    run_id: str

    # --- 工作区信息 ---
    worktree_path: str | None
    branch_name: str | None

    # --- 改动信息（来自 diff evidence）---
    changed_files_count: int
    changed_files: list[str]
    added_files: list[str]
    modified_files: list[str]
    deleted_files: list[str]
    renamed_files: list[str]

    # --- 提案操作 ---
    proposed_operation: str         # "git_add_commit" | "git_push_pr" | "none"
    proposed_steps: list[str]       # 有序步骤列表，如 ["git add <files>", "git commit -m '...'"]
    proposed_commit_message: str | None  # 建议的 commit message
    proposed_pr_title: str | None        # 建议的 PR 标题
    proposed_pr_body: str | None         # 建议的 PR 描述

    # --- 审批要求 ---
    user_confirmation_required: bool    # 是否需要用户确认（始终为 True）
    human_approval_required: bool       # 是否需要人工审批（始终为 True）
    feature_flag_required: bool         # 是否需要 feature flag 翻转（始终为 True）

    # --- 中文摘要 ---
    summary_cn: str                 # 用户可读中文摘要

    # --- 安全标志 ---
    runs_git: bool = False              # P4-C dry-run 不执行任何 git 命令
    runs_write_git: bool = False        # 必须为 False
    git_add_triggered: bool = False     # 必须为 False
    git_commit_triggered: bool = False  # 必须为 False
    git_push_triggered: bool = False    # 必须为 False
    pr_opened: bool = False             # 必须为 False
    ci_triggered: bool = False          # 必须为 False
    execution_enabled: bool = False     # 必须为 False
    operation_applied: bool = False     # 必须为 False（提案尚未应用）
    approval_granted: bool = False      # 必须为 False（审批尚未发生）
```

### 6.2 proposed_operation 枚举

| 值 | 含义 | 对应步骤 |
|----|------|---------|
| `"git_add_commit"` | 准备执行 git add + git commit | 生成本地提交 |
| `"git_push_pr"` | 准备执行 git push + PR 创建 | 推送并创建合并请求 |
| `"none"` | 无操作建议 | 没有改动或条件不满足 |

### 6.3 proposed_steps 示例

```python
# 有改动时的 proposed_steps
proposed_steps = [
    "git add src/a.py src/b.py README.md",
    "git commit -m 'feat: add new feature with documentation updates'",
]

# 无改动时的 proposed_steps
proposed_steps = []
```

---

## 7. P4-C Safety Flags 设计

### 7.1 安全标志定义

P4-C 的 safety flags 必须在语义上区分 "是否执行了只读检查" 和 "是否执行了写操作"：

| 安全标志 | P4-C 预期值 | 含义 |
|---------|-----------|------|
| `runs_git` | **False** | P4-C dry-run 本身不执行任何 Git 命令（连只读都不执行） |
| `runs_write_git` | **False** | **不执行** git add/commit/push 等写操作——安全核心 |
| `git_add_triggered` | **False** | git add 未触发 |
| `git_commit_triggered` | **False** | git commit 未触发 |
| `git_push_triggered` | **False** | git push 未触发 |
| `pr_opened` | **False** | PR 未创建 |
| `ci_triggered` | **False** | CI 未触发 |
| `execution_enabled` | **False** | 真实 Git 写入执行未开启 |
| `approval_granted` | **False** | 审批尚未授予 |
| `operation_applied` | **False** | 提案操作尚未应用到仓库 |

### 7.2 P4-C 与 P4-B safety flags 的关键区别

| 标志 | P4-B（Diff Dry-run） | P4-C（Operation Dry-run） | 原因 |
|------|---------------------|--------------------------|------|
| `runs_git` | **True**（执行了 git diff/status） | **False**（不执行任何 git 命令） | P4-C 是纯计算/提案，不调 git |
| 其他写标志 | 全部 False | 全部 False | 两个阶段都不做写操作 |

### 7.3 Safety Flags 强制校验规则

P4-C 的 `GitOperationDryRunResult` 构造时必须强制执行：

```python
P4C_FORBIDDEN_TRUE_SAFETY_FLAGS: tuple[str, ...] = (
    "runs_git",                 # P4-C 不执行任何 git 命令
    "runs_write_git",           # 不执行写操作
    "git_add_triggered",        # 不触发 add
    "git_commit_triggered",     # 不触发 commit
    "git_push_triggered",       # 不触发 push
    "pr_opened",                # 不创建 PR
    "ci_triggered",             # 不触发 CI
    "execution_enabled",        # 不开启真实执行
    "approval_granted",         # 不假设审批已通过
    "operation_applied",        # 不假设操作已应用
)
```

**关键声明**：与 P4-B 不同，P4-C 的 `runs_git` 也在 forbidden 列表中。因为 P4-C 是纯粹的提案计算——它不执行任何 Git 命令，连只读命令也不执行。它只读取已有的 P4-B diff evidence 并基于这些 evidence 构建 operation plan。

---

## 8. P4-C 用户可见中文规范

### 8.1 核心原则

所有展示给用户的主文案必须是简单中文。技术词不能直接作为主文案，只能放在括号里作为辅助说明。**严禁在功能未实现时使用误导文案**。

### 8.2 推荐文案（P4-C 允许使用）

| 场景 | 推荐中文文案 |
|------|------------|
| 操作预览已生成 | 已生成提交预览：检测到 X 个文件变更。如果确认，将把这些文件提交到分支 Y。 |
| 操作预览无改动 | 当前没有可提交的代码改动。 |
| 工作区不可用 | 当前工作区不可用，无法生成提交预览。 |
| 提交预览说明 | 这是提交前预览，尚未加入待提交区、尚未生成本地提交、尚未推送。需要用户确认后才能进入下一步。 |
| 需要用户确认 | 需要你确认后才能进入下一步。 |
| 审批尚未发生 | 提交操作尚未获得审批。 |
| feature flag 关闭 | 提交功能尚未开启，请联系管理员。 |
| 操作预览就绪状态 | 提交预览已就绪 / 提交预览未就绪 |
| 提案步骤标题 | 如果确认，将执行以下步骤： |
| 步骤 1 | 1. 加入待提交区（git add） |
| 步骤 2 | 2. 生成本地提交（git commit） |
| safety flag 面板标题 | 操作安全标记 |
| runs_git=false | 未执行 Git 命令 |
| runs_write_git=false | 未执行提交或推送等写操作 |
| git_add_triggered=false | 未加入待提交区 |
| git_commit_triggered=false | 未生成本地提交 |
| git_push_triggered=false | 未推送到远程仓库 |
| pr_opened=false | 未创建代码合并请求 |
| execution_enabled=false | 未开启真实提交 |
| approval_granted=false | 尚未获得审批 |
| operation_applied=false | 提案尚未执行 |

### 8.3 禁止文案（P4-C 及所有后续阶段严禁使用，直到对应功能实现）

| 禁止文案 | 原因 |
|---------|------|
| 代码已提交 | git commit 尚未实现 |
| 代码已推送 | git push 尚未实现 |
| 合并请求已创建 | PR 尚未实现 |
| 自动提交成功 | git commit 不是自动的，且尚未实现 |
| AI 已完成交付 | Delivery Axis 未闭环 |
| 交付完成 | 同上 |
| PR 已准备 | PR 尚未实现 |
| 提交成功 | 无 git commit 能力 |
| 推送成功 | 无 git push 能力 |
| 可合并 | merge 尚未实现 |

---

## 9. P4-C Event / Audit 设计边界

### 9.1 可以设计但不实现的 event 类型

P4-C 可以在文档中定义以下 event 类型作为未来实现参考，但**本轮不实现**：

| # | event_type | 含义 | 触发时机 | 实现阶段 |
|---|-----------|------|---------|---------|
| 1 | `delivery_git_operation_dry_run_created` | Git 操作预览已生成 | GitOperationDryRunBuilder 成功构建 ready=True 的结果 | 未来 P4-C 实现 |
| 2 | `delivery_git_operation_dry_run_blocked` | Git 操作预览已阻断 | 前置条件不满足（无改动、无 worktree 等） | 未来 P4-C 实现 |

### 9.2 禁止设计为已完成事件

以下事件在 P4-C、P4-D、P4-E 阶段**严禁**设计为已完成——它们对应真实 Git 写操作，尚未实现：

| # | event_type | 为什么禁止 |
|---|-----------|----------|
| 1 | `delivery_git_add_completed` | git add 尚未实现 |
| 2 | `delivery_git_commit_completed` | git commit 尚未实现 |
| 3 | `delivery_git_push_completed` | git push 尚未实现 |
| 4 | `delivery_pr_created` | PR 创建尚未实现 |
| 5 | `delivery_pr_merged` | merge 尚未实现 |
| 6 | `delivery_branch_deleted` | branch delete 尚未实现 |

### 9.3 Event/Audit 实现边界

P4-C 设计阶段只定义 event 类型名称和 JSON 合同形状。以下行为**不在** P4-C 范围内：

- 不实现 DeliveryEventBuilder 对 operation dry-run event 的支持
- 不实现 DeliveryEventAuditService 对 operation dry-run event 的写入
- 不修改 `P4B3_BUILDABLE_DELIVERY_EVENT_TYPES` 元组
- 不修改 `DeliveryEventType` 枚举

---

## 10. P4-C 与后续阶段关系

| 阶段 | 目标 | 依赖 P4-C 的内容 | 不依赖 P4-C 的内容 |
|------|------|-----------------|-----------------|
| **P4-C** | Git operation dry-run contract 设计（本轮） | — | — |
| **P4-D** | Delivery gate evidence | GitOperationDryRunResult 作为 gate 输入 | 不执行真实 git 写操作 |
| **P4-F** | Human approval gate | proposed_operation + proposed_steps 作为审批展示内容 | 不执行真实 git 写操作 |
| **P4-G** | git add + git commit（带 guardrail + feature flag） | proposed_commit_message + changed_files 作为执行输入 | operation dry-run 本身不执行 |
| **P4-H** | git push + PR（带 guardrail + feature flag） | proposed_pr_title + proposed_pr_body 作为执行输入 | operation dry-run 本身不执行 |

**关键原则**：P4-C 只定义"预览什么"，P4-D/P4-F 定义"门禁拦什么"，P4-G/P4-H 定义"真实执行什么"。三者不能混用——预览不是门禁，门禁不是执行。

---

## 11. 参考机制总结

从 Agent Orchestrator 参考项目中提取的机制，及其在 P4-C 设计中的应用：

| # | AO 机制 | 学习要点 | P4-C 对应设计 |
|---|---------|---------|-------------|
| 1 | session / runtime / PR 分轴建模 | `CanonicalSessionLifecycle` 三元组 — 各维度独立推导，互不污染 | P4-C 的 GitOperationDryRunResult 作为独立 contract，不修改 DeliveryAxis 状态 |
| 2 | workspace/worktree 作为隔离边界 | `workspacePath` 既是 runtime cwd 也是 delivery 操作的工作目录 | P4-C 必须验证 worktree_path 有效 |
| 3 | evidence / event / snapshot 分离 | evidence 瞬态、event 历史、snapshot 派生 — 三者不混用 | P4-C 的 operation dry-run 是 evidence 层的扩展（提案级 evidence），不是 event 层的写入 |
| 4 | operation preview 与真实执行分离 | AO 的 SCM 接口抽象 — `detectPR()` 只读，`createPR()` 写操作，分开设计 | P4-C 只做 preview，P4-G/H 才做真实执行 |
| 5 | cleanup / rollback 作为未来阶段参考 | CleanupStack LIFO undo — 失败时保留审计线索 | P4-C 不实现 rollback，但在 contract 中预留 `operation_applied=false` 标志 |
| 6 | 前端只表达真实状态 | AO dashboard 只显示已完成的 session/PR/CI 状态，不提前显示未实现能力 | P4-C 前端展示必须声明"这是预览，尚未执行" |

---

## 12. 下一步 Codex 最小实现建议

### 12.1 实现范围

下一条 Codex 指令应严格限定在以下范围：

| # | 做什么 | 说明 |
|---|--------|------|
| 1 | 新增 `GitOperationDryRunBuilder` | 位置：`runtime/orchestrator/app/domain/git_operation_dry_run.py`（新文件） |
| 2 | 实现 `build_from_diff_evidence()` | 从一个已有的 `GitDiffDryRunResult` + `AgentSession` 构建 `GitOperationDryRunResult` |
| 3 | 包含 `GitOperationDryRunSafetyFlags` 域模型 | 10 个 safety flags + validator 拒绝任何 forbidden flag 为 True |
| 4 | 窄范围单元测试 | 只测试 builder 的构造逻辑（有改动/无改动/worktree 不可用） |

### 12.2 不做什么

| # | 不做什么 | 说明 |
|---|---------|------|
| 1 | 不接前端 | 不新增组件、不修改现有组件 |
| 2 | 不执行 Git 写操作 | 不调 git add/commit/push |
| 3 | 不写 AgentMessage | 不实现 delivery_git_operation_dry_run_* event 写入 |
| 4 | 不写 approval | 不实现 human approval API |
| 5 | 不创建 PR | 不调 gh pr create 或 GitHub API |
| 6 | 不修改 DeliveryEventBuilder | 不扩展 `P4B3_BUILDABLE_DELIVERY_EVENT_TYPES` |
| 7 | 不修改 TaskWorker | 不在 `run_once()` 中调用 GitOperationDryRunBuilder |
| 8 | 不跑全量 pytest | 只跑新增的 targeted tests |
| 9 | 不跑全量 build | 不触发 `apps/web build` |

### 12.3 测试范围

```bash
# 只允许运行：
cd runtime/orchestrator
python -m pytest tests/test_git_operation_dry_run.py -v

# 禁止运行：
pytest  # 全量
cd apps/web && npm run build  # 前端 build
```

### 12.4 文件清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `runtime/orchestrator/app/domain/git_operation_dry_run.py` | 新建 | `GitOperationDryRunSafetyFlags` + `GitOperationDryRunResult` + `GitOperationDryRunBuilder` |
| `runtime/orchestrator/tests/test_git_operation_dry_run.py` | 新建 | 窄范围 targeted tests（≤10 个测试用例） |

---

## Gate 结论

| Gate | 结论 |
|------|------|
| P4-E WorkerGitDiffDryRunEvidenceCard | **Pass** |
| P4-E AgentDeliveryDiffEventPanel | **Pass** |
| P4-E 无事件 return null | **Pass** |
| P4-E ManualRunResultSection 接入 | **Pass** |
| P4-E WorkerPoolResultSection 接入 | **Pass** |
| P4-E 用户可见中文 | **Pass** |
| P4-E 禁止文案未出现 | **Pass** |
| P4-E git add / commit / push / PR | **Not started（正确）** |
| **P4-E Closure** | **Pass** |
| P4-C Git Operation Dry-run Contract 设计 | **Design only** |
| P4-C GitOperationDryRunBuilder 实现 | **Not started** |
| P4-C Git operation dry-run API | **Not started** |
| Delivery gate (D1–D5) | **Not started** |
| Human approval API | **Not started** |
| git add / commit | **Not started** |
| git push / PR 创建 | **Not started** |
| CI / review / merge | **Not started** |
| CleanupStack rollback | **Not started** |
| **AI Project Director 总闭环** | **Partial** |

P4-E 完成了前端只读展示的完整收口——两个核心组件（WorkerGitDiffDryRunEvidenceCard + AgentDeliveryDiffEventPanel）、两个接入点（ManualRunResultSection + WorkerPoolResultSection）、无事件时 return null、全中文展示、无任何禁止文案、无任何 git add/commit/push/PR 按钮。

P4-C 定义了 Git Operation Dry-run Contract——"如果未来用户确认提交，将准备执行哪些动作"的完整合同：输入条件 11 项、输出字段 34 个、safety flags 10 个（全部 False）、用户可见中文规范、event/audit 设计边界、与 P4-D/P4-F/P4-G/P4-H 的后继关系。

P4-C 明确：不执行 git add、不执行 git commit、不执行 git push、不创建 PR、不 merge、不删除 branch、不执行 reset/checkout/switch/stash/rebase/tag。AI Project Director 总闭环仍为 **Partial**——在 git add/commit/push/PR 全部实现并通过证据验证之前，不能标记为 Pass。

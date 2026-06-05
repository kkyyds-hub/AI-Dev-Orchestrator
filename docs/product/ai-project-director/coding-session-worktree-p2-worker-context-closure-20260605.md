# Coding Session + Worktree Lifecycle P2 收口：Worker Context 阶段

> **文档类型**: P2 阶段收口审计
> **生成日期**: 2026-06-05
> **基准 commit**: `6ebe05f804eceb9ae238500cbae41e677a010822`
> **参考项目**: ComposioHQ Agent Orchestrator (`c3eeecb`)
> **前置文档**:
> - `.kkr/skills/ai-project-director-command-governance/SKILL.md`
> - `docs/product/ai-project-director/coding-session-worktree-p1-lifecycle-closure-20260605.md`
> - `docs/product/ai-project-director/gap-analysis/ai-project-director-ideal-gap-after-p1-20260605.md`
> - `docs/product/ai-project-director/coding-session-lifecycle-design-20260604.md`
> - `docs/product/ai-project-director/page-information-architecture-20260518.md`
> - `docs/product/ai-project-director/closure-flow-20260518.md`
> - `docs/product/ai-project-director/closure-checklist-20260518.md`
> **边界**: 文档收口审计，不改代码，不新增功能
> **状态**: P2 Worker Context / Runtime Dry-run / Safe Command Proof: Pass；AI Project Director 总闭环 Partial

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator 后端 (4 个)

| 文件 | 用途 |
|------|------|
| `runtime/orchestrator/app/workers/task_worker.py` | `WorkerRunResult` evidence 字段 + `validate_worker_agent_workspace()` + `resolve_worker_workspace_context()` + `build_worker_runtime_launch_dry_run()` + proof blocker |
| `runtime/orchestrator/app/workers/worktree_safe_command.py` | `WorkerWorktreeSafeCommandProofRunner.run_probe()` — 唯一的 allowlisted `pwd` proof |
| `runtime/orchestrator/app/api/routes/workers.py` | `WorkerRunOnceResponse` — API 层透传全部 evidence 字段 |
| `runtime/orchestrator/tests/test_worker_workspace_readonly_validation.py` | 12 targeted tests: validation/context/dry-run/proof/executor-block/API-evidence |

### AI-Dev-Orchestrator 前端 (5 个)

| 文件 | 用途 |
|------|------|
| `apps/web/src/features/agents/types.ts` | `AgentSessionSnapshot` — workspace 字段全量类型 |
| `apps/web/src/features/agents/components/AgentCodingSessionSnapshot.tsx` | 会话运行状态只读卡片 (agent/runtime/workspace/branch/error) |
| `apps/web/src/features/agents/components/AgentSessionList.tsx` | 会话列表 (workspace_type/workspace_path/branch_name 可见) |
| `apps/web/src/features/agents/components/AgentWorkspaceLifecycleAuditPanel.tsx` | workspace lifecycle audit 事件只读面板 (create/cleanup 审计) |
| `apps/web/src/features/agents/components/AgentThreadControlGrid.tsx` | 组合 AgentCodingSessionSnapshot + AgentWorkspaceLifecycleAuditPanel |

### Agent Orchestrator 参考 (4 个)

| 文件 | 参考要点 |
|------|---------|
| `packages/core/src/types.ts` | `CanonicalSessionLifecycle` 三元组 (session/pr/runtime)；`Runtime.create()` + `isAlive()`；`Agent.getLaunchCommand()` |
| `packages/core/src/session-manager.ts` | CleanupStack LIFO undo；spawn → workspace.create → runtime.create → agent |
| `packages/core/src/lifecycle-manager.ts` | 轮询循环 + status detection + reaction engine |
| `packages/plugins/workspace-worktree/src/index.ts` | `workspacePath` 作为 runtime/command seam；`destroy()`: git worktree remove --force，不删 branch |

---

## 1. P2 Closure Verdict

| 阶段 | 结论 | 依据 |
|------|------|------|
| P2-A | **Pass** | 前端只读展示 AgentSession workspace 状态：`AgentCodingSessionSnapshot` + `AgentSessionList` 展示 `workspace_type`、`workspace_path`、`workspace_clean`、`branch_name`、`last_workspace_error`。所有组件均含免责声明：不创建/清理 worktree，不启动 AI runtime。 |
| P2-A-R1 | **Pass** | `AgentWorkspaceLifecycleAuditPanel` 从 timeline 只读筛选 `workspace_lifecycle_audit` 事件，展示 create/cleanup 审计记录（路径、分支、状态、阻止原因、`runs_git`、`runs_write_git`）。 |
| P2-B | **Pass** | `validate_worker_agent_workspace()` 在 `TaskWorker.run_once()` 中对 AgentSession workspace 进行只读 preflight：验证路径存在、绝对路径、目录类型、`workspace_clean=True`。不执行 git 命令。 |
| P2-B-R1 | **Pass** | `resolve_worker_workspace_context()` 将 validation 结果转为 `WorkerWorkspaceContextResolution` evidence：`uses_agent_workspace`、`changes_cwd=False`、`runs_git=False`、`runs_write_git=False`、`launches_runtime=False`。字段写入 `WorkerRunResult` 并透传至 `WorkerRunOnceResponse` API。 |
| P2-C | **Pass** | `build_worker_runtime_launch_dry_run()` 构建 `WorkerRuntimeLaunchDryRun`：生成 `RuntimeCreateConfig(...)` 预览字符串，`launch_cwd_preview` 指向 worktree 路径。`execution_enabled=False`、`changes_cwd=False`、`runs_git=False`、`launches_runtime=False`。未调用 `ExecutorService`、subprocess、git 或任何 AI provider。 |
| P2-D | **Pass** | `WorkerWorktreeSafeCommandProofRunner.run_probe()` 执行唯一的 allowlisted 只读 `pwd` 命令。`observed_pwd == AgentSession.workspace_path` 证明 cwd 指向 worktree。`runs_git=False`、`runs_write_git=False`、`changes_process_cwd=False`、`launches_ai_runtime=False`。proof 失败阻断 `executor_service.execute_task()` 调用。 |
| **AI Project Director Total Closure** | **Partial** | P2 全部六项 Pass，但 Runtime Axis (AI 进程启动/探活/退出检测) 未实现，Delivery Axis (git push/PR/CI/review/merge) 未实现，四轴联合推导整体状态未实现。AI runtime 未进入 worktree 执行自动编码。 |

---

## 2. P2 Scope

P2 的目标是在 P1 worktree create / cleanup 基础设施之上，完成以下工作：

1. **让 AgentSession.workspace_path 进入 Worker 准备阶段**：Worker 在执行前检查 AgentSession 的 workspace 元数据，确认 worktree 路径存在且干净。

2. **让前端只读可见 workspace 状态**：AgentSession 的 `workspace_type`、`workspace_path`、`workspace_clean`、`branch_name`、`last_workspace_error` 字段在前端 Agent 线程页面中可见，所有组件均标注只读免责声明。

3. **让 Worker 能只读解析 workspace context**：`resolve_worker_workspace_context()` 将 workspace validation 结果转为结构化 evidence 字段（source、reason_code、是否使用 agent workspace、是否改变 cwd、是否运行 git 等），写入 `WorkerRunResult`。

4. **让 runtime launch 只做 dry-run evidence**：`build_worker_runtime_launch_dry_run()` 生成 `RuntimeCreateConfig(...)` 预览字符串，证明未来的 runtime 可以绑定到 worktree 路径。不实际启动任何 runtime 进程。

5. **让 Worker 执行一个 allowlisted safe command proof，证明 cwd 指向 worktree**：`WorkerWorktreeSafeCommandProofRunner.run_probe()` 执行唯一允许的只读 `pwd` 命令，验证 `observed_pwd == AgentSession.workspace_path`，为未来 runtime launch 提供 cwd 证明。

P2 的核心语义是 **"证明可以，但不执行"**——证明 Worker 能找到 worktree、runtime 配置能指向 worktree、在 worktree 内执行命令的路径是正确的，但所有通道 (`execution_enabled`、`launches_runtime`、`runs_git`、`runs_write_git`、`changes_process_cwd`) 全部保持 `False`。

---

## 3. What P2 Actually Implemented

### 3.1 P2-A：前端只读展示

**文件**: `apps/web/src/features/agents/components/AgentCodingSessionSnapshot.tsx`
**文件**: `apps/web/src/features/agents/components/AgentSessionList.tsx`
**文件**: `apps/web/src/features/agents/types.ts`

前端 `AgentSessionSnapshot` 类型包含全部 workspace 字段：

```typescript
workspace_type: string | null;
workspace_path: string | null;
workspace_clean: boolean | null;
last_workspace_error: string | null;
branch_name: string | null;
```

`AgentCodingSessionSnapshot` 组件以只读卡片形式展示：
- 智能体 (`agent_type`)
- 运行载体 (`runtime_type`)
- 后台通道 (`runtime_handle_id`)
- 分支 (`branch_name`)
- 工作区类型 (`workspace_type`)
- 工作区路径 (`workspace_path`)
- 最近工作区错误 (`last_workspace_error`)

组件底部固定显示免责声明：**"当前阶段只读展示 AgentSession 与 timeline 已有数据...这里不会创建或清理 worktree，也不表示已经进入 AI runtime、自动编码、提交、推送或创建 PR。"**

`AgentSessionList` 组件在每条会话中展示工作区类型、路径、分支名。

### 3.2 P2-A-R1：lifecycle audit 展示

**文件**: `apps/web/src/features/agents/components/AgentWorkspaceLifecycleAuditPanel.tsx`

从当前会话 timeline 中只读筛选 `event_type = "workspace_lifecycle_audit"` 消息，按时间倒序展示最近 3 条审计事件。

每个审计条目展示：
- 事件时间
- 事件类型 (`workspace.create.created` / `workspace.create.blocked` / `workspace.create.failed` / `workspace.cleanup.cleaned` / `workspace.cleanup.blocked` / `workspace.cleanup.failed`)
- 工作区路径 (`workspace_path`)
- 分支 (`branch_name`)
- 状态
- 阻止原因 (`blocked_reason`)
- 执行只读 git (`runs_git`)
- 执行写 git (`runs_write_git`)

面板包含免责声明：**"从当前会话 timeline 只读筛选 workspace lifecycle audit 事件；这里只展示审计结果，不调用创建、清理、worker 或 runtime。"**

### 3.3 P2-B：workspace preflight / context

**文件**: `runtime/orchestrator/app/workers/task_worker.py`
**函数**: `validate_worker_agent_workspace()` (L255–L377)
**函数**: `resolve_worker_workspace_context()` (L380–L410)

`validate_worker_agent_workspace()` 在 `TaskWorker.run_once()` 中对 AgentSession 进行只读 preflight：

1. 检查 `workspace_type == WORKTREE`——非 worktree 直接返回 `ready=True`（跳过 preflight）
2. 检查 `workspace_path` 非 None
3. 检查路径为绝对路径
4. 检查路径存在且为目录
5. 检查 `workspace_clean == True`

所有检查均为 Python `Path` 文件系统只读操作。不执行 `git status` 或其他 git 命令。

Preflight 失败阻断后续 executor：AgentSession 标记为 `STUCK/BLOCKED`，任务置为 `BLOCKED`，返回 `WorkerRunResult` 而不调用 `executor_service.execute_task()`。

`resolve_worker_workspace_context()` 将 validation 转为 evidence 结构体：

```python
@dataclass(slots=True, frozen=True)
class WorkerWorkspaceContextResolution:
    ready: bool
    source: str                    # "agent_session_worktree" | "agent_session_worktree_blocked" | "agent_session_non_worktree"
    reason_code: str | None
    workspace_path: str | None
    resolved_workspace_path: str | None
    uses_agent_workspace: bool
    changes_cwd: bool = False       # P2 阶段固定为 False
    runs_git: bool = False          # P2 阶段固定为 False
    runs_write_git: bool = False    # P2 阶段固定为 False
    launches_runtime: bool = False  # P2 阶段固定为 False
```

### 3.4 P2-B-R1：context evidence API

**文件**: `runtime/orchestrator/app/workers/task_worker.py` → `WorkerRunResult`
**文件**: `runtime/orchestrator/app/api/routes/workers.py` → `WorkerRunOnceResponse`

`WorkerRunResult` 新增 9 个 workspace context evidence 字段：

| 字段 | 类型 | 含义 |
|------|------|------|
| `workspace_context_ready` | `bool | None` | workspace context 是否就绪 |
| `workspace_context_source` | `str | None` | 来源标识 |
| `workspace_context_reason_code` | `str | None` | 未就绪原因码 |
| `workspace_context_path` | `str | None` | workspace_path 原始值 |
| `workspace_context_resolved_path` | `str | None` | 解析后的绝对路径 |
| `workspace_context_uses_agent_workspace` | `bool | None` | 是否使用 agent workspace |
| `workspace_context_changes_cwd` | `bool | None` | 是否改变 process cwd |
| `workspace_context_runs_git` | `bool | None` | 是否执行只读 git |
| `workspace_context_runs_write_git` | `bool | None` | 是否执行写 git |
| `workspace_context_launches_runtime` | `bool | None` | 是否启动 AI runtime |

全部字段通过 `WorkerRunOnceResponse` 透传至 `POST /workers/run-once` API。

### 3.5 P2-C：runtime launch dry-run evidence

**文件**: `runtime/orchestrator/app/workers/task_worker.py`
**函数**: `build_worker_runtime_launch_dry_run()` (L413–L548)
**数据类**: `WorkerRuntimeLaunchDryRun` (L224–L252)

`build_worker_runtime_launch_dry_run()` 构建 runtime launch 的纯预览 evidence，不调用任何 runtime：

1. 检查 `workspace_context.ready`——不 ready 返回 blocked
2. 检查 `uses_agent_workspace`——不满足返回 blocked
3. 检查 `agent_type`——缺失返回 blocked
4. 检查 `runtime_type`——缺失返回 blocked
5. 检查 `launch_cwd_preview`（即 `resolved_workspace_path`）——缺失返回 blocked
6. 生成 `launch_command_preview`：`RuntimeCreateConfig(session_id=..., runtime_type=..., agent_type=..., workspace_path=...)`

`WorkerRuntimeLaunchDryRun` 的硬性声明：

```python
execution_enabled: bool = False          # 不执行
changes_cwd: bool = False                # 不改变 cwd
runs_command: bool = False               # 不运行命令
runs_git: bool = False                   # 不运行 git
runs_write_git: bool = False             # 不运行 git write
launches_runtime: bool = False           # 不启动 AI runtime
```

`WorkerRunResult` 新增 17 个 runtime launch dry-run evidence 字段（`runtime_launch_dry_run_*`），通过 `WorkerRunOnceResponse` 透传至 API。

### 3.6 P2-D：pwd safe command proof

**文件**: `runtime/orchestrator/app/workers/worktree_safe_command.py`
**数据类**: `WorkerWorktreeSafeCommandProof` (L98–L122)
**类**: `WorkerPwdCommandRunner` (L41–L95)
**类**: `WorkerWorktreeSafeCommandProofRunner` (L125–L251)

`WorkerWorktreeSafeCommandProofRunner.run_probe()` 是 P2-D 的核心：

1. 检查 `workspace_context.ready`——不 ready 返回 blocked proof
2. 检查 `uses_agent_workspace`——不满足返回 skipped proof
3. 检查 `workspace_path`——缺失返回 blocked proof
4. 调用 `WorkerPwdCommandRunner.pwd(cwd=workspace_path)` 构建唯一的 allowlisted 命令 spec
5. 调用 `WorkerPwdCommandRunner.run(spec)` 执行 `pwd` 命令，subprocess `cwd` 指向 worktree
6. 验证 `observed_pwd == workspace_path`（即 `AgentSession.workspace_path`）
7. 验证 `allowlisted`（argv 必须恰好为 `("pwd",)`，`mutates_workspace` 必须为 `False`）
8. `ready = allowlisted and return_code == 0 and pwd_matches_workspace_path`

Proof 的硬性声明：

```python
changes_process_cwd: bool = False        # 不改变 process cwd
runs_git: bool = False                   # 不运行 git
runs_write_git: bool = False             # 不运行 git write
launches_worker_loop: bool = False       # 不启动 worker loop
launches_ai_runtime: bool = False        # 不启动 AI runtime
```

Proof 失败阻断 executor：在 `TaskWorker.run_once()` 中 (L1627–L1908)，当 `worktree_safe_command_proof.ready == False` 时，任务置为 `BLOCKED`、Run 置为 `CANCELLED`、failure_category 为 `EXECUTION_FAILED`，且 **不调用 `executor_service.execute_task()`**。测试 `test_worker_run_once_blocks_executor_when_worktree_safe_command_proof_fails` 通过 `_ExplodingExecutorService` 验证：executor 的任何方法被调用都会抛出 `AssertionError`。

`WorkerRunResult` 新增 20 个 proof evidence 字段（`worktree_safe_command_proof_*`），通过 `WorkerRunOnceResponse` 透传至 API。

---

## 4. P2-D Final Safety Contract

P2-D 的安全契约定义如下：

| 契约项 | 值 | 说明 |
|--------|-----|------|
| **默认命令** | `pwd` | 唯一 allowlisted 命令；`WorkerPwdCommandRunner._ensure_allowlisted()` 检查 `argv == ("pwd",)` |
| **不再使用的默认** | `git rev-parse --is-inside-work-tree` | P2-D 明确排除 git 命令作为默认 proof |
| **success 条件** | `observed_pwd == AgentSession.workspace_path` | pwd 输出必须精确匹配 AgentSession 的 workspace_path |
| **runs_git** | `False` | proof 不运行任何 git 命令 |
| **runs_write_git** | `False` | proof 不运行任何 git 写命令 |
| **changes_process_cwd** | `False` | proof 不改变宿主进程的 working directory |
| **launches_ai_runtime** | `False` | proof 不启动 Claude Code / Codex / DeepSeek / OpenCode 等任何 AI runtime |
| **launches_worker_loop** | `False` | proof 不启动后台 worker 循环 |
| **proof failed 行为** | 阻断 executor | `executor_service.execute_task()` 不被调用；任务置为 BLOCKED；Run 置为 CANCELLED |
| **不影响 executor_service.execute_task 的 cwd / 入参** | 无影响 | proof 在 executor 调用之前运行，通过早期返回来阻断；如果 proof 通过，executor 的调用方式与 P2-D 引入前完全一致 |

命令执行细节：

```python
# WorkerPwdCommandRunner.run()
subprocess.run(
    spec.argv,              # ("pwd",)
    cwd=spec.cwd,           # AgentSession.workspace_path
    capture_output=True,
    text=True,
    timeout=spec.timeout_seconds,  # 默认 30s
    check=False,            # 不抛异常，由 proof runner 检查 return code
    shell=False,            # 无 shell 注入风险（默认值，显式确认）
)
```

---

## 5. API / Evidence Fields

### 5.1 workspace_context_* 字段 (P2-B / P2-B-R1)

| 字段 | 来源数据类 | 含义 |
|------|-----------|------|
| `workspace_context_ready` | `WorkerWorkspaceContextResolution.ready` | workspace context 是否就绪 |
| `workspace_context_source` | `WorkerWorkspaceContextResolution.source` | `agent_session_worktree` / `agent_session_worktree_blocked` / `agent_session_non_worktree` |
| `workspace_context_reason_code` | `WorkerWorkspaceContextResolution.reason_code` | 未就绪原因码 |
| `workspace_context_path` | `WorkerWorkspaceContextResolution.workspace_path` | AgentSession.workspace_path 原始值 |
| `workspace_context_resolved_path` | `WorkerWorkspaceContextResolution.resolved_workspace_path` | 解析后的绝对路径 |
| `workspace_context_uses_agent_workspace` | `WorkerWorkspaceContextResolution.uses_agent_workspace` | 是否使用 agent worktree |
| `workspace_context_changes_cwd` | `WorkerWorkspaceContextResolution.changes_cwd` | 固定 `False` |
| `workspace_context_runs_git` | `WorkerWorkspaceContextResolution.runs_git` | 固定 `False` |
| `workspace_context_runs_write_git` | `WorkerWorkspaceContextResolution.runs_write_git` | 固定 `False` |
| `workspace_context_launches_runtime` | `WorkerWorkspaceContextResolution.launches_runtime` | 固定 `False` |

### 5.2 runtime_launch_dry_run_* 字段 (P2-C)

| 字段 | 来源数据类 | 含义 |
|------|-----------|------|
| `runtime_launch_dry_run_ready` | `WorkerRuntimeLaunchDryRun.ready` | dry-run 配置是否就绪 |
| `runtime_launch_dry_run_source` | `WorkerRuntimeLaunchDryRun.source` | `agent_session_worktree_runtime_dry_run` / `workspace_context_blocked` 等 |
| `runtime_launch_dry_run_reason_code` | `WorkerRuntimeLaunchDryRun.reason_code` | 未就绪原因码 |
| `runtime_launch_dry_run_session_id` | `WorkerRuntimeLaunchDryRun.session_id` | AgentSession ID |
| `runtime_launch_dry_run_agent_type` | `WorkerRuntimeLaunchDryRun.agent_type` | `openai_provider` / `claude_code` 等 |
| `runtime_launch_dry_run_runtime_type` | `WorkerRuntimeLaunchDryRun.runtime_type` | `subprocess` / `tmux` 等 |
| `runtime_launch_dry_run_workspace_path` | `WorkerRuntimeLaunchDryRun.workspace_path` | AgentSession.workspace_path |
| `runtime_launch_dry_run_resolved_workspace_path` | `WorkerRuntimeLaunchDryRun.resolved_workspace_path` | 解析后的绝对路径 |
| `runtime_launch_dry_run_launch_cwd_preview` | `WorkerRuntimeLaunchDryRun.launch_cwd_preview` | runtime 将使用的 cwd 预览 |
| `runtime_launch_dry_run_launch_command_preview` | `WorkerRuntimeLaunchDryRun.launch_command_preview` | `RuntimeCreateConfig(...)` 格式化字符串 |
| `runtime_launch_dry_run_uses_agent_workspace` | `WorkerRuntimeLaunchDryRun.uses_agent_workspace` | 是否使用 agent workspace |
| `runtime_launch_dry_run_command_preview_uses_workspace` | `WorkerRuntimeLaunchDryRun.command_preview_uses_workspace` | 命令预览是否引用 workspace |
| `runtime_launch_dry_run_execution_enabled` | `WorkerRuntimeLaunchDryRun.execution_enabled` | **固定 `False`** |
| `runtime_launch_dry_run_changes_cwd` | `WorkerRuntimeLaunchDryRun.changes_cwd` | **固定 `False`** |
| `runtime_launch_dry_run_runs_command` | `WorkerRuntimeLaunchDryRun.runs_command` | **固定 `False`** |
| `runtime_launch_dry_run_runs_git` | `WorkerRuntimeLaunchDryRun.runs_git` | **固定 `False`** |
| `runtime_launch_dry_run_runs_write_git` | `WorkerRuntimeLaunchDryRun.runs_write_git` | **固定 `False`** |
| `runtime_launch_dry_run_launches_runtime` | `WorkerRuntimeLaunchDryRun.launches_runtime` | **固定 `False`** |

### 5.3 worktree_safe_command_proof_* 字段 (P2-D)

| 字段 | 来源数据类 | 含义 |
|------|-----------|------|
| `worktree_safe_command_proof_ready` | `WorkerWorktreeSafeCommandProof.ready` | proof 是否通过 |
| `worktree_safe_command_proof_source` | `WorkerWorktreeSafeCommandProof.source` | `agent_session_worktree_safe_command` / `agent_session_worktree_safe_command_blocked` |
| `worktree_safe_command_proof_reason_code` | `WorkerWorktreeSafeCommandProof.reason_code` | 未通过原因码 |
| `worktree_safe_command_proof_command` | `WorkerWorktreeSafeCommandProof.command` | 执行命令字符串 (`"pwd"`) |
| `worktree_safe_command_proof_cwd` | `WorkerWorktreeSafeCommandProof.cwd` | subprocess cwd（worktree 路径） |
| `worktree_safe_command_proof_expected_workspace_path` | `WorkerWorktreeSafeCommandProof.expected_workspace_path` | `AgentSession.workspace_path` |
| `worktree_safe_command_proof_observed_pwd` | `WorkerWorktreeSafeCommandProof.observed_pwd` | pwd stdout（去空白） |
| `worktree_safe_command_proof_pwd_matches_workspace_path` | `WorkerWorktreeSafeCommandProof.pwd_matches_workspace_path` | `observed_pwd == workspace_path` |
| `worktree_safe_command_proof_exit_code` | `WorkerWorktreeSafeCommandProof.exit_code` | subprocess 返回码 |
| `worktree_safe_command_proof_stdout` | `WorkerWorktreeSafeCommandProof.stdout` | stdout 截断至 500 字符 |
| `worktree_safe_command_proof_stderr` | `WorkerWorktreeSafeCommandProof.stderr` | stderr 截断至 500 字符 |
| `worktree_safe_command_proof_timed_out` | `WorkerWorktreeSafeCommandProof.timed_out` | 是否超时 |
| `worktree_safe_command_proof_read_only` | `WorkerWorktreeSafeCommandProof.read_only` | `not spec.mutates_workspace` |
| `worktree_safe_command_proof_allowlisted` | `WorkerWorktreeSafeCommandProof.allowlisted` | 命令是否为 allowlisted 形状 |
| `worktree_safe_command_proof_uses_agent_workspace` | `WorkerWorktreeSafeCommandProof.uses_agent_workspace` | 是否使用 agent workspace |
| `worktree_safe_command_proof_changes_process_cwd` | `WorkerWorktreeSafeCommandProof.changes_process_cwd` | **固定 `False`** |
| `worktree_safe_command_proof_runs_command` | `WorkerWorktreeSafeCommandProof.runs_command` | `True`（执行了 `pwd`） |
| `worktree_safe_command_proof_runs_git` | `WorkerWorktreeSafeCommandProof.runs_git` | **固定 `False`** |
| `worktree_safe_command_proof_runs_write_git` | `WorkerWorktreeSafeCommandProof.runs_write_git` | **固定 `False`** |
| `worktree_safe_command_proof_launches_worker_loop` | `WorkerWorktreeSafeCommandProof.launches_worker_loop` | **固定 `False`** |
| `worktree_safe_command_proof_launches_ai_runtime` | `WorkerWorktreeSafeCommandProof.launches_ai_runtime` | **固定 `False`** |

### 5.4 关键声明

所有以上字段都是 **evidence**——它们记录 Worker 观察到的状态和计算出的预览。它们不表示：

- AI runtime 已经启动
- 进程 cwd 已经改变
- git 命令已经执行
- executor 已经用新参数调用
- 代码已经被修改

---

## 6. Reference Project Inspiration

Agent Orchestrator (ComposioHQ) 对 P2 阶段的关键启发：

### 6.1 workspacePath 作为 runtime / command seam

AO 的 `RuntimeCreateConfig` 将 `workspacePath` 作为核心 seam：
```typescript
interface RuntimeCreateConfig {
  workspacePath: string;  // ← runtime 启动时绑定的工作区路径
  sessionId: string;
  ...
}
```
P2-C 的 `build_worker_runtime_launch_dry_run()` 直接参考这个 seam：生成的 `RuntimeCreateConfig(...)` 预览中的 `workspace_path` 参数反映了同一设计意图——runtime 的 launch cwd 应绑定到 AgentSession 的 worktree 路径。

P2-D 的 `WorkerWorktreeSafeCommandProofRunner.run_probe()` 将此推进一步：不仅预览配置，还执行一个安全的只读 `pwd` 命令来证明 subprocess cwd 能正确指向 worktree 路径（`observed_pwd == workspace_path`）。

### 6.2 session / workspace / runtime / lifecycle 分轴

AO 的 `CanonicalSessionLifecycle` 三元组（session / pr / runtime）展示了独立维度联合推导整体状态的设计。P2 在四轴模型（session / workspace / runtime / delivery）的框架下，分别填充了：

- **Workspace Axis**: P2-A/P2-B — workspace path 进入 Worker preflight
- **Runtime Axis**: P2-C — runtime launch dry-run evidence；P2-D — safe command proof

P2 阶段 workspace context 和 runtime dry-run 的分离（先解析 context，再构建 dry-run，再运行 proof）遵循了 AO 的"独立变化、联合推导"原则。

### 6.3 不照搬的部分

| 不照搬 | 原因 |
|--------|------|
| 插件架构 (`PluginModule`/`PluginManifest`/8 类 slot) | AI-Dev 不需要完整插件系统；workspace/runtime 通过 Python 服务层和 Worker seam 管理 |
| `Runtime.create()` — 真实进程创建 | P2 阶段只做 dry-run，不启动真实 runtime 进程 |
| Node.js / TypeScript 技术栈 | AI-Dev 使用 Python + FastAPI + SQLite |
| Next.js dashboard | AI-Dev 有自己的 React 前端 |
| CLI `ao spawn/status/kill` | AI-Dev 是 web-first API 应用 |
| 以 Session 为顶层调度单元 | AI-Dev 以 Project → Task → Run 为顶层 |

---

## 7. Explicit Non-Goals

P2 阶段明确未做以下事项：

| # | 未做事项 | 说明 |
|---|---------|------|
| 1 | **不接真实 AI runtime** | 未启动 Claude Code / Codex / DeepSeek / OpenCode 或任何 AI 编码进程 |
| 2 | **不启动 AI 编码** | Agent 未进入 worktree 执行自主编码 |
| 3 | **不自动改代码** | 不修改任何仓库文件 |
| 4 | **不 git add / commit / push / PR 产品闭环** | Delivery Axis 全部未实现 |
| 5 | **不创建 / 删除 branch** | P1 create 创建了 branch，但 cleanup 不删除 branch；P2 不新增任何 branch 操作 |
| 6 | **不做 CI / review / merge** | SCM 集成全部未实现 |
| 7 | **不把 AI Project Director 总闭环标记为 Pass** | 总闭环明确为 Partial |
| 8 | **不创建 / 清理 worktree** | P1 已完成 worktree create/cleanup 基础设施；P2 只做只读 preflight 和 proof |
| 9 | **不改变 executor_service.execute_task 的 cwd / 入参** | proof 在 executor 之前运行，通过早期返回来阻断；executor 调用方式不变 |
| 10 | **不在 P2-D 中使用 `git rev-parse --is-inside-work-tree`** | 默认 proof 命令是 `pwd`，不使用任何 git 命令 |

---

## 8. Known Regression / Follow-up

### 8.1 本轮 targeted worker tests 通过

```
runtime/orchestrator/.venv/bin/pytest \
    runtime/orchestrator/tests/test_worker_workspace_readonly_validation.py -q

12 passed in 0.43s
```

12 个 targeted tests 覆盖：
- `test_validate_worker_agent_workspace_*` (7 tests): 各种 workspace 状态的 validation
- `test_runtime_launch_dry_run_targets_clean_worktree_without_execution`: dry-run 不启动 runtime
- `test_worktree_safe_command_proof_*` (4 tests): proof 通过/失败/跳过/拒绝 mutating probe
- `test_worker_run_once_blocks_executor_when_worktree_safe_command_proof_fails`: executor 阻断验证

### 8.2 全量 pytest 已知失败

全量 pytest 运行中，以下测试出现非 P2-D 修改引起的失败：

```
tests/test_project_director_confirmations.py::TestConfirmationInbox::test_pending_confirmation_plan_version_appears
  → 422 Unprocessable Entity (期望 201 Created)
```

**该失败不属于 P2-D worker/proof 修改范围**。失败发生在 `TestConfirmationInbox` 中，涉及 Project Director confirmation 流程，与 `worktree_safe_command.py`、`task_worker.py` 的 workspace/context/proof 修改无关联。

### 8.3 建议

后续单独做一次 regression cleanup——聚焦 `test_project_director_confirmations.py` 的 422 问题——不混入 P2 closure 文档。

---

## 9. Next Recommended Phase

不建议下一阶段直接进入 AI 自动编码。P2 的 "证明可以，但不执行" 模式应在 P3 继续深化：

| 阶段 | 方向 | 说明 |
|------|------|------|
| **P3-A** | runtime lifecycle design doc / dry-run API | 设计 RuntimeAxis 的完整生命周期（spawning → alive → exited → missing → probe_failed），定义 runtime launch 的 dry-run API contract |
| **P3-B** | Project Director Conversation Hub 设计 | 参考 gap analysis 的 P7 路线，设计 `ProjectDirectorConversation`、`ConversationList`、`Inbox`、`Router`、`ContextAssembler` 的数据模型 |
| **P3-C** | worker runtime adapter contract | 定义 Worker 与不同 runtime 类型（subprocess/tmux/docker）的适配器接口，作为 P2-C dry-run 的下游消费者 |
| **P3-D** | safe command proof 前端只读展示 | 将 `worktree_safe_command_proof_*` evidence 字段接入前端 Agent 线程页面，允许用户查看 proof 结果而不触发执行 |

**上述方向均为建议，不表示已完成。** P2 收口文档不宣称任何 P3 能力已实现。

---

## 10. Gate Statement

```
P2 Worker Context / Runtime Dry-run / Safe Command Proof: Pass
AI runtime automatic coding: Not started
Git add / commit / push / PR product loop: Not started
CI / review / merge loop: Not started
AI Project Director total closure: Partial
```

### 10.1 P2 各阶段 Gate

| 阶段 | Gate | 关键证据 |
|------|------|---------|
| P2-A | Pass | 前端 `AgentCodingSessionSnapshot` + `AgentSessionList` 只读展示 workspace 字段；所有组件含免责声明 |
| P2-A-R1 | Pass | `AgentWorkspaceLifecycleAuditPanel` 只读展示 create/cleanup audit 事件 |
| P2-B | Pass | `validate_worker_agent_workspace()` 只读 preflight；不运行 git |
| P2-B-R1 | Pass | `resolve_worker_workspace_context()` evidence 写入 `WorkerRunResult` 和 API |
| P2-C | Pass | `build_worker_runtime_launch_dry_run()` 生成 `RuntimeCreateConfig(...)` 预览；所有执行标志为 False |
| P2-D | Pass | `WorkerWorktreeSafeCommandProofRunner.run_probe()` 执行唯一 allowlisted `pwd`；proof 失败阻断 executor；12 targeted tests pass |

### 10.2 AI Project Director 总闭环

**仍为 Partial。**

P1 完成了 worktree 创建和清理的基础设施。P2 在此基础上完成了 Worker workspace context、runtime dry-run 和 safe command proof。但：

- **Runtime Axis**: ❌ AI agent 进程未启动，无 `agent_type` 对应的真实编码进程
- **Delivery Axis**: ❌ 无 git push / PR / CI / review / merge
- **四轴联合推导整体状态**: ❌ 未实现
- **Project Director Conversation Hub**: ❌ 未建设

P2 的全部能力集中在 "证明基础设施可以工作"——证明 Worker 能找到 worktree、runtime 配置能指向 worktree、命令能安全地在 worktree 中执行——但所有这些证明都带着 `execution_enabled=False`、`launches_runtime=False` 的硬性声明。

**AI Project Director 总闭环不能标记为 Pass。** 只有当 Runtime Axis 和 Delivery Axis 完成真实闭环、四轴联合状态推导实现、且 Project Director Conversation Hub 建成后，总闭环才有条件从 Partial 升级。

---

## 附录 A: 测试结果

### A.1 目标测试 (P2 worker workspace)

```
$ runtime/orchestrator/.venv/bin/pytest \
    runtime/orchestrator/tests/test_worker_workspace_readonly_validation.py -q

12 passed in 0.43s
```

### A.2 相邻测试 (P0 coding fields)

```
$ runtime/orchestrator/.venv/bin/pytest \
    runtime/orchestrator/tests/test_agent_session_p0_coding_fields.py -q

6 passed in 0.37s
```

### A.3 补充验证

```
$ python3 -m compileall -q runtime/orchestrator/app runtime/orchestrator/tests
(no output — clean)

$ git diff --check
(no output — clean)
```

---

## 附录 B: 提交历史 (P2-D / proof chain)

| Commit | 说明 |
|--------|------|
| `436ce8a` | Implement worker worktree safe read-only command |
| `69aa71b` | Refine worker worktree safe command proof |
| `f89a2bf` | Prove worker worktree cwd with pwd |
| `addec3a` | fix: expose worker safe command proof evidence |
| `6ebe05f` | fix: block executor when worktree proof fails |

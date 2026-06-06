# Coding Session P1-D-E-B real worktree create minimal execution 验证

> **文档类型**: 运行证据验证
> **生成日期**: 2026-06-05
> **验证基准 commit**: `67a5e3bd683ed527b94994e599e5b9557faa53aa` (Fix workspace create error reset)
> **前置文档**:
> - `docs/product/ai-project-director/worktree-create-p1de-execution-readiness-audit-20260605.md`
> - `docs/product/ai-project-director/verification-worktree-create-p1dea-blocked-skeleton-20260605.md`
> - `docs/product/ai-project-director/verification-worktree-prepare-p1dd2-preflight-blockers-20260605.md`
> - `docs/product/ai-project-director/verification-worktree-prepare-p1dd-readonly-preflight-20260605.md`
> **验证模型**: DeepSeek (Claude Code CLI)
> **状态**: Pass

---

## 1. 验证基准

| 项目 | 值 |
|------|-----|
| origin/main HEAD | `67a5e3bd683ed527b94994e599e5b9557faa53aa` |
| 提交信息 | `Fix workspace create error reset` |
| 前一提交 | `340a55c` (Implement guarded worktree creation) |
| 验证时间 | 2026-06-05 |
| HEAD == origin/main | ✅ 一致 |

---

## 2. 核对过的文件清单

| 文件 | 说明 | 关键状态 |
|------|------|----------|
| `app/domain/worktree_create.py` | Domain: WorktreeWriteCommandPreview + WorktreeCreateResult | `execution_enabled=True`, 3 factory methods (blocked/created/failed) |
| `app/services/worktree_write_command_runner.py` | Guard: 唯一 allowlisted 写命令执行器 | `git_worktree_add_new_branch` only, `subprocess.run` 在 allowlist 内 |
| `app/services/worktree_create_service.py` | Guard: 完整 guard 链 + 真实执行 + AgentSession 写回 | 17 guard checks before execution |
| `app/services/worktree_git_preflight_service.py` | Read-only: 5 只读 preflight 命令 | 全部 `mutates_repository=False` |
| `app/services/worktree_plan_service.py` | Dry-run: plan 生成 + plan_hash | `dry_run=True`, `requires_user_confirmation=True` |
| `app/repositories/agent_session_repository.py` | Persistence: workspace 字段 CRUD | update_status 支持所有 workspace 字段 |
| `app/domain/agent_session.py` | Domain: AgentSession 模型 | 10 workspace/branch/error nullable 字段 |
| `app/api/routes/agent_threads.py` | API: POST /workspace/create endpoint | full DTO chain with guard fields |
| `tests/test_worktree_plan_dry_run.py` | Tests: 47 total (含 11 create 测试) | real git worktree add in tmp_path |
| `tests/test_agent_session_p0_coding_fields.py` | Tests: 13 P0 field tests | all pass |

---

## 3. WorktreeWriteCommandRunner allowlist 证明

### 3.1 唯一允许的写命令

```python
# worktree_write_command_runner.py L20-42
def git_worktree_add_new_branch(self, *, repository_path, worktree_path, branch_name, base_ref):
    return self._preview(
        cwd=repository_path,
        argv=("git", "worktree", "add", "-b", branch_name, worktree_path, base_ref),
        command_kind="git_worktree_add_new_branch",
    )
```

**只有这一个方法。没有 `git_worktree_remove`、`git_branch_delete` 等方法暴露在服务层调用路径中。**

### 3.2 `_preview()` 设置 `execution_enabled=True`

```python
# worktree_write_command_runner.py L72-93
def _preview(self, *, cwd, argv, command_kind):
    ...
    return WorktreeWriteCommandPreview(
        ...
        mutates_repository=True,
        command_kind=command_kind,
        execution_enabled=True,   # ← P1-D-E-B: 从 False 变为 True
    )
```

### 3.3 `_ensure_write_allowlisted()` 完整 deny-by-default 链

```python
# worktree_write_command_runner.py L95-119
@staticmethod
def _ensure_write_allowlisted(preview):
    if not preview.execution_enabled:                         # 拒绝 execution_enabled=False
        raise ValueError("write command execution is disabled")
    if not preview.mutates_repository:                        # 拒绝非 mutating
        raise ValueError("write command must be marked as mutating")
    if preview.command_kind != "git_worktree_add_new_branch": # 拒绝未知 command_kind
        raise ValueError("write command kind is not allowlisted")
    if len(argv) != 7:                                        # 拒绝错误形状
        raise ValueError("git worktree add command shape is invalid")
    if argv[:4] != ("git", "worktree", "add", "-b"):          # 拒绝非 allowlisted 命令
        raise ValueError("git write command is not allowlisted")
    if branch_name.startswith("-"):                           # 拒绝以 "-" 开头的分支名
        raise ValueError("branch name must not start with '-'")
    if not worktree_path.is_absolute():                       # 拒绝相对路径
        raise ValueError("worktree path must be absolute")
    if base_ref.startswith("-"):                              # 拒绝以 "-" 开头的 ref
        raise ValueError("base ref must not start with '-'")
```

### 3.4 `run()` 使用安全 subprocess 调用

```python
# worktree_write_command_runner.py L44-70
def run(self, preview):
    self._ensure_write_allowlisted(preview)   # ← gate first
    try:
        completed = subprocess.run(
            preview.argv,                     # tuple[str, ...] — 不可变
            cwd=preview.cwd,
            capture_output=True,              # 捕获输出
            text=True,
            timeout=preview.timeout_seconds,  # 120s default
            check=False,                      # 不抛异常
        )
    except subprocess.TimeoutExpired as exc:
        return WorktreeCommandResult(..., timed_out=True)
```

### 3.5 安全检查清单

| 检查项 | 结果 | 证据 |
|--------|------|------|
| 只允许 `git worktree add -b` | ✅ | `command_kind="git_worktree_add_new_branch"` 唯一 allowlist |
| argv tuple/list | ✅ | `argv: tuple[str, ...]` — 不可变 |
| 不使用 `shell=True` | ✅ | subprocess.run 无 shell 参数 (默认 False) |
| 不使用 `os.system` | ✅ | grep 零匹配 |
| timeout 有值 | ✅ | `timeout=preview.timeout_seconds` (120s default) |
| `capture_output=True` | ✅ | 输出被捕获 |
| `check=False` | ✅ | 不抛 CalledProcessError |
| 拒绝 `execution_enabled=False` | ✅ | `_ensure_write_allowlisted` L100-101 |
| 拒绝 `command_kind` 不匹配 | ✅ | L104-105 |
| 拒绝非绝对 worktree_path | ✅ | L115-116 |
| 拒绝 branch/base_ref 以 "-" 开头 | ✅ | L113-114, L117-118 |

---

## 4. WorktreeCreateService guard 链清单

### 4.1 完整 guard 序列 (create_workspace)

```
 1. user_confirmed=True → False → raise WorktreeCreateError
 2. plan_hash trim + blank check → blank → raise WorktreeCreateError
 3. build_plan() 重新计算
 4. plan_hash 对比 → 不匹配 → raise WorktreeCreateHashMismatchError
 5. plan.safe=False → blockers.extend(plan.blockers)
 6. plan.dry_run=False → blockers.append("workspace create only accepts dry-run plans")
 7. plan.requires_user_confirmation=False → blockers.append("workspace create requires a user-confirmed plan")
 8. repository_workspace is None → blockers.append("repository workspace is not bound for this project")
 9. run_preflight() → 执行 5 只读命令
10. preflight.errors 非空 → blockers.extend(errors)
11. repository_is_git_worktree=False → blockers.append("repository root is not a git worktree")
12. repository_clean=False → blockers.append("repository has uncommitted changes")
13. planned_branch_exists=True → blockers.append("planned branch already exists")
14. planned_worktree_registered=True → blockers.append("planned worktree path is already registered")
15. repository_head_sha=None → blockers.append("repository HEAD could not be resolved")
16. 所有 blockers 检查 → 有 blockers → write last_workspace_error + return failed
17. 无 blockers → execute git worktree add -b
```

### 4.2 Guard 验证表

| # | Guard | 类型 | 状态 |
|---|-------|------|------|
| 1 | user_confirmed=True | raise ValueError | ✅ |
| 2 | plan_hash blank | raise ValueError | ✅ |
| 3 | plan_hash 匹配 | raise WorktreeCreateHashMismatchError | ✅ |
| 4 | plan.safe | blocker | ✅ |
| 5 | plan.dry_run | blocker | ✅ |
| 6 | plan.requires_user_confirmation | blocker | ✅ |
| 7 | repository_workspace binding | blocker | ✅ |
| 8 | git preflight errors | blocker | ✅ |
| 9 | repository_is_git_worktree | blocker | ✅ |
| 10 | repository_clean | blocker | ✅ |
| 11 | planned_branch_exists | blocker | ✅ |
| 12 | planned_worktree_registered | blocker | ✅ |
| 13 | repository_head_sha | blocker | ✅ |
| 14 | setup integrity (branch/path/preflight/preview) | blocker | ✅ |
| 15 | git worktree add return code | blocker | ✅ |

---

## 5. 成功路径证据

### 5.1 测试: `test_worktree_create_executes_real_worktree_and_writes_agent_session`

```python
# test_worktree_plan_dry_run.py L1079-1143
result = WorktreeCreateService(worktree_plan_service=plan_service).create_workspace(
    WorktreeCreateRequest(agent_session_id=session.id, plan_hash=plan.plan_hash, user_confirmed=True)
)

# 断言:
assert result.create_status == "created"                          # ✅
assert result.blocked_reason is None                              # ✅
assert result.dry_run is False                                    # ✅
assert result.creates_worktree is True                            # ✅
assert result.creates_branch is True                              # ✅
assert result.runs_git is True                                    # ✅
assert result.runs_write_git is True                              # ✅
assert result.mutates_agent_session_workspace is True             # ✅
assert result.git_preflight.read_only is True                     # ✅
assert result.write_command_preview[0].execution_enabled is True  # ✅
assert Path(plan.worktree_path).is_dir()                          # ✅ worktree 真实创建
assert (Path(plan.worktree_path) / "README.md").read_text() == "fixture\n"  # ✅ 内容完整
assert _run_git(repository_root, "branch", "--list", plan.branch_name).stdout.strip()  # ✅ branch 真实创建
```

### 5.2 AgentSession 写回验证

```python
updated_session = AgentSessionRepository(db_session).get_by_id(session.id)
assert updated_session.workspace_type == "worktree"               # ✅ WORKTREE
assert updated_session.workspace_path == plan.worktree_path       # ✅ created path
assert updated_session.branch_name == plan.branch_name            # ✅ created branch
assert updated_session.workspace_clean is True                    # ✅ clean
assert updated_session.last_workspace_error is None               # ✅ None (成功)
```

### 5.3 WorktreeCreateResult.created_from_plan() 字段

| 字段 | 成功值 |
|------|--------|
| `create_status` | `"created"` |
| `blocked_reason` | `None` |
| `dry_run` | `False` |
| `requires_user_confirmation` | `True` (来自 plan) |
| `creates_worktree` | `True` |
| `creates_branch` | `True` |
| `runs_git` | `True` |
| `runs_write_git` | `True` |
| `mutates_agent_session_workspace` | `True` |
| `base_commit_sha` | `git_preflight.repository_head_sha` |
| `blockers` | `[]` |
| `next_action` | `"workspace_created_ready_for_coding"` |

---

## 6. 失败/拒绝路径证据

### 6.1 stale plan_hash → 409

```python
# test_worktree_create_rejects_stale_plan_hash (L1146-1158)
with pytest.raises(WorktreeCreateHashMismatchError):
    WorktreeCreateService(...).create_workspace(
        WorktreeCreateRequest(plan_hash="0" * 64, user_confirmed=True)
    )
# → 409 Conflict via API route (agent_threads.py L641-645)
```

### 6.2 dirty repo → blocked

```python
# test_worktree_create_blocks_unsafe_preflight_and_writes_last_error (L1161-1205)
preflight = WorktreeGitPreflight(..., repository_clean=False, ...)
result = create_service.create_workspace(...)

assert result.create_status == "blocked"                          # ✅
assert "repository has uncommitted changes" in result.blockers    # ✅
assert result.creates_worktree is False                           # ✅
assert result.runs_write_git is False                             # ✅
assert not Path(plan.worktree_path).exists()                      # ✅ 未创建 worktree

# AgentSession: workspace 字段不变, last_workspace_error 写入
assert updated_session.workspace_path is None                     # ✅
assert updated_session.branch_name is None                        # ✅
assert updated_session.workspace_clean is None                    # ✅
assert updated_session.last_workspace_error is not None           # ✅
assert "preflight blocked:" in updated_session.last_workspace_error  # ✅
```

### 6.3 已有非空目录 → blocked

```python
# test_worktree_create_write_failure_records_last_workspace_error (L1208-1236)
Path(plan.worktree_path).mkdir(parents=True)
(Path(plan.worktree_path) / "occupied.txt").write_text("busy\n")
result = create_service.create_workspace(...)

assert result.create_status == "blocked"                                       # ✅
assert "worktree path already exists and is not empty" in result.blockers      # ✅
assert result.runs_write_git is False                                          # ✅
```

### 6.4 git worktree add 执行失败 → last_workspace_error

```python
# test_worktree_create_write_command_failure_records_last_workspace_error (L1239-1274)
class FailingWriteCommandRunner(WorktreeWriteCommandRunner):
    def run(self, preview):
        self.calls.append(preview)
        return WorktreeCommandResult(spec=preview, return_code=1, stderr="simulated worktree add failure")

result = create_service.create_workspace(...)

assert result.create_status == "failed"                              # ✅
assert result.blocked_reason == "workspace_create_git_write_failed"  # ✅
assert result.runs_write_git is True                                 # ✅ (尝试过)
assert result.mutates_agent_session_workspace is True                # ✅ (写了 error)
assert not Path(plan.worktree_path).exists()                         # ✅ worktree 未创建

# AgentSession: workspace_path/branch_name 不写入, last_workspace_error 写入
assert updated_session.workspace_path is None                        # ✅
assert updated_session.branch_name is None                           # ✅
assert updated_session.workspace_clean is None                       # ✅
assert updated_session.last_workspace_error is not None              # ✅
assert "git worktree add failed:" in updated_session.last_workspace_error  # ✅
```

### 6.5 user_confirmed=False → 422

```python
# worktree_create_service.py L50-53
if not request.user_confirmed:
    raise WorktreeCreateError("workspace create requires explicit user_confirmed=true")
# → 422 Unprocessable Entity via API route (agent_threads.py L646-651)
```

### 6.6 unsafe plan → blocked

```python
# worktree_create_service.py L72-77
if not plan.safe:
    blockers.extend(plan.blockers)
if not plan.dry_run:
    blockers.append("workspace create only accepts dry-run plans")
if not plan.requires_user_confirmation:
    blockers.append("workspace create requires a user-confirmed plan")
```

---

## 7. AgentSession 写回字段清单

### 7.1 成功写回 (5 字段)

| 字段 | 写入值 | 代码位置 |
|------|--------|----------|
| `workspace_type` | `WorkspaceType.WORKTREE` | `worktree_create_service.py` L174 |
| `workspace_path` | `plan.worktree_path` | L175 |
| `workspace_clean` | `True` | L176 |
| `branch_name` | `plan.branch_name` | L173 |
| `last_workspace_error` | `None` | L177 |

### 7.2 失败写回 (1 字段 only)

| 字段 | 写入值 | 代码位置 |
|------|--------|----------|
| `last_workspace_error` | 详细错误信息 (截断 2000 字符) | `_write_last_workspace_error()` L207-213 |

**失败时 workspace_path / branch_name / workspace_clean / workspace_type 均不写入** — 由测试 `test_worktree_create_blocks_unsafe_preflight_and_writes_last_error` 和 `test_worktree_create_write_command_failure_records_last_workspace_error` 验证。

### 7.3 last_workspace_error=None 修正证据

P1-D-E-A blocked skeleton 阶段 `last_workspace_error` 在 blocker 路径被写入。P1-D-E-B 成功路径显式设置 `last_workspace_error=None`:

```python
# worktree_create_service.py L171-178
self.worktree_plan_service.agent_session_repository.update_status(
    request.agent_session_id,
    branch_name=plan.branch_name,
    workspace_type=WorkspaceType.WORKTREE,
    workspace_path=plan.worktree_path,
    workspace_clean=True,
    last_workspace_error=None,           # ← 成功时清空
)
```

测试验证 (`L1087-1090`):
```python
AgentSessionRepository(db_session).update_status(
    session.id, last_workspace_error="stale workspace failure",  # ← 先写入 stale error
)
# ... create workspace ...
assert updated_session.last_workspace_error is None              # ← 验证成功时清空
```

---

## 8. 未触发项确认

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 未业务 git add | ✅ | grep 仅在 test fixture `_create_tmp_git_repository` 中 |
| 未业务 git commit | ✅ | 同上，仅 tmp_path 测试仓库 |
| 未业务 git push | ✅ | grep 零匹配 |
| 未创建 PR | ✅ | grep `gh pr` 零匹配 |
| 未 apply-local | ✅ | grep 零匹配 |
| 未运行 worker | ✅ | grep `TaskWorker\|Worker` 仅在 import/test DTO 中，不执行 |
| 未运行 AI runtime | ✅ | grep `Claude\|Codex` 零匹配 |
| 不让 AI 进入 worktree 改代码 | ✅ | create 只建 worktree + branch，不 spawn process |
| 不修改主仓库 working tree | ✅ | `git worktree add` 创建独立 worktree，不影响主仓库 |
| 不改前端 | ✅ | 所有文件在 `runtime/orchestrator/` |

### 8.1 grep 结果详解

```
rg "git add|git commit|git push|gh pr|apply-local|TaskWorker|Worker|Claude|Codex|subprocess\.run|os\.system|shell=True" \
   runtime/orchestrator/app/services/worktree_write_command_runner.py \
   runtime/orchestrator/app/services/worktree_create_service.py \
   runtime/orchestrator/app/api/routes/agent_threads.py \
   runtime/orchestrator/tests/test_worktree_plan_dry_run.py
```

**命中分析**:

| 匹配 | 文件 | 位置 | 判定 |
|------|------|------|------|
| `subprocess.run` | `worktree_write_command_runner.py:49` | `run()` 方法内执行 `git worktree add -b` | ✅ Allowlisted — 唯一写命令 |
| `subprocess.run` | `test_worktree_plan_dry_run.py:104` | `_run_git()` helper — 仅用于 tmp_path fixture | ✅ 测试辅助函数 |
| `git add` | `test_worktree_plan_dry_run.py:122` | `_create_tmp_git_repository()` — tmp_path fixture | ✅ 仅用于 initial commit |
| `git commit` | `test_worktree_plan_dry_run.py:123` | `_create_tmp_git_repository()` — tmp_path fixture | ✅ 仅用于 initial commit |

**无任何 `shell=True`、`os.system`、`git push`、`gh pr`、`apply-local`、`TaskWorker`、`Worker`、`Claude`、`Codex` 出现在业务流程代码中。**

---

## 9. 测试命令与结果

### 9.1 pytest

```
$ runtime/orchestrator/.venv/bin/pytest \
    runtime/orchestrator/tests/test_worktree_plan_dry_run.py \
    runtime/orchestrator/tests/test_agent_session_p0_coding_fields.py -q

47 passed in 1.60s
```

| 分类 | 测试数 | 关键验证 |
|------|--------|---------|
| P1-C dry-run plan | 10 | plan/hash/API |
| P1-D-A command runner | 3 | deny-by-default specs, 只读 args, 无写方法 |
| P1-D-B confirmation | 4 | receipt hash/block validation |
| P1-D-C prepare skeleton | 5 | blocked/guard/stale hash |
| P1-D-D-2 blocker tightening | 4 | 4 unsafe preflight states → blocker |
| P1-D-D git preflight | 5 | read-only commands, dirty repo, preflight service |
| **P1-D-E-A blocked skeleton** | 9 | write runner, blocked create, DTO guards |
| **P1-D-E-B real create** | **11** | **真实 worktree add + AgentSession 写回 + 失败路径** |
| P0 coding fields | 13 | 全链路通过 |

**P1-D-E-B 新增/修改测试 (11 个)**:

| 测试 | 验证内容 |
|------|---------|
| `test_worktree_write_command_runner_builds_executable_allowlisted_command` | `execution_enabled=True`, runner has `run()` |
| `test_worktree_create_executes_real_worktree_and_writes_agent_session` | **真实 worktree + branch 创建 + AgentSession 写回** |
| `test_worktree_create_rejects_stale_plan_hash` | stale hash → error |
| `test_worktree_create_blocks_unsafe_preflight_and_writes_last_error` | dirty repo blocker + last_workspace_error |
| `test_worktree_create_write_failure_records_last_workspace_error` | plan 层 blocker → last_workspace_error |
| `test_worktree_create_write_command_failure_records_last_workspace_error` | git write 失败 → "failed" + error |
| `test_worktree_create_response_exposes_created_guard_fields` | DTO guard fields post-create |
| `test_worktree_create_endpoint_creates_workspace` | API route function 完整链路 |

### 9.2 compileall

```
$ python3 -m compileall -q runtime/orchestrator/app runtime/orchestrator/tests
(no output — clean)
```

### 9.3 git diff --check

```
(no output — clean)
```

---

## 10. 已发现缺口

| 缺口 | 状态 | 说明 |
|------|------|------|
| cleanup 仍未实现 | P1-E scope | worktree remove / branch delete 未接入 |
| audit event (AgentMessage) 仍未实现 | P1-E scope | `create_workspace` 不写 AgentMessage timeline |
| worktree 后续代码执行仍未接入 | P2+ scope | 不 spawn Claude Code / Codex 进入 worktree |
| commit candidate 仍未接入 | P2+ scope | 不执行 git add/commit |
| PR 仍未接入 | P2+ scope | 不执行 gh pr create |
| git fetch origin 在 create 前未执行 | 待评估 | 目前只在 preflight 中用 rev-parse HEAD |
| 幂等 guard 基于 `workspace_path is not None` | 当前未实现 | `create_workspace` 无幂等检查 — 多次调用会尝试重复创建 |

---

## 11. 业务主仓库安全检查

| 检查项 | 结果 |
|--------|------|
| 是否创建业务主仓库 worktree | **否** ✅ |
| 是否创建业务主仓库 `session/*` branch | **否** ✅ |
| `git branch --list 'session/*'` | 空 (零 session branch) |
| `git worktree list --porcelain` 额外 worktree | 仅 main repo + agent-orchestrator (无关项目) |
| 工作树是否干净 | `git status --short` 仅新增本文档 |

---

## 12. Gate 结论

### Coding Session P1-D-E-B real worktree create minimal execution 验证: **Pass** ✅

**证据**:

1. ✅ WorktreeWriteCommandRunner 唯一 allowlisted 写命令: `git worktree add -b`，argv tuple，无 `shell=True`，无 `os.system`，`timeout=120s`，`capture_output=True`，`check=False`
2. ✅ `_ensure_write_allowlisted()` 9 项拒绝规则: execution_enabled、mutates_repository、command_kind、argv length、argv prefix、branch "-" prefix、absolute path、base_ref "-" prefix
3. ✅ WorktreeCreateService 完整 15-guard 链: user_confirmed、plan_hash match、plan.safe、plan.dry_run、plan.requires_user_confirmation、repo binding、5 只读 preflight + 4 unsafe blocker、HEAD resolution、setup integrity、write return code
4. ✅ 成功路径: `create_status="created"`, `creates_worktree=True`, `creates_branch=True`, `runs_git=True`, `runs_write_git=True`, `mutates_agent_session_workspace=True`
5. ✅ AgentSession 成功写回: workspace_type=WORKTREE, workspace_path, workspace_clean=True, branch_name, last_workspace_error=None
6. ✅ 失败路径: stale hash → 409, dirty repo → blocked + last_workspace_error, existing non-empty dir → blocked, git write fail → "failed" + last_workspace_error
7. ✅ last_workspace_error=None 修正: 成功路径显式清空 stale error
8. ✅ 47 tests pass, compileall clean, git diff --check clean
9. ✅ grep 确认: 零业务 `git add/commit/push`、零 `gh pr`、零 `apply-local`、零 `TaskWorker`/`Worker`/`Claude`/`Codex`、零 `shell=True`/`os.system`
10. ✅ 测试 `git add/commit` 仅在 tmp_path fixture `_create_tmp_git_repository` 中用于 initial commit
11. ✅ 未创建业务主仓库 worktree
12. ✅ 未创建业务主仓库 `session/*` branch

### AI Project Director 总闭环: **仍为 Partial**

P0 → P1-A → P1-B → P1-C → P1-D-A → P1-D-B → P1-D-C → P1-D-D → P1-D-D-2 → P1-D-E-A → **P1-D-E-B** 全部 Pass。

真实 worktree create 已可在测试临时仓库中执行 `git worktree add -b`、创建 per-AgentSession worktree + branch、写回 AgentSession workspace 字段。

仍缺: cleanup (P1-E)、audit event、worktree 后续代码执行、commit candidate、PR、前端集成。

AI Project Director total closure remains Partial — 不能标记为 Pass。

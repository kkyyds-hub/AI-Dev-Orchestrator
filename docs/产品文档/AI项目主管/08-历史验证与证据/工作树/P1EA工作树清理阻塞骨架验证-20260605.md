# Coding Session P1-E-A worktree cleanup blocked skeleton 验证

> **文档类型**: 运行证据验证
> **生成日期**: 2026-06-05
> **验证基准 commit**: `8113f3f47b2d7ddea7b55c4fb1a50aea6b1f1d82` (Coding Session P1-E-A worktree cleanup blocked skeleton)
> **前置文档**:
> - `docs/product/ai-project-director/worktree-cleanup-p1e-design-audit-20260605.md`
> - `docs/product/ai-project-director/verification-worktree-create-p1deb-real-create-20260605.md`
> - `docs/product/ai-project-director/worktree-create-p1de-execution-readiness-audit-20260605.md`
> - `docs/product/ai-project-director/coding-session-lifecycle-design-20260604.md`
> **验证模型**: DeepSeek (Claude Code CLI)
> **状态**: Pass

---

## 1. 验证基准

| 项目 | 值 |
|------|-----|
| origin/main HEAD | `8113f3f47b2d7ddea7b55c4fb1a50aea6b1f1d82` |
| 提交信息 | `Coding Session P1-E-A worktree cleanup blocked skeleton` |
| 验证时间 | 2026-06-05 |
| HEAD == origin/main | ✅ 一致 |

---

## 2. 新增/修改文件清单

| 文件 | 说明 |
|------|------|
| `app/domain/worktree_cleanup.py` | ✨ 新增 (127 行) — WorktreeCleanupCommandPreview + WorktreeCleanupResult |
| `app/services/worktree_cleanup_service.py` | ✨ 新增 (152 行) — blocked cleanup skeleton |
| `app/api/routes/agent_threads.py` | ✅ 扩展 — WorktreeCleanupRequestBody/Response + POST /workspace/cleanup |
| `tests/test_worktree_plan_dry_run.py` | ✅ 扩展 — 4 个新 cleanup 测试 |

---

## 3. WorktreeCleanupResult 字段清单 (22 字段)

| 字段 | 值 | 说明 |
|------|-----|------|
| `agent_session_id` | UUID | 关联会话 |
| `project_id` | UUID | 关联项目 |
| `repository_workspace_id` | `UUID \| None` | 仓库 ID |
| `plan_hash` | str(64) | 当前 plan hash |
| `submitted_plan_hash` | str(64) | 请求中的 hash |
| `cleanup_status` | `"blocked"` | blocked skeleton |
| `blocked_reason` | `"workspace_cleanup_blocked"` | 明确 blocked |
| `dry_run` | `True` | 仍是 dry-run |
| `requires_user_confirmation` | `True` | 仍需用户确认 |
| `worktree_path` | `str \| None` | 当前/计划路径 |
| `branch_name` | `str \| None` | 当前/计划分支名 |
| `base_branch` | `str \| None` | plan 基线 |
| `base_commit_sha` | `str \| None` | plan SHA |
| `checked_at` | datetime | 校验时间 |
| `cleanup_command_preview` | list[WorktreeCleanupCommandPreview] | 未来命令预览 |
| `blockers` | list[str] | 含 3 个 P1-E-A blocker |
| `warnings` | list[str] | 含 4 条 warning |
| `next_action` | str | `"keep_workspace_until_cleanup_execution_gate_passes"` |
| `removes_worktree` | **False** | 不删除 worktree |
| `deletes_branch` | **False** | 不删除 branch |
| `deletes_directory` | **False** | 不删除目录 |
| `runs_git` | **False** | 不运行 git |
| `runs_write_git` | **False** | 不运行写 git |
| `mutates_agent_session_workspace` | **False** | 不修改 AgentSession |

### 3.1 WorktreeCleanupCommandPreview (单个预览)

| 字段 | 值 | 说明 |
|------|-----|------|
| `argv` | tuple | 不可变命令参数 |
| `cwd` | str | 工作目录 |
| `timeout_seconds` | 120 | 超时 (default) |
| `mutates_repository` | `True` | 标注性质 |
| `command_kind` | `"git_worktree_remove"` 或 `"git_branch_delete"` | 命令类型 |
| `execution_enabled` | **False** | 硬编码不执行 |

### 3.2 域模型关键证据

```python
# worktree_cleanup.py L14-26
class WorktreeCleanupCommandPreview(DomainModel):
    """Disabled preview of one future cleanup command.

    P1-E-A exposes intended commands for review only.  These previews must not
    be passed to a runner and are always returned with execution_enabled=False.
    """
    execution_enabled: bool = False  # ← 硬编码 False


# worktree_cleanup.py L39-45
class WorktreeCleanupResult(DomainModel):
    """Blocked cleanup result for future workspace removal.

    P1-E-A is intentionally non-mutating: no git command is executed, no
    worktree or branch is deleted, no directory is removed, and AgentSession
    workspace fields are not changed.
    """
```

**注意**: WorktreeCleanupResult 只有 `blocked_from_plan()` 一个工厂方法；没有 `cleaned_from_plan()` 或 `failed_from_plan()` — 当前只能返回 blocked。

---

## 4. cleanup endpoint 清单

| Method | Path | Summary | 语义 |
|--------|------|---------|------|
| `POST` | `/agent-threads/sessions/{session_id}/workspace/cleanup` | Preview and block future workspace cleanup execution | blocked preview — 不执行任何删除 |

**请求体**:
```json
{ "plan_hash": "sha256...", "user_confirmed": true }
```

**响应 (200)**: 完整的 `WorktreeCleanupResponse` — 22 字段, 包含 `cleanup_command_preview` (命令预览), `removes_worktree=False`, `deletes_branch=False`, `deletes_directory=False`, `runs_git=False`, `runs_write_git=False`, `mutates_agent_session_workspace=False`

**错误**:
- `409` — plan_hash 不匹配 (stale)
- `422` — user_confirmed=False
- `404` — AgentSession 不存在

**API docstring 关键行** (agent_threads.py L760):
```
"""Return blocked cleanup preview; no worktree, branch, directory, or session mutation occurs."""
```

---

## 5. blocked skeleton 语义证明

### 5.1 WorktreeCleanupService 执行路径

```
cleanup_workspace():
  1. user_confirmed 校验 → False → raise WorktreeCleanupError (422)
  2. plan_hash trim + blank check → blank → raise WorktreeCleanupError (422)
  3. build_plan() 重新计算 → 纯计算 (零副作用)
  4. plan_hash 对比 → 不匹配 → raise WorktreeCleanupHashMismatchError (409)
  5. 读取 AgentSession → 只读 (零副作用)
  6. 构建 blockers: 3 固定 blocker 字符串
  7. 构建 warnings: 4 固定 warning 字符串
  8. 可选: 生成 cleanup_command_preview (纯对象构造, execution_enabled=False)
  9. 返回 WorktreeCleanupResult.blocked_from_plan()
```

**零副作用**: 无 git, 无文件系统, 无 DB write, 无 AgentSession mutation.

### 5.2 固定 blocker (3 个)

```python
# worktree_cleanup_service.py L70-73
blockers = [
    "workspace cleanup execution is blocked in P1-E-A",
    "git worktree remove is not enabled",
    "git branch delete is not enabled",
]
```

### 5.3 固定 warning (4 个)

```python
# worktree_cleanup_service.py L75-79
warnings = [
    "cleanup command preview is review-only and was not executed",
    "no worktree or branch was deleted",
    "no directory was removed",
    "AgentSession workspace fields were not changed",
]
```

### 5.4 cleanup command preview 生成

```python
# worktree_cleanup_service.py L123-151
@staticmethod
def _build_cleanup_command_preview(*, repository_cwd, worktree_path, branch_name):
    previews = []
    if worktree_path is not None:
        previews.append(WorktreeCleanupCommandPreview(
            argv=("git", "worktree", "remove", worktree_path),
            command_kind="git_worktree_remove",
            execution_enabled=False,         # ← 硬编码 False
        ))
    if branch_name is not None:
        previews.append(WorktreeCleanupCommandPreview(
            argv=("git", "branch", "-d", branch_name),  # ← -d (safe), 不是 -D (force)
            command_kind="git_branch_delete",
            execution_enabled=False,         # ← 硬编码 False
        ))
    return previews
```

**关键**: branch delete preview 使用 `-d` (safe delete)，不是 `-D` (force delete)。

---

## 6. Grep 结果分析

```
rg "subprocess|os\.system|git worktree remove|git branch -d|git branch -D|rm -rf|
    shutil\.rmtree|Path\.unlink|unlink\(|rmdir\(|workspace_path\s*=|branch_name\s*=|workspace_type\s*="
    <5 target files>
```

### 6.1 命中分析

| 匹配 | 文件 | 位置 | 判定 |
|------|------|------|------|
| `subprocess` import | `worktree_write_command_runner.py:6` | import 声明 | ✅ 用于 create 的 allowlisted `git worktree add -b` |
| `subprocess.run(` | `worktree_write_command_runner.py:49` | `run()` 方法内执行 `git worktree add -b` | ✅ Allowlisted write — 仅用于 create |
| `subprocess.TimeoutExpired` | `worktree_write_command_runner.py:57` | 异常处理 | ✅ 超时处理 |
| `branch_name = argv[4]` | `worktree_write_command_runner.py:110` | `_ensure_write_allowlisted()` 内读取 argv | ✅ 只读验证 |
| `"git worktree remove is not enabled"` | `worktree_cleanup_service.py:72` | blocker 字符串文本 | ✅ 文本消息，非执行 |
| `branch_name = session.branch_name or plan.branch_name` | `worktree_cleanup_service.py:89` | 只读读取 | ✅ 字段读取 |
| `branch_name=branch_name,` | `worktree_cleanup_service.py:97,105` | 传递给 factory 方法 | ✅ 对象构造 |
| `branch_name=branch_name,` | `worktree_cleanup.py:95` | factory 方法参数赋值 | ✅ 对象构造 |
| `branch_name=session.branch_name,` | `agent_threads.py:116` | DTO 转换读取 | ✅ 只读 |
| `workspace_type=(` | `agent_threads.py:117` | DTO 转换读取 | ✅ 只读 |
| `workspace_path=session.workspace_path,` | `agent_threads.py:120` | DTO 转换读取 | ✅ 只读 |
| `subprocess` import | `tests/test_worktree_plan_dry_run.py:10` | test 文件 import | ✅ 仅用于 tmp_path fixture |
| `subprocess.run(` | `tests/test_worktree_plan_dry_run.py:104` | `_run_git()` helper — tmp_path fixture | ✅ 测试辅助函数 |
| `workspace_type == "worktree"` | `tests/test_worktree_plan_dry_run.py` | 测试断言 | ✅ 断言检查 |
| `workspace_path == plan.worktree_path` | `tests/test_worktree_plan_dry_run.py` | 测试断言 | ✅ 断言检查 |
| `branch_name == plan.branch_name` | `tests/test_worktree_plan_dry_run.py` | 测试断言 | ✅ 断言检查 |
| `"git worktree remove is not enabled" in result.blockers` | `tests/test_worktree_plan_dry_run.py` | 测试断言 | ✅ 断言检查 |

### 6.2 关键结论

**在 cleanup 相关新文件 (`worktree_cleanup.py`, `worktree_cleanup_service.py`) 中:**
- ❌ 零 `subprocess` import
- ❌ 零 `os.system` 
- ❌ 零 `git worktree remove` 执行调用 (仅在字符串/argv preview 中出现)
- ❌ 零 `git branch -d` 执行调用 (仅在字符串/argv preview 中出现)
- ❌ 零 `git branch -D`
- ❌ 零 `rm -rf`
- ❌ 零 `shutil.rmtree`
- ❌ 零 `Path.unlink`
- ❌ 零 workspace_path / branch_name / workspace_type **写回** AgentSession

---

## 7. 未触发项确认

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 未执行 git worktree remove | ✅ | 无 subprocess/os.system in cleanup files; preview 仅 argv tuple |
| 未执行 git branch -d/-D | ✅ | 同上; branch delete 仅 preview argv tuple |
| 未删除任何目录 | ✅ | `deletes_directory=False`; 无 rm/rmdir/unlink in cleanup service |
| 未修改 AgentSession.workspace_path | ✅ | `mutates_agent_session_workspace=False`; 测试验证 None 不变 |
| 未修改 AgentSession.branch_name | ✅ | 测试验证 None 不变 |
| 未修改 AgentSession.workspace_type | ✅ | cleanup service 无 update_status 调用 |
| 未修改 RepositoryWorkspace | ✅ | 无 upsert 调用 |
| 未写 AgentMessage | ✅ | 无 append_message 调用 |
| 未运行 worker | ✅ | 无 TaskWorker 调用 |
| 未启动服务 | ✅ | tmp_path 隔离 |
| 未改前端 | ✅ | 4 文件全部 backend |

---

## 8. 测试命令与结果

### 8.1 目标测试 (worktree plan dry run)

```
$ runtime/orchestrator/.venv/bin/pytest \
    runtime/orchestrator/tests/test_worktree_plan_dry_run.py -q

45 passed in 1.71s
```

### 8.2 相邻测试 (P0 coding fields)

```
$ runtime/orchestrator/.venv/bin/pytest \
    runtime/orchestrator/tests/test_agent_session_p0_coding_fields.py -q

6 passed in 0.37s
```

### 8.3 合计: 51 tests pass

| 分类 | 测试数 | 关键验证 |
|------|--------|---------|
| P1-C dry-run plan | 10 | plan/hash/API |
| P1-D-A command runner | 3 | deny-by-default specs, 只读 args, 无写方法 |
| P1-D-B confirmation | 4 | receipt hash/block validation |
| P1-D-C prepare skeleton | 5 | blocked/guard/stale hash |
| P1-D-D-2 blocker tightening | 4 | 4 unsafe preflight states → blocker |
| P1-D-D git preflight | 5 | read-only commands, dirty repo, preflight service |
| P1-D-E-A blocked skeleton | 9 | write runner, blocked create, DTO guards |
| P1-D-E-B real create | 11 | 真实 worktree add + AgentSession 写回 + 失败路径 |
| **P1-E-A cleanup blocked skeleton** | **4** | **blocked cleanup + stale hash + DTO + endpoint** |
| P0 coding fields | 6 | 全链路通过 |

### 8.4 P1-E-A 新增测试 (4 个)

| 测试 | 验证内容 |
|------|---------|
| `test_worktree_cleanup_returns_blocked_preview_without_mutation` | blocked status + 3 blockers + 6 guard fields False + execution_enabled=False |
| `test_worktree_cleanup_rejects_stale_plan_hash` | stale hash → WorktreeCleanupHashMismatchError |
| `test_worktree_cleanup_response_exposes_blocked_guard_fields` | DTO 透传 6 guard fields |
| `test_worktree_cleanup_endpoint_returns_blocked_preview` | API route → 200 + blocked + cleanup_command_preview disabled |

**关键断言 (test_worktree_cleanup_returns_blocked_preview_without_mutation)**:
```python
assert result.cleanup_status == "blocked"
assert "workspace cleanup execution is blocked in P1-E-A" in result.blockers
assert "git worktree remove is not enabled" in result.blockers
assert "git branch delete is not enabled" in result.blockers
assert result.removes_worktree is False
assert result.deletes_branch is False
assert result.deletes_directory is False
assert result.runs_git is False
assert result.runs_write_git is False
assert result.mutates_agent_session_workspace is False
assert result.cleanup_command_preview[0].execution_enabled is False
assert result.cleanup_command_preview[1].execution_enabled is False
assert not Path(plan.worktree_path).exists()  # worktree 未创建 (test session 从未 create)

# AgentSession 字段完全不变
assert unchanged_session.workspace_path is None
assert unchanged_session.branch_name is None
assert unchanged_session.workspace_clean is None
assert unchanged_session.last_workspace_error is None
```

### 8.5 补充验证

```
$ python3 -m compileall -q runtime/orchestrator/app runtime/orchestrator/tests
(no output — clean)

$ git diff --check
(no output — clean)
```

---

## 9. 已发现缺口

| 缺口 | 状态 |
|------|------|
| 真实 cleanup 仍未实现 | P1-E-A 预期 — blocked skeleton only |
| 真实 git worktree remove 仍未执行 | 同上 |
| 真实 git branch -d 仍未执行 | 同上 |
| worktree clean 检查仍未接入 cleanup 执行 | 同上 |
| branch 删除仍未实现 | 同上 |
| cleanup audit event (AgentMessage) 仍未记录 | P1-E scope |
| cleanup_status 字段仍未实现 | 复用现有字段; 设计审计建议不需要新增 |
| WorktreeWriteCommandRunner 未扩展 cleanup 方法 | `git_worktree_remove` + `git_branch_delete_safe` 在 runner 中仍不存在 |

---

## 10. Gate 结论

### Coding Session P1-E-A worktree cleanup blocked skeleton 验证: **Pass** ✅

**证据**:
1. ✅ WorktreeCleanupResult 22 字段, 6 个 guard field 全部 False (`removes_worktree`, `deletes_branch`, `deletes_directory`, `runs_git`, `runs_write_git`, `mutates_agent_session_workspace`)
2. ✅ WorktreeCleanupCommandPreview `execution_enabled=False` hardcoded; 只有 `blocked_from_plan()` factory; 无 `cleaned_from_plan()`
3. ✅ WorktreeCleanupService 纯计算 — 零副作用; 无 subprocess/os.system import
4. ✅ 3 固定 blocker: `P1-E-A blocked`, `git worktree remove is not enabled`, `git branch delete is not enabled`
5. ✅ 4 固定 warning: `review-only`, `no deletion`, `no directory removed`, `no AgentSession mutation`
6. ✅ cleanup command preview 使用 `-d` (safe) 不是 `-D` (force)
7. ✅ API endpoint: `POST /workspace/cleanup`, summary `Preview and block`, docstring `no mutation occurs`
8. ✅ 4 个新测试: blocked result, stale hash rejection, DTO guard fields, endpoint return
9. ✅ 51 tests pass (45 worktree + 6 P0), compileall clean, git diff check clean
10. ✅ grep 确认: cleanup service 零 subprocess/os.system/rm/rmdir/unlink; 所有命中均为无害读取或 blocked 文本
11. ✅ 零 AgentSession.workspace_path/branch_name/workspace_type 写回
12. ✅ 零 worktree 创建, 零 worktree 删除, 零 directory 删除

### AI Project Director 总闭环: **仍为 Partial**

P0 → P1-A → P1-B → P1-C → P1-D-A → P1-D-B → P1-D-C → P1-D-D → P1-D-D-2 → P1-D-E-A → P1-D-E-B → **P1-E-A** 全部 Pass。

cleanup blocked skeleton 已就位。真实 cleanup 执行仍未实现。

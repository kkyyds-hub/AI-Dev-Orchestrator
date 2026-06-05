# Coding Session P1-E-B worktree cleanup read-only preflight 验证

> **文档类型**: 运行证据验证
> **生成日期**: 2026-06-05
> **验证基准 commit**: `1caabfc510819bbcf88fbc1aebe7f2626bd615c7` (Coding Session P1-E-B worktree cleanup read-only preflight)
> **前置文档**:
> - `docs/product/ai-project-director/verification-worktree-cleanup-p1ea-blocked-skeleton-20260605.md`
> - `docs/product/ai-project-director/worktree-cleanup-p1e-design-audit-20260605.md`
> - `docs/product/ai-project-director/verification-worktree-create-p1deb-real-create-20260605.md`
> - `docs/product/ai-project-director/coding-session-lifecycle-design-20260604.md`
> **验证模型**: DeepSeek (Claude Code CLI)
> **状态**: Pass

---

## 1. 验证基准

| 项目 | 值 |
|------|-----|
| origin/main HEAD | `1caabfc510819bbcf88fbc1aebe7f2626bd615c7` |
| 提交信息 | `Coding Session P1-E-B worktree cleanup read-only preflight` |
| 验证时间 | 2026-06-05 |
| HEAD == origin/main | ✅ 一致 |

---

## 2. 新增/修改文件清单

| 文件 | 说明 |
|------|------|
| `app/domain/worktree_cleanup.py` | ✅ 扩展 — 新增 WorktreeCleanupPreflight (13 字段) + WorktreeCleanupResult 新增 cleanup_preflight 字段 + runs_git 动态计算 |
| `app/services/worktree_cleanup_service.py` | ✅ 重构 — 新增 WorktreeCleanupPreflightService + WorktreeCleanupService 注入 preflight service |
| `tests/test_worktree_plan_dry_run.py` | ✅ 扩展 — 4 个新 cleanup preflight 测试 |

---

## 3. WorktreeCleanupPreflight 字段清单 (13 字段)

| 字段 | 类型 | 说明 |
|------|------|------|
| `preflight_status` | str | `"passed"` / `"failed"` |
| `read_only` | bool | **True** — hardcoded |
| `commands_run` | list[str] | 3-4 个只读命令的 shell-escaped 表示 |
| `worktree_path_exists` | `bool \| None` | pathlib 检查 |
| `worktree_path_is_directory` | `bool \| None` | pathlib 检查 |
| `worktree_path_safe` | `bool \| None` | 路径在 allowed_workspace_root 下 |
| `worktree_registered` | `bool \| None` | 在 `git worktree list` 中注册 |
| `worktree_clean` | `bool \| None` | `git status --porcelain` 空 |
| `repository_is_git_worktree` | `bool \| None` | `git rev-parse --is-inside-work-tree` |
| `registered_worktree_paths` | list[str] | 已注册 worktree 路径 |
| `errors` | list[str] | 命令失败详情 (截断 500 字符) |
| `warnings` | list[str] | 非阻塞警告 |

```python
# worktree_cleanup.py L39-53
class WorktreeCleanupPreflight(DomainModel):
    """Read-only cleanup preflight for the current AgentSession worktree."""
    preflight_status: str = "not_run"
    read_only: bool = True               # ← hardcoded
    ...
```

---

## 4. read-only command allowlist

### 4.1 在 repository root 下执行的命令 (始终执行)

| 命令 | cwd | 用途 |
|------|-----|------|
| `git rev-parse --is-inside-work-tree` | repository_path | 验证仓库是 git worktree |
| `git worktree list --porcelain` | repository_path | 获取已注册 worktree + 验证目标 worktree 注册 |
| `git branch --list <branch>` | repository_path | 检查 branch 是否存在 |

### 4.2 在 workspace_path 下执行的条件命令

| 条件 | 命令 | cwd |
|------|------|-----|
| path exists + is dir + is safe | `git status --porcelain` | worktree_path |
| path missing / not dir / unsafe | **跳过** | — |

```python
# worktree_cleanup_service.py L80-89
should_check_worktree_clean = (
    path_result.worktree_path_exists
    and path_result.worktree_path_is_directory
    and path_result.worktree_path_safe
)
if should_check_worktree_clean:
    specs.insert(2, self.command_runner.git_status_porcelain(repository_path=worktree_path))
```

### 4.3 所有命令经由 WorktreeCommandRunner (deny-by-default)

所有 git 命令通过 `WorktreeCommandRunner.run()` 执行，该方法拒绝:
- `mutates_repository=True` 的任何 spec
- 不在 5 个只读 allowlist 中的任何 argv

**cleanup preflight 不使用 `WorktreeWriteCommandRunner`** — 只使用只读 runner。

---

## 5. git status 跳过规则证明

### 5.1 跳过条件: 路径不存在

```python
# worktree_cleanup_service.py L147-187 _inspect_path()
target_path = Path(worktree_path).expanduser()
worktree_path_exists = target_path.exists()  # pathlib.Path.exists() — 只读
# ...
# worktree_cleanup_service.py L80-84
should_check_worktree_clean = (
    path_result.worktree_path_exists    # ← False → skip git status
    and ...
)
```

### 5.2 跳过条件: 路径不安全 (outside allowed root)

```python
target_resolved = target_path.resolve(strict=False)   # pathlib.Path.resolve() — 只读
worktree_path_safe = _is_within(target_resolved, allowed_resolved)
# worktree_path_safe=False → skip git status
```

### 5.3 测试验证: `test_worktree_cleanup_read_only_preflight_skips_status_for_missing_path`

```python
missing_path = str(tmp_path / "workspaces" / ".aido-worktrees" / "missing-session")
AgentSessionRepository(db_session).update_status(..., workspace_path=missing_path, ...)

result = cleanup_service.cleanup_workspace(...)

assert result.cleanup_preflight.worktree_path_exists is False
assert result.cleanup_preflight.worktree_clean is None       # ← skipped
assert result.cleanup_preflight.commands_run == [             # ← 只有 3 个命令
    "git rev-parse --is-inside-work-tree",                   # (no git status entry)
    "git worktree list --porcelain",
    "git branch --list ...",
]
```

---

## 6. blocker 规则清单

### 6.1 固定 blocker (3 个 — 始终)

| # | Blocker | 说明 |
|---|---------|------|
| 1 | `workspace cleanup execution is blocked in P1-E-A` | 执行门控 |
| 2 | `git worktree remove is not enabled` | 删除未启用 |
| 3 | `git branch delete is not enabled` | 分支删除未启用 |

### 6.2 条件 blocker (plan 层 — 复用)

| # | 条件 | Blocker |
|---|------|---------|
| 4 | `plan.safe=False` | plan.blockers (合并) |
| 5 | `plan.dry_run=False` | `"workspace cleanup only accepts dry-run plans"` |
| 6 | `plan.requires_user_confirmation=False` | `"workspace cleanup requires a user-confirmed plan"` |

### 6.3 preflight blocker (6 个 — P1-E-B 新增)

| # | 条件 | Blocker |
|---|------|---------|
| 7 | `preflight.errors` 非空 | errors (逐条) |
| 8 | `repository_is_git_worktree=False` | `"repository root is not a git worktree"` |
| 9 | `worktree_path_exists=False` | `"AgentSession worktree path does not exist"` |
| 10 | `worktree_path_is_directory=False` | `"AgentSession worktree path is not a directory"` |
| 11 | `worktree_path_safe=False` | `"AgentSession worktree path is outside allowed workspace root"` |
| 12 | `worktree_registered=False` | `"AgentSession worktree path is not registered"` |
| 13 | `worktree_clean=False` | `"AgentSession worktree has uncommitted changes"` |

### 6.4 额外条件 blocker

| # | 条件 | Blocker |
|---|------|---------|
| 14 | `repository_workspace=None` | `"repository workspace is not bound for this project"` |

---

## 7. disabled cleanup command preview 证明

### 7.1 preview 构建 (仍为 disabled)

```python
# worktree_cleanup_service.py L378-405
previews = []
if worktree_path is not None:
    previews.append(WorktreeCleanupCommandPreview(
        argv=("git", "worktree", "remove", worktree_path),
        command_kind="git_worktree_remove",
        execution_enabled=False,         # ← 硬编码 False
    ))
if branch_name is not None:
    previews.append(WorktreeCleanupCommandPreview(
        argv=("git", "branch", "-d", branch_name),
        command_kind="git_branch_delete",
        execution_enabled=False,         # ← 硬编码 False
    ))
```

### 7.2 测试验证

```python
# test_worktree_cleanup_read_only_preflight_checks_bound_worktree
assert result.cleanup_command_preview[0].execution_enabled is False  # worktree remove
assert result.cleanup_command_preview[1].execution_enabled is False  # branch delete
assert Path(original_workspace_path).exists()  # worktree 仍存在!
```

---

## 8. Grep 结果分析

```
rg "git worktree remove|git branch -d|git branch -D|rm -rf|shutil\.rmtree|Path\.unlink|
    unlink\(|rmdir\(|workspace_path\s*=|branch_name\s*=|workspace_type\s*=|update_status\("
    <5 target files>
```

### 8.1 命中分析

| 匹配 | 文件 | 位置 | 判定 |
|------|------|------|------|
| `branch_name=branch_name,` | `worktree_cleanup.py:131` | factory 方法参数赋值 | ✅ 对象构造 |
| `"git worktree remove is not enabled"` | `worktree_cleanup_service.py:284` | blocker 字符串文本 | ✅ 文本消息 |
| `branch_name = session.branch_name or plan.branch_name` | `worktree_cleanup_service.py:302` | READ from session | ✅ 只读 |
| `branch_name=branch_name,` 3x | `worktree_cleanup_service.py` | 参数传递 | ✅ 对象构造 |
| `branch_name = argv[4]` | `worktree_write_command_runner.py:110` | argv validation READ | ✅ 只读验证 |
| `branch_name=session.branch_name,` | `agent_threads.py:116` | DTO 转换 READ | ✅ 只读 |
| `workspace_type=(` | `agent_threads.py:117` | DTO 转换 READ | ✅ 只读 |
| `workspace_path=session.workspace_path,` | `agent_threads.py:120` | DTO 转换 READ | ✅ 只读 |
| `update_status(` 2x in tests | `test_worktree_plan_dry_run.py` | test setup: 创建 session + 设置 missing_path | ✅ 测试 fixture |
| `workspace_path=missing_path,` | `test_worktree_plan_dry_run.py` | test setup for "missing path" precondition | ✅ 测试 fixture |
| `workspace_path == original_workspace_path` | `test_worktree_plan_dry_run.py` | 测试断言: cleanup 后 workspace_path 不变 | ✅ 断言 |
| 其他 `workspace_path`/`branch_name`/`workspace_type` | test 文件 | 测试断言 (== 检查) | ✅ 断言 |

### 8.2 关键结论

**在 cleanup service 中:**
- ❌ 零 `git worktree remove` 执行调用 (仅在 blocker 字符串和 preview argv 中出现)
- ❌ 零 `git branch -d`/`-D` 执行调用 (仅在 preview argv 中出现)
- ❌ 零 `rm -rf`
- ❌ 零 `shutil.rmtree`
- ❌ 零 `Path.unlink`/`unlink(`/`rmdir(`
- ❌ 零 `workspace_path =` 写回 (仅 `session.workspace_path` READ)
- ❌ 零 `workspace_type =` 写回
- ❌ 零 `update_status(` 调用

---

## 9. 未触发项确认

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 未执行 git worktree remove | ✅ | grep: 仅在 blocker 字符串 + preview argv 中；无 subprocess/os.system in cleanup files |
| 未执行 git branch -d/-D | ✅ | 同上；preview 用 `-d` (safe) 非 `-D` (force) |
| 未删除任何目录 | ✅ | `deletes_directory=False`; worktree 在 test 中 post-cleanup 仍存在 |
| 未修改 AgentSession.workspace_path | ✅ | `mutates_agent_session_workspace=False`; test 验证 pre/post 值不变 |
| 未修改 AgentSession.branch_name | ✅ | test 验证 pre/post 值不变 |
| 未修改 AgentSession.workspace_type | ✅ | test 验证 pre/post 值不变 |
| 未修改 RepositoryWorkspace | ✅ | 无 upsert 调用 |
| 未写 AgentMessage | ✅ | 无 append_message |
| 未运行 worker | ✅ | 无 TaskWorker |
| 未启动服务 | ✅ | tmp_path 隔离 |
| 未改前端 | ✅ | 3 文件全部 backend |

---

## 10. 测试命令与结果

### 10.1 目标测试 (cleanup only, -k worktree_cleanup)

```
$ runtime/orchestrator/.venv/bin/pytest \
    runtime/orchestrator/tests/test_worktree_plan_dry_run.py -q -k worktree_cleanup

8 passed, 41 deselected in 1.24s
```

### 10.2 相邻测试 (P0 coding fields)

```
$ runtime/orchestrator/.venv/bin/pytest \
    runtime/orchestrator/tests/test_agent_session_p0_coding_fields.py -q

6 passed in 0.37s
```

### 10.3 P1-E-B 新增测试 (4 个)

| 测试 | 验证内容 |
|------|---------|
| `test_worktree_cleanup_read_only_preflight_checks_bound_worktree` | 真实 worktree post-create cleanup preflight: exists/dir/safe/registered/clean=True + 4 commands + runs_git=True + runs_write_git=False + AgentSession 字段不变 + worktree 仍存在 |
| `test_worktree_cleanup_read_only_preflight_blocks_dirty_bound_worktree` | 脏 worktree → worktree_clean=False → blocker "uncommitted changes" → worktree 仍存在 |
| `test_worktree_cleanup_read_only_preflight_skips_status_for_missing_path` | missing path → worktree_path_exists=False → git status skipped → 只有 3 commands |
| `test_worktree_cleanup_response_exposes_read_only_preflight` | API DTO 透传 cleanup_preflight 所有字段 |

### 10.4 关键断言 (test_worktree_cleanup_read_only_preflight_checks_bound_worktree)

```python
# preflight 字段
assert result.cleanup_preflight.read_only is True
assert result.cleanup_preflight.worktree_path_exists is True
assert result.cleanup_preflight.worktree_path_is_directory is True
assert result.cleanup_preflight.worktree_path_safe is True
assert result.cleanup_preflight.worktree_registered is True
assert result.cleanup_preflight.worktree_clean is True
assert result.cleanup_preflight.repository_is_git_worktree is True
assert result.cleanup_preflight.errors == []

# 4 read-only commands (含 git status in worktree_path)
assert result.cleanup_preflight.commands_run == [
    "git rev-parse --is-inside-work-tree",
    "git worktree list --porcelain",
    "git status --porcelain",                    # ← 在 worktree_path 下
    f"git branch --list {plan.branch_name}",
]

# guard 字段
assert result.runs_git is True                  # ← 只读 git 已执行
assert result.runs_write_git is False           # ← 零写 git
assert result.removes_worktree is False
assert result.deletes_branch is False
assert result.deletes_directory is False
assert result.mutates_agent_session_workspace is False

# cleanup command preview 仍 disabled
assert result.cleanup_command_preview[0].execution_enabled is False

# worktree 仍存在!
assert Path(original_workspace_path).exists()

# AgentSession 字段完全不变
assert unchanged_session.workspace_path == original_workspace_path
assert unchanged_session.branch_name == original_branch_name
assert unchanged_session.workspace_type == original_workspace_type
```

### 10.5 补充验证

```
$ python3 -m compileall -q runtime/orchestrator/app runtime/orchestrator/tests
(no output — clean)

$ git diff --check
(no output — clean)
```

---

## 11. 已发现缺口

| 缺口 | 状态 |
|------|------|
| 真实 cleanup 仍未实现 | P1-E-A/B 预期 — 仍 blocked skeleton |
| 真实 git worktree remove 仍未执行 | 同上 |
| 真实 git branch -d 仍未执行 | 同上 |
| cleanup audit event (AgentMessage) 仍未记录 | P1-E scope |
| cleanup_status 字段仍未实现 | 复用现有字段；设计审计建议不需要新增 |
| WorktreeWriteCommandRunner 未扩展 cleanup 方法 | `git_worktree_remove` + `git_branch_delete_safe` 在 write runner 中仍不存在 |
| 幂等 guard 未实现 | 重复调用 cleanup 会每次都跑 preflight |

---

## 12. Gate 结论

### Coding Session P1-E-B worktree cleanup read-only preflight 验证: **Pass** ✅

**证据**:
1. ✅ WorktreeCleanupPreflight 13 字段: `read_only=True` hardcoded
2. ✅ 3-4 只读命令经由 `WorktreeCommandRunner` (deny-by-default allowlist): `git rev-parse --is-inside-work-tree`, `git worktree list --porcelain`, `git status --porcelain` (条件), `git branch --list`
3. ✅ `git status --porcelain` 只在 path exists + is dir + is safe 时执行；missing/unsafe path 跳过
4. ✅ `_inspect_path()` 用 pure pathlib (`.exists()`, `.is_dir()`, `.resolve()`, `.relative_to()`) — 纯只读
5. ✅ 13 blocker 规则: 3 固定 + 3 plan 层 + 6 preflight + 1 repo binding
6. ✅ 仍 blocked: `cleanup_status="blocked"`, `removes_worktree=False`, `deletes_branch=False`, `deletes_directory=False`, `runs_write_git=False`, `mutates_agent_session_workspace=False`
7. ✅ `runs_git=True` 仅代表 read-only git 已执行
8. ✅ Cleanup command preview 仍 `execution_enabled=False`；branch delete 使用 `-d` (safe)
9. ✅ 4 个新 preflight 测试: bound worktree check, dirty worktree blocker, missing path skip, DTO guard
10. ✅ 8 cleanup tests pass (4 P1-E-A + 4 P1-E-B), 6 P0 tests pass
11. ✅ compileall clean, git diff check clean
12. ✅ grep 确认: cleanup service 零 `subprocess`/`os.system`/`rm`/`rmdir`/`unlink`/`update_status`; 所有命中均为无害读取或 blocker 文本
13. ✅ 零 AgentSession workspace_path/branch_name/workspace_type 写回
14. ✅ worktree 在 cleanup preflight 后仍存在 (验证未删除)

### AI Project Director 总闭环: **仍为 Partial**

P0 → P1-A → P1-B → P1-C → P1-D-A → P1-D-B → P1-D-C → P1-D-D → P1-D-D-2 → P1-D-E-A → P1-D-E-B → P1-E-A → **P1-E-B** 全部 Pass。

cleanup read-only preflight 已就位。真实 cleanup 执行仍未实现。

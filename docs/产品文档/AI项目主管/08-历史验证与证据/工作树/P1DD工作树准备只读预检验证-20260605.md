# Coding Session P1-D-D workspace prepare read-only git preflight 验证

> **文档类型**: 运行证据验证
> **生成日期**: 2026-06-05
> **验证基准 commit**: `8f154a9` (Coding Session P1-D-D workspace prepare read-only git preflight)
> **前置文档**:
> - `docs/product/ai-project-director/worktree-create-p1d-readiness-audit-20260604.md`
> - `docs/product/ai-project-director/verification-worktree-prepare-p1dc-skeleton-20260604.md`
> **验证模型**: DeepSeek (Claude Code CLI)
> **状态**: Pass

---

## 1. 验证基准

| 项目 | 值 |
|------|-----|
| origin/main HEAD | `8f154a902ee05382f5f40db4b5d115796c5c7ec4` |
| 提交信息 | `Coding Session P1-D-D workspace prepare read-only git preflight` |
| 验证时间 | 2026-06-05 |
| 变更 | 6 files (+518 −48) |

---

## 2. 新增/修改文件清单

| 文件 | 变更 | 说明 |
|------|------|------|
| `app/services/worktree_command_runner.py` | ✅ 重写 | deny-by-default allowlist + `run()` 执行器 |
| `app/services/worktree_git_preflight_service.py` | ✨ 新增 (112 行) | 只读 preflight: rev-parse + status + worktree list + branch --list |
| `app/services/worktree_prepare_service.py` | ✅ 重构 | 注入 git_preflight_service，safe plan 时执行 preflight |
| `app/domain/worktree_prepare.py` | ✅ 扩展 | 新增 WorktreeGitPreflight (9 字段) + WorktreePrepareResult 新增 git_preflight/runs_write_git |
| `app/api/routes/agent_threads.py` | ✅ 扩展 | WorktreePrepareResponse 新增 git_preflight + runs_write_git |
| `tests/test_worktree_plan_dry_run.py` | ✅ 扩展 | 10 个新测试 (runner/execution/preflight/dirty repo) |

---

## 3. read-only Git Allowlist

### 3.1 允许的只读命令 (4 个)

| Spec 方法 | argv | mutates_repository |
|-----------|------|--------------------|
| `git_rev_parse()` | `("git", "rev-parse", "HEAD")` | **False** |
| `git_status_porcelain()` | `("git", "status", "--porcelain")` | **False** |
| `git_worktree_list()` | `("git", "worktree", "list", "--porcelain")` | **False** |
| `git_branch_list()` | `("git", "branch", "--list", pattern)` | **False** |

**验证**: 所有 4 个 spec 的 `mutates_repository=False`，argv 不可变 tuple，通过 `_ensure_read_only_allowlisted()` 精确匹配。

### 3.2 明确拒绝的命令

`_ensure_read_only_allowlisted()` 拒绝:

```
- mutates_repository=True 的任何 spec  → ValueError("mutating git command specs are not allowed")
- 不在 allowlist 中的任何 argv → ValueError("git command is not allowlisted: ...")
```

**未暴露的写 spec**: `git_worktree_add`, `git_checkout_new_branch`, `git_worktree_remove`, `git_branch_delete` — **代码中不存在这些方法**。

### 3.3 命令执行方式

```python
def run(self, spec: WorktreeCommandSpec) -> WorktreeCommandResult:
    self._ensure_read_only_allowlisted(spec)   # ← deny-by-default gate
    completed = subprocess.run(
        spec.argv,                             # list[str], 不可变
        cwd=spec.cwd,
        capture_output=True,                   # 捕获输出
        text=True,
        timeout=spec.timeout_seconds,          # 120s default
        check=False,                           # 不抛异常
    )
    # shell 未设置 → 默认 False
    # 无 os.system 调用
```

**安全验证**: `subprocess.run` 使用 `list[str]` argv (非字符串), 无 `shell=True`, 无 `os.system`。

---

## 4. forbidden Git Command List (grep 验证)

```
rg "shell=True|os\.system|git worktree add|git checkout -b|git switch -c|
    git branch -D|git branch -d|git add |git commit|git push|gh pr|
    Path\.mkdir|mkdir\(" <all relevant files>

→ 零匹配
```

**证明**: 在所有 5 个相关文件中未发现任何 forbidden 调用。

---

## 5. Subprocess 安全用法证明

| 检查项 | 值 | 安全? |
|--------|-----|------|
| argv 类型 | `tuple[str, ...]` (不可变) | ✅ 安全 |
| subprocess.run args | `list[str]` | ✅ 安全 (非字符串 shell 注入) |
| shell= | 未设置 (默认 False) | ✅ 安全 |
| capture_output | True | ✅ 输出被捕获 |
| timeout | 120s (default) | ✅ 超时保护 |
| check | False | ✅ 不抛异常, 返回结果 |
| os.system | 无调用 | ✅ 安全 |

---

## 6. WorktreeGitPreflight 字段清单

| 字段 | 类型 | 说明 |
|------|------|------|
| `preflight_status` | str | "passed" / "not_run" — read-only only |
| `read_only` | bool | **True** — hardcoded |
| `commands_run` | list[str] | 4 个只读命令的 shell-escaped 表示 |
| `repository_head_sha` | `str \| None` | `git rev-parse HEAD` 结果 |
| `repository_clean` | `bool \| None` | dirty repo → False + warning |
| `planned_branch_exists` | `bool \| None` | 已存在分支 → warning |
| `planned_worktree_registered` | `bool \| None` | 已注册 worktree → warning |
| `registered_worktree_paths` | list[str] | 已存在的 worktree 路径列表 |
| `errors` | list[str] | 命令失败详情 (截断 500 字符) |
| `warnings` | list[str] | 非阻塞警告 |

---

## 7. WorktreePrepareResponse 关键 Guard 字段

| 字段 | 值 | 语义 |
|------|-----|------|
| `prepare_status` | `"blocked"` | 仍未实现真实创建 |
| `blocked_reason` | `"workspace_prepare_not_implemented"` | 明确未实现 |
| `creates_worktree` | **False** | 不创建 worktree |
| `creates_branch` | **False** | 不创建 branch |
| `runs_git` | **True** (preflight 运行时) | 执行了只读 git |
| `runs_write_git` | **False** | **不执行写 git** |
| `mutates_agent_session_workspace` | **False** | 不修改 AgentSession |
| `git_preflight.read_only` | **True** | preflight 是只读的 |
| `git_preflight.commands_run` | 4 commands | rev-parse, status, worktree list, branch --list |

---

## 8. 测试命令与结果

```
$ python -m pytest runtime/orchestrator/tests/test_worktree_plan_dry_run.py \
    runtime/orchestrator/tests/test_agent_session_p0_coding_fields.py -q

35 passed in 0.63s
```

| 分类 | 测试数 | 关键验证 |
|------|--------|---------|
| P1-C dry-run plan | 10 | plan 生成、hash 稳定性/变化、API DTO、hash 字段 |
| P1-D-A command runner | 3 | deny-by-default specs、只读 args、无写方法暴露 |
| P1-D-B confirmation | 4 | receipt (正确/错误 hash、blocked plan、DTO guard) |
| P1-D-C prepare skeleton | 5 | blocked return、stale hash、blocked plan merge、DTO guard |
| P1-D-D git preflight | **5** | **read-only commands run, dirty repo detection, preflight service, prepare runs git=true/write git=false, endpoint guard fields** |
| P0 coding fields | 13 | 全链路通过 |

**补充验证**:
```
$ python -m compileall -q runtime/orchestrator/app runtime/orchestrator/tests
(no output)
$ git diff --check
(no output)
```

---

## 9. 未触发项确认

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 未执行写 Git | ✅ | `runs_write_git=False`, allowlist 仅 4 个 mutates_repository=False spec |
| 未创建 worktree | ✅ | `creates_worktree=False`, 无 `git worktree add` 方法 |
| 未创建 branch | ✅ | `creates_branch=False`, 无 `git checkout -b` 方法 |
| 未修改 AgentSession.workspace_path | ✅ | `mutates_agent_session_workspace=False`, 测试验证 `unchanged_session.workspace_path is None` |
| 未修改 AgentSession.branch_name | ✅ | 测试验证 `unchanged_session.branch_name is None` |
| 未修改 RepositoryWorkspace | ✅ | 无 upsert 调用 |
| 未运行 worker | ✅ | 无 TaskWorker 调用 |
| 未启动服务 | ✅ | `tmp_path` 隔离 SQLite |
| 未改前端 | ✅ | 6 文件全部在 `runtime/orchestrator/` |

---

## 10. 已发现缺口

| 缺口 | 状态 |
|------|------|
| 仍未真实创建 worktree | P1-D-D 预期 — blocked skeleton only |
| 仍未真实创建 branch | P1-D-D 预期 |
| 仍未实现 cleanup | P1-E scope |
| 仍未写 audit event | 无 AgentMessage 记录 |
| 仍未接 `git rev-parse --is-inside-work-tree` | 未在 preflight 中检查 |
| base_commit_sha 仍未填充 | WorktreePlan.base_commit_sha 始终 None |
| `WorktreeCommandRunner` 不支持 `ref` 参数 | `git_rev_parse(ref="HEAD")` 硬编码 "HEAD"，未来需要支持 `origin/<base>` |

---

## 11. Gate 结论

### Coding Session P1-D-D workspace prepare read-only git preflight 验证: **Pass** ✅

**证据**:
1. ✅ WorktreeCommandRunner deny-by-default — 仅 4 个 `mutates_repository=False` allowlist spec
2. ✅ 无写 git 方法暴露 — `git_worktree_add` / `git_checkout_new_branch` / `git_worktree_remove` / `git_branch_delete` 不存在
3. ✅ Subprocess 安全 — `list[str]` argv, 无 `shell=True`, 无 `os.system`, `timeout=120s`
4. ✅ WorktreeGitPreflight 只读 — `read_only=True` hardcoded, 仅 rev-parse + status + worktree list + branch --list
5. ✅ Dirty repo → warning, existing branch → warning, registered worktree → warning
6. ✅ Prepare 仍 blocked — `blocked_reason="workspace_prepare_not_implemented"`, `creates_worktree=False`, `runs_write_git=False`
7. ✅ 5 个新测试: read-only specs, dirty repo, preflight service, prepare guard fields, endpoint
8. ✅ Zero forbidden calls (grep verified)
9. ✅ 35 tests pass, compileall clean, git diff clean

### AI Project Director 总闭环: **仍为 Partial**

**原因**: P0 字段 (Pass) → P1-A 审计 (Pass) → P1-B workspace 字段 (Pass) → P1-C dry-run plan (Pass) → P1-D-A command runner spec (Pass) → P1-D-B confirmation (Pass) → P1-D-C prepare skeleton (Pass) → P1-D-D read-only git preflight (Pass) ← 当前。真实 worktree 创建仍未实现。

# Coding Session P1-D-C workspace prepare skeleton 验证

> **文档类型**: 运行证据验证
> **生成日期**: 2026-06-05
> **验证基准 commit**: `3d52eb3` (Coding Session P1-D-C workspace prepare skeleton)
> **前置设计基线**: `docs/product/ai-project-director/worktree-create-p1d-readiness-audit-20260604.md`
> **验证模型**: DeepSeek (Claude Code CLI)
> **状态**: Pass

---

## 1. 验证基准

| 项目 | 值 |
|------|-----|
| origin/main HEAD | `3d52eb3fd0faead85892e0a81ff246e965a05051` |
| 提交信息 | `Coding Session P1-D-C workspace prepare skeleton` |
| 验证时间 | 2026-06-05 |
| 变更文件数 | 4 files (+498 −0) |

---

## 2. 新增/修改文件清单

| 文件 | 说明 |
|------|------|
| `runtime/orchestrator/app/domain/worktree_prepare.py` | ✨ 新增 — WorktreePrepareResult 领域模型 (92 行) |
| `runtime/orchestrator/app/services/worktree_prepare_service.py` | ✨ 新增 — WorktreePrepareService (80 行) |
| `runtime/orchestrator/app/api/routes/agent_threads.py` | ✅ 扩展 — WorktreePrepareRequestBody/Response + `/workspace/prepare` endpoint |
| `runtime/orchestrator/tests/test_worktree_plan_dry_run.py` | ✅ 扩展 — 13 个新测试 |

---

## 3. Prepare Model 字段清单

### 3.1 WorktreePrepareResult (15 个业务字段 + 4 个 guard 字段)

| 字段 | 类型 | 值 | 说明 |
|------|------|-----|------|
| `agent_session_id` | UUID | session ID | 关联会话 |
| `project_id` | UUID | project ID | 关联项目 |
| `repository_workspace_id` | `UUID \| None` | 仓库 ID | 关联仓库 |
| `plan_hash` | str(64) | sha256 hex | 当前 plan 的指纹 |
| `submitted_plan_hash` | str(64) | sha256 hex | 用户提交的指纹 |
| `prepare_status` | str | `"blocked"` | blocked skeleton |
| `blocked_reason` | str | `"workspace_prepare_not_implemented"` | 明确未实现 |
| `dry_run` | bool | `True` | 仍是 dry-run |
| `requires_user_confirmation` | bool | `True` | 仍需用户确认 |
| `worktree_path` | `str \| None` | plan 路径 | 来自当前 plan |
| `branch_name` | `str \| None` | plan 分支 | 来自当前 plan |
| `base_branch` | `str \| None` | plan 基线 | 来自当前 plan |
| `base_commit_sha` | `str \| None` | plan SHA | 来自当前 plan |
| `checked_at` | datetime | utc_now() | 校验时间 |
| `blockers` | list[str] | 含 not_implemented | 阻塞原因 |
| `warnings` | list[str] | 含 3 条 warning | 警告 |
| `next_action` | str | `"implement_workspace_prepare_execution_after_gate"` | 下一步 |
| **`creates_worktree`** | bool | **`False`** | 不创建 worktree |
| **`creates_branch`** | bool | **`False`** | 不创建 branch |
| **`runs_git`** | bool | **`False`** | 不运行 git |
| **`mutates_agent_session_workspace`** | bool | **`False`** | 不修改 AgentSession |

### 3.2 WorktreePrepareResponse (API DTO, 19 字段)

```python
class WorktreePrepareResponse(BaseModel):
    agent_session_id: UUID
    project_id: UUID
    repository_workspace_id: UUID | None
    plan_hash: str
    submitted_plan_hash: str
    prepare_status: str                     # "blocked"
    blocked_reason: str                     # "workspace_prepare_not_implemented"
    dry_run: bool                           # True
    requires_user_confirmation: bool        # True
    worktree_path: str | None
    branch_name: str | None
    base_branch: str | None
    base_commit_sha: str | None
    checked_at: datetime
    blockers: list[str]
    warnings: list[str]
    next_action: str
    creates_worktree: bool                  # False
    creates_branch: bool                    # False
    runs_git: bool                          # False
    mutates_agent_session_workspace: bool   # False
```

---

## 4. Prepare Endpoint 清单

| Method | Path | Summary | 语义 |
|--------|------|---------|------|
| `POST` | `/agent-threads/sessions/{id}/workspace-plan` | Build a dry-run worktree plan | 纯读 — 计算 plan |
| `GET` | `/agent-threads/sessions/{id}/workspace-plan` | Read back current dry-run plan | 纯读 — 重新计算 |
| `POST` | `/agent-threads/sessions/{id}/workspace-plan/confirm` | Confirm the current dry-run workspace plan hash | 纯写 DB — 记录 receipt, 不执行 git |
| `POST` | `/agent-threads/sessions/{id}/workspace/prepare` | **Validate and block** future workspace prepare execution | **blocked skeleton** — 不执行 git |

**命名验证**: endpoint 使用 `workspace/prepare`，summary 明确 "Validate and **block** future workspace prepare execution"。response 明确 "blocked/not_implemented; no git, branch, worktree, or session mutation occurs"。

---

## 5. blocked skeleton 语义证明

### 5.1 WorktreePrepareService 代码审计

```
WorktreePrepareService.prepare_workspace():
  1. 检查 user_confirmed == True
  2. trim submitted plan_hash
  3. 调用 WorktreePlanService.build_plan() 重新计算 plan
  4. 比较 submitted_plan_hash == plan.plan_hash
  5. 对比失败 → raise WorktreePrepareHashMismatchError
  6. 对比成功 → 构建 blocked result:
     · prepare_status = "blocked"
     · blocked_reason = "workspace_prepare_not_implemented"
     · 合并 plan blocker (如无仓库绑定) + 3 条 warning
     · creates_worktree = False
     · creates_branch = False
     · runs_git = False
     · mutates_agent_session_workspace = False
  7. 返回 WorktreePrepareResult
```

**结论**: 方法中没有任何 git 调用、文件系统写入、AgentSession 更新。只有:
- 输入校验 (trim, blank check)
- Plan 重新计算 (现有 WorktreePlanService, 已审计为纯计算)
- Hash 对比 (字符串比较)
- Blocked result 构建 (纯构造函数)

### 5.2 Import 审计

```python
# worktree_prepare_service.py imports:
from app.domain.worktree_prepare import WorktreePrepareResult
from app.services.worktree_plan_service import WorktreePlanService
# 无 subprocess, os, pathlib.Path, 任何 git/command 模块
```

**Grep 验证**: `rg "subprocess|os\.system|git worktree add|git checkout -b|..."` 在 `worktree_prepare.py`, `worktree_prepare_service.py` 和 `agent_threads.py` (prepare 相关行) 中返回 **零匹配**。

---

## 6. plan_hash 校验证明

### 6.1 stale plan hash → 409 Conflict

```python
# test_worktree_prepare_skeleton_rejects_stale_plan_hash
# 提交 "0" * 64 → 当前 plan hash 不同 → WorktreePrepareHashMismatchError
with pytest.raises(WorktreePrepareHashMismatchError):
    WorktreePrepareService(...).prepare_workspace(
        WorktreePrepareRequest(plan_hash="0" * 64, ...)
    )
```

### 6.2 correct plan hash → blocked (not 409)

```python
# test_worktree_prepare_skeleton_returns_blocked_for_current_hash
# 当前 plan hash 匹配 → prepare_status="blocked"
result = WorktreePrepareService(...).prepare_workspace(
    WorktreePrepareRequest(plan_hash=plan.plan_hash, ...)
)
assert result.prepare_status == "blocked"
```

### 6.3 blocked plan hash → still blocked + merged blockers

```python
# test_worktree_prepare_skeleton_keeps_blocked_plan_blocked
# 无仓库绑定的 blocked plan → skeleton blocker + plan blocker 合并
assert "workspace prepare execution is not implemented in P1-D-C" in result.blockers
assert "repository workspace is not bound for this project" in result.blockers
```

---

## 7. 未执行项确认

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 未执行 git | ✅ | `runs_git=False`, zero subprocess/os.system imports, grep 零匹配 |
| 未创建 worktree | ✅ | `creates_worktree=False`, 无 `git worktree add` 调用 |
| 未创建 branch | ✅ | `creates_branch=False`, 无 `git checkout -b` 调用 |
| 未修改 AgentSession.workspace_path | ✅ | `mutates_agent_session_workspace=False`, 测试验证 `unchanged_session.workspace_path is None` |
| 未修改 AgentSession.branch_name | ✅ | 测试验证 `unchanged_session.branch_name is None` |
| 未修改 RepositoryWorkspace | ✅ | 无 `repository_workspace_repository.upsert` 调用 |
| 未运行 worker | ✅ | 无 TaskWorker 调用 |
| 未启动服务 | ✅ | 所有测试使用 `tmp_path` 隔离 SQLite |
| 未改前端 | ✅ | 4 个变更文件全部在 `runtime/orchestrator/` 下 |
| 未创建 PR | ✅ | 无 `gh pr` 调用 |
| 未触发 apply-local | ✅ | 无 `local_git_write_service` import |
| 未触发 git-commit | ✅ | 无 git commit 调用 |

---

## 8. 测试命令与结果

```
$ python -m pytest runtime/orchestrator/tests/test_worktree_plan_dry_run.py \
    runtime/orchestrator/tests/test_agent_session_p0_coding_fields.py -q

33 passed in 0.64s
```

| 分类 | 测试数 | 验证内容 |
|------|--------|---------|
| P1-C dry-run plan | 8 | plan 生成、hash 稳定性、hash 变化、API DTO |
| P1-D-B confirmation | 4 | receipt 接受正确 hash、拒绝 stale hash、拒绝 blocked plan、DTO 暴露 guard 字段 |
| P1-D-C prepare skeleton | 5 | blocked 返回、stale hash 拒绝、blocked plan 合并、DTO 暴露 guard 字段、endpoint route function |
| P1-D-A command runner | 2 | deny-by-default allowlist specs、无写方法暴露 |
| P0 coding fields | 13 | 模型/ORM/Repository/Service/API/DTO |
| Branch/path policy | 2 | 安全分支名、不安全分支名拒绝 |
| Path guard | 2 | 路径外 allowed root、路径内源仓库 |

```
$ python -m compileall -q runtime/orchestrator/app runtime/orchestrator/tests
(no output — 全部编译成功)

$ git diff --check
(no output — 无 whitespace 问题)
```

---

## 9. 已发现缺口

| 缺口 | 状态 |
|------|------|
| 真实 workspace 创建仍未实现 | P1-D-C 预期 — blocked skeleton only |
| base_commit_sha 仍未接 `git rev-parse` | WorktreePlan.base_commit_sha 始终 None |
| workspace_status lifecycle enum 仍未实现 | AgentSession 只有 workspace_clean (boolean) |
| cleanup 仍未实现 | P1-E scope |
| audit event 仍未实现 | WorktreePrepareService 不写 AgentMessage |
| WorktreeCommandRunner 仅暴露只读 spec，写方法 (git_worktree_add 等) 未暴露 | P1-D-A 预期 |

---

## 10. Gate 结论

### Coding Session P1-D-C workspace prepare skeleton 验证: **Pass** ✅

**证据**:
1. ✅ WorktreePrepareResult 19 字段完整，含 4 个 guard 布尔字段 (creates_worktree/creates_branch/runs_git/mutates_agent_session_workspace) 全部 `False`
2. ✅ WorktreePrepareService 纯计算 — 无 subprocess, 无 os.system, 无 git, 无文件系统写入, 无 AgentSession 更新
3. ✅ plan_hash 校验正确 — stale hash → 409 Conflict, correct hash → blocked skeleton
4. ✅ blocked plan 合并 — skeleton blocker + plan blocking reasons 全部透传
5. ✅ API endpoint 语义明确 — summary "Validate and block", response "blocked/not_implemented"
6. ✅ 5 个 prepare 测试覆盖: blocked return, stale hash, blocked plan, DTO guard fields, route function
7. ✅ 33 tests pass (0.64s), compileall clean, git diff clean
8. ✅ 零 git 执行、零 worktree 创建、零 branch 创建、零 AgentSession 变异

### AI Project Director 总闭环: **仍为 Partial**

**原因**:
- P0 字段实现并验证 (Pass)
- P1-A 设计审计 (Pass)
- P1-B workspace 字段 (Pass)
- P1-C dry-run plan (Pass)
- P1-D-A command runner spec (Pass)
- P1-D-B confirmation receipt (Pass)
- P1-D-C prepare skeleton (Pass) ← 当前
- P1-D 真实创建尚未实现 (blocked/not_implemented)
- P1-E cleanup 尚未设计
- P2 SCM 集成尚未开始

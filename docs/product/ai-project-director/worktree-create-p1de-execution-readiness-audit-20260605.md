# Coding Session P1-D-E real worktree create execution readiness audit

> **文档类型**: 设计审计 / readiness audit
> **生成日期**: 2026-06-05
> **基准 commit (AI-Dev)**: `729ea90` (docs: verify worktree prepare p1dd2 preflight blockers)
> **参考项目 agent-orchestrator**: `c3eeecb`
> **前置文档**:
> - `docs/product/ai-project-director/worktree-create-p1d-readiness-audit-20260604.md`
> - `docs/product/ai-project-director/verification-worktree-prepare-p1dd2-preflight-blockers-20260605.md`
> **边界**: 只做设计审计，不改代码，不创建 worktree/branch
> **状态**: 设计审计完成

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator (15 个)

| 文件 | 当前关键状态 |
|------|------------|
| `app/domain/agent_session.py` | workspace_type (IN_PLACE), workspace_path, workspace_clean, branch_name, last_workspace_error — 全部 nullable |
| `app/repositories/agent_session_repository.py` | update_status 支持所有 workspace 字段 |
| `app/services/worktree_command_runner.py` | 5 只读 spec, `_ensure_read_only_allowlisted()` 拒绝 mutates_repository=True |
| `app/domain/worktree_plan.py` | plan_hash 稳定, dry_run=True, requires_user_confirmation=True |
| `app/domain/worktree_plan_confirmation.py` | confirmation receipt, confirmation_scope=workspace_plan_dry_run |
| `app/domain/worktree_prepare.py` | WorktreeGitPreflight (10 字段), WorktreePrepareResult (runs_git/runs_write_git) |
| `app/services/worktree_plan_service.py` | build_plan + plan_hash 计算 |
| `app/services/worktree_plan_confirmation_service.py` | confirm_plan 非持久化 receipt |
| `app/services/worktree_prepare_service.py` | 9 blockers, read-only preflight 执行 |
| `app/services/worktree_git_preflight_service.py` | 5 只读命令 preflight |
| `app/api/routes/agent_threads.py` | workspace-plan, workspace-plan/confirm, workspace/prepare |
| `app/core/db_tables.py` | workspace_type/path/clean + last_workspace_error columns |
| `app/core/db.py` | get_db_session |
| `tests/test_worktree_plan_dry_run.py` | 39 tests pass |
| `tests/test_agent_session_p0_coding_fields.py` | 13 tests pass |

### Agent Orchestrator (8 个)

| 文件 | 参考要点 |
|------|---------|
| `README.md` | 项目概览 |
| `ARCHITECTURE.md` | hash-based 目录结构, worktree 布局 |
| `docs/PLUGIN_SPEC.md` | Workspace interface 契约 |
| `packages/core/src/types.ts` | WorkspaceCreateConfig, WorkspaceInfo, CleanupStack |
| `packages/plugins/workspace-worktree/src/index.ts` | `git worktree add --detach` + `git checkout -b` |
| `packages/core/src/session-manager.ts` | spawn → workspace.create → runtime.create |
| `packages/core/src/lifecycle-manager.ts` | readWorkspaceBranch |
| `packages/core/src/lifecycle-state.ts` | CanonicalSessionLifecycle |

---

## 1. 当前已具备的安全前置条件

| 条件 | 层 | 状态 |
|------|-----|------|
| WorktreePlan 生成 + plan_hash | P1-C | ✅ 稳定 hash, dry_run=True |
| BranchNamePolicy (安全分支名) | P1-C | ✅ 确定性, 无 shell 注入 |
| WorktreeGuardService (路径安全) | P1-C | ✅ 绝对路径, allowed root 内, 源仓库隔离 |
| plan_hash 验证 (stale plan 拒绝) | P1-D-C | ✅ stale → 409 Conflict |
| confirmation receipt (非持久化) | P1-D-B | ✅ confirmation_scope=workspace_plan_dry_run |
| prepare skeleton (blocked) | P1-D-C | ✅ prepare_status=blocked |
| read-only git preflight | P1-D-D | ✅ 5 只读命令, 获取 HEAD SHA, dirty/clean, branch exists, worktree registered |
| repository_is_git_worktree blocker | P1-D-D-2 | ✅ 非 git worktree → blocker |
| repository_clean blocker | P1-D-D-2 | ✅ dirty repo → blocker |
| planned_branch_exists blocker | P1-D-D-2 | ✅ 已有 branch → blocker |
| planned_worktree_registered blocker | P1-D-D-2 | ✅ 已有 worktree → blocker |
| 9 blocker 总集 | P1-D-D-2 | ✅ 全覆盖 |

**当前 AgentSession 已准备好的字段**:

| 字段 | 当前值 | 创建后写入 |
|------|--------|----------|
| `workspace_type` | `IN_PLACE` | → `WORKTREE` |
| `workspace_path` | `None` | → created path |
| `workspace_clean` | `None` | → `True` |
| `branch_name` | `None` | → created branch |
| `last_workspace_error` | `None` | → `None` (成功) / error message (失败) |

---

## 2. P1-D-E 最小真实创建目标

### 2.1 要做的

```
1. 创建一个 git worktree (隔离工作区)
2. 在新 worktree 中创建一个 session 分支
3. 写回 AgentSession 5 个 workspace 字段
4. 写 AgentMessage timeline event (审计)
```

### 2.2 不做的

```
不 git add / git commit / git push / gh pr create
不 merge / rebase
不 apply-local
不运行 Worker
不运行 AI runtime (不启动 Claude Code / Codex)
不修改主仓库 working tree / HEAD / index
不修改任何源文件
```

---

## 3. 推荐 Git 命令顺序

### 方案 A: 两步法 (参考 agent-orchestrator)

```bash
# Step 1: 基于 HEAD 创建 detached worktree
git worktree add --detach <worktree_path> HEAD
# Step 2: 在新 worktree 中创建分支
git -C <worktree_path> switch -c <branch_name>
```

**优点**: 两步分离, 每步失败可单独回滚
**缺点**: 两步操作, 中间失败需要更复杂的 rollback

### 方案 B: 一步法

```bash
# 一步创建 worktree + 分支
git worktree add -b <branch_name> <worktree_path> HEAD
```

**优点**: 单步原子操作, git 内部处理 rollback
**缺点**: 错误信息不够精细

### 推荐: 方案 B (一步法)

**原因**:
1. 原子性: `git worktree add -b` 要么成功 (worktree + branch 都有), 要么失败 (都没有)
2. 回滚简单: 失败后不需要清理中间状态
3. agent-orchestrator 的 `workspace-worktree` 插件在实践中证明了可靠性
4. 不需要两步法分别处理分支名冲突和路径冲突

### 3.1 完整 Git 命令序列

```python
# P1-D-E 真实创建序列:

# 1. 重新生成 WorktreePlan (verify plan hasn't changed)
plan = worktree_plan_service.build_plan(agent_session_id=...)

# 2. 验证 plan_hash 匹配请求中的 hash
assert plan.plan_hash == request.plan_hash

# 3. 重新执行 read-only preflight (verify no new blockers)
preflight = git_preflight_service.run_preflight(...)
assert preflight errors are empty
assert preflight.repository_clean is True
assert preflight.planned_branch_exists is False
assert preflight.planned_worktree_registered is False

# 4. 验证 blockers 仅剩 "not implemented" 一个 (执行阶段移除该 blocker)
# 5. 执行: git worktree add -b <branch_name> <worktree_path> HEAD
# 6. 写回 AgentSession workspace 字段
```

---

## 4. WorktreeCommandRunner 扩展策略

### 4.1 当前状态

`WorktreeCommandRunner` 的 `_ensure_read_only_allowlisted()` 硬编码了 5 个只读 spec, 且拒绝任何 `mutates_repository=True` 的 spec。

### 4.2 建议: 新增独立 `WorktreeWriteCommandRunner`

```python
class WorktreeWriteCommandRunner:
    """Deny-by-default command runner for worktree write operations.

    Separated from the read-only runner so that the allowlist boundary is
    enforced at the type level: services that import this class intend to
    write.  The read-only WorktreeCommandRunner remains untouched.
    """

    def __init__(self, *, default_timeout_seconds: int = 120) -> None: ...

    # Write allowlist (deny-by-default):
    def git_worktree_add_b(self, *, repository_path: str, branch_name: str, worktree_path: str, ref: str = "HEAD") -> WorktreeCommandSpec: ...
    def git_worktree_remove(self, *, worktree_path: str) -> WorktreeCommandSpec: ...
    def git_branch_delete(self, *, repository_path: str, branch_name: str) -> WorktreeCommandSpec: ...

    def run(self, spec: WorktreeCommandSpec) -> WorktreeCommandResult:
        # 复用 subprocess.run(...) 逻辑, 但检查 mutates_repository 必须为 True
        ...
```

### 4.3 为什么不扩展 `WorktreeCommandRunner`

1. **类型安全**: 分离后, `worktree_git_preflight_service.py` 只能 import read-only runner, 无法误调用写命令
2. **代码审计**: grep `WorktreeWriteCommandRunner` 即可显示所有写调用, 无需检查 allowlist 内部
3. **测试隔离**: 写 runner 的测试需要真实 `.git` 目录, 只读 runner 可以用 Fake

### 4.4 Recommandation

P1-D-E 第一版使用独立 `WorktreeWriteCommandRunner`。`WorktreeCommandRunner` (只读) 保持不变。

---

## 5. 用户确认与 plan_hash 流程

### 5.1 当前 confirmation receipt

`WorktreePlanConfirmationService.confirm_plan()` 返回 `WorktreePlanConfirmationReceipt` — 纯内存对象, 不持久化。

字段: `plan_hash`, `confirmed_plan_hash`, `confirmation_status="confirmed"`, `confirmation_scope="workspace_plan_dry_run"`, `confirmated_at`, `creates_worktree=False`, etc.

### 5.2 P1-D-E 是否需要持久化确认

**不需要。** P1-D-E 通过以下方式验证用户已确认:

1. API POST `/workspace/create` 的请求体包含:
   ```json
   { "plan_hash": "...", "user_confirmed": true }
   ```

2. 后端验证 `user_confirmed=True` (与 prepare 相同的逻辑)

3. 后端验证 `plan_hash` 匹配当前 plan (防止 stale plan 被执行)

4. 不需要持久化 confirmation receipt — 因为:
   - 每一次 create 调用都重新验证 plan_hash (实时)
   - create 成功后写入 AgentMessage timeline (审计记录)
   - 不需要 "先确认, 后执行" 的两阶段持久化

### 5.3 plan_hash 变化处理

如果用户在 step 1 (GET workspace-plan) 和 step 2 (POST workspace/create) 之间仓库状态发生了变化 (如仓库被 force push), plan_hash 会变, 后端拒绝创建 → 409 Conflict → 用户必须重新 plan → 重新 preflight → 重新确认。

---

## 6. API 设计建议

### 6.1 推荐命名

```
POST /agent-threads/sessions/{session_id}/workspace
  summary: "Create a per-session worktree and branch from a confirmed dry-run plan"
```

### 6.2 请求体

```python
class WorktreeCreateRequestBody(BaseModel):
    plan_hash: str = Field(min_length=64, max_length=64)
    user_confirmed: bool = True
```

### 6.3 响应体

```python
class WorktreeCreateResponse(BaseModel):
    agent_session_id: UUID
    project_id: UUID
    workspace_type: str           # "worktree" on success
    workspace_path: str           # created path
    branch_name: str              # created branch
    base_branch: str              # baseline branch
    workspace_clean: bool         # True (new worktree)
    created_at: datetime          # creation timestamp
```

### 6.4 错误边界

| 场景 | HTTP 状态 | detail |
|------|----------|--------|
| plan_hash 不匹配 | 409 | "submitted plan_hash does not match current workspace plan" |
| user_confirmed=False | 422 | "workspace create requires explicit user_confirmed=true" |
| preflight 失败 (has blockers) | 422 | "cannot create workspace: ...blockers..." |
| workspace 已存在 (幂等) | 200 | 返回当前 AgentSession workspace 字段 (已创建) |
| git worktree add 失败 | 500 | "workspace creation failed: ...error..." |
| AgentSession 不存在 | 404 | "Agent session not found: {id}" |

### 6.5 防误触

1. 使用 `POST /workspace` (动词) 而不是 `.../prepare` (检查) — 语义明确
2. 要求 `user_confirmed=True` 显式传入
3. 返回 `201 Created` (新建) 或 `200 OK` (已存在, 幂等)
4. 响应体明确包含 `workspace_path` 和 `branch_name` — 用户看到后知道已创建

---

## 7. 失败与回滚策略

### 7.1 完整创建流程与回滚矩阵

```
Step 1: 重新生成 WorktreePlan
  Failure → 500 "plan generation failed"

Step 2: plan_hash 验证
  Failure → 409 "plan has changed"

Step 3: 重新执行 read-only preflight
  Failure → 422 "preflight failed: ...blockers..."

Step 4: 执行 git worktree add -b <name> <path> HEAD
  Success → cleanup_actions = [("worktree_remove", path), ("branch_delete", name)]
  Failure (timeout) → 500 "git timed out"
  Failure (exit code != 0) → 500 "git worktree add -b failed: ...stderr..."

Step 5: 写回 AgentSession:
    workspace_type = WORKTREE
    workspace_path = <path>
    workspace_clean = True
    branch_name = <name>
    last_workspace_error = None
  Failure (DB error) → git worktree remove <path> → 500 "db write failed after creation"

Step 6: 写 AgentMessage timeline event
  Failure → non-fatal (warning log), 不回滚 worktree

Step 7: 返回 201 Created
```

### 7.2 幂等设计

```python
def create_workspace(session_id, plan_hash, user_confirmed):
    session = agent_session_repository.get_by_id(session_id)

    # Idempotency: 如果 workspace_path 已有值, 直接返回
    if session.workspace_path is not None:
        return 200 + session workspace fields

    # ... 验证 plan_hash, preflight, git create, write back ...
```

### 7.3 安全约束

- `git worktree add -b` 只能用于 allowed_workspace_root/.aido-worktrees/ 下
- branch 名通过 BranchNamePolicy.generate() 生成 (已验证安全)
- `HEAD` 作为 ref (不引外部不可信 ref)

---

## 8. AgentSession 写回策略

### 8.1 写入字段 (创建成功)

| 字段 | 写入值 | 原因 |
|------|--------|------|
| `workspace_type` | `WORKTREE` | 从 `IN_PLACE` 变为 `WORKTREE` |
| `workspace_path` | created path | 真实路径 |
| `workspace_clean` | `True` | 新 worktree 无修改 |
| `branch_name` | created branch | session/proj-xxx-xxx |
| `last_workspace_error` | `None` | 成功时清空 |

### 8.2 写入字段 (创建失败)

| 字段 | 写入值 |
|------|--------|
| `last_workspace_error` | 详细错误信息 (截断 2000 字符) |

### 8.3 不需要新增的字段

| 字段 | 原因 |
|------|------|
| `workspace_status` (enum) | P1-D-E 当前用 `workspace_clean` boolean + `last_workspace_error` 足够表达状态 |
| `worktree_created_at` | 可从 AgentSession.updated_at 推导 |
| `base_commit_sha` | 已在 WorktreeGitPreflight.repository_head_sha 中, 不需要复制到 AgentSession |

---

## 9. 审计记录策略

### 9.1 推荐: AgentMessage timeline event

复用 `AgentConversationService._append_message()`:

```python
# 创建成功
event_type = "workspace_created"
content_summary = f"Worktree created at {path}, branch {branch}"
content_detail = f"plan_hash={plan_hash}, base_ref=HEAD"

# 创建失败
event_type = "workspace_create_failed"
content_summary = f"Failed: {error}"
content_detail = f"plan_hash={plan_hash}"
```

### 9.2 不推荐的方案

| 方案 | 原因 |
|------|------|
| 独立 WorkspaceOperationLog 表 | 过度设计, P1-E cleanup 可以用 message |
| Run event | workspace 操作不属于 Run 生命周期 |
| 纯内存 receipt | 不留痕迹, 不可追溯 |

---

## 10. 第一条 Codex 实现任务建议

### 建议: 新增 WorktreeWriteCommandRunner + WorktreeCreateService skeleton

```
任务: 新增 WorktreeWriteCommandRunner + WorktreeCreateService blocked skeleton

范围:
  1. 新增 WorktreeWriteCommandRunner:
     · git_worktree_add_b() → WorktreeCommandSpec (mutates_repository=True)
     · git_worktree_remove() → WorktreeCommandSpec (mutates_repository=True)
     · git_branch_delete() → WorktreeCommandSpec (mutates_repository=True)
     · run(spec) → WorktreeCommandResult (复用 subprocess.run, check=False)
     · _ensure_allowed() 检查 spec.mutates_repository is True +
       argv 精确匹配 allowlist
     · 不接 WorktreeCreateService

  2. 新增 WorktreeCreateService blocked skeleton:
     · 接收 plan_hash + user_confirmed
     · 重新生成 plan + 验证 hash
     · 重新执行 preflight
     · 返回 blocked result (not_implemented, creates_worktree=False)
     · 不实际创建 worktree

  3. 新增 WorktreeCreateResponse DTO (agent_threads.py)

  4. 新增 API POST /agent-threads/sessions/{id}/workspace
     · 返回 blocked skeleton (类似 prepare 的 skeleton 模式)
     · response: creates_worktree=False, runs_write_git=False

  5. 测试:
     · WorktreeWriteCommandRunner allowlist 验证
     · Write spec mutates_repository 必须为 True
     · Write runner 不运行 (spec only)
     · WorktreeCreateService blocked skeleton

边界:
  - 不创建 worktree
  - 不创建 branch
  - 不执行 git write (write runner 只有 spec 方法, 不调用 run)
  - 不改 AgentSession
  - 不新增 DB 表
  - 不改前端

验收: pytest 新测试
```

### 为什么选这个

1. **最小增量**: Write runner 只是 spec 构建器, 不执行 git
2. **安全渐进**: blocked skeleton 模式已验证安全 (P1-D-C prepare 先例)
3. **API shape 先定义**: 在真实 git 操作前, API 接口和响应结构先确定
4. **与已有基础设施兼容**: 复用 WorktreePlanService, WorktreeGitPreflightService

---

## 11. 明确不建议现在做的事

| 不建议 | 原因 |
|--------|------|
| 接 Claude Code / Codex runtime | P1 只做 worktree 基础设施 |
| 让 AI 进 worktree 改代码 | P2+ scope |
| 自动 apply patch | P2+ scope |
| 自动 git commit | P2+ scope |
| git push / gh pr create | P2 scope |
| 接 CI | P2 scope |
| cleanup 自动删除 | P1-E scope |
| 大规模重构前端 | P1 是后端基础设施 |
| 把 AI Project Director 总闭环标记为 Pass | 总闭环仍为 Partial |

---

## 12. 总结

### 当前已具备条件

| 条件 | 状态 |
|------|------|
| WorktreePlan dry-run + plan_hash | ✅ |
| BranchNamePolicy | ✅ |
| WorktreeGuardService | ✅ |
| plan_hash 验证 (stale 拒绝) | ✅ |
| confirmation receipt | ✅ |
| read-only git preflight (5 specs) | ✅ |
| 9 blocker 全覆盖 | ✅ |
| AgentSession workspace 字段 | ✅ |
| AgentSessionRepository workspace CRUD | ✅ |
| API: workspace-plan, /confirm, /prepare | ✅ |

### 当前仍缺口

| 缺口 | P |
|------|---|
| WorktreeWriteCommandRunner | P1-D-E |
| WorktreeCreateService | P1-D-E |
| API POST /workspace | P1-D-E |
| 真实 git worktree add 执行 | P1-D-E |
| 幂等 guard | P1-D-E |
| AgentMessage timeline 记录 | P1-D-E |

### 推荐真实创建最小路线

1. **P1-D-E-A**: WorktreeWriteCommandRunner + WorktreeCreateService blocked skeleton (本次建议)
2. **P1-D-E-B**: Feature-flag guarded real git write execution + API

### 下一条建议给 Codex 的最小任务

**P1-D-E-A**: `WorktreeWriteCommandRunner` + `WorktreeCreateService` blocked skeleton。纯新增, 不执行 git write, 不创建 worktree。API shape 先于实现。

### Gate 结论

- **Coding Session P1-D-E real worktree create readiness audit**: **Pass** ✅
- **AI Project Director 总闭环**: **仍为 Partial**

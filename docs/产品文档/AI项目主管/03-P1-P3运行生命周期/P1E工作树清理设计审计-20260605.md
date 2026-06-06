# Coding Session P1-E cleanup / rollback 设计审计

> **文档类型**: 设计审计 / readiness audit
> **生成日期**: 2026-06-05
> **基准 commit (AI-Dev)**: `78f7fe6` (docs: verify worktree create p1deb real create)
> **参考项目 agent-orchestrator**: `c3eeecb`
> **前置文档**:
> - `docs/product/ai-project-director/verification-worktree-create-p1deb-real-create-20260605.md`
> - `docs/product/ai-project-director/worktree-create-p1de-execution-readiness-audit-20260605.md`
> - `docs/product/ai-project-director/verification-worktree-create-p1dea-blocked-skeleton-20260605.md`
> - `docs/product/ai-project-director/verification-worktree-prepare-p1dd2-preflight-blockers-20260605.md`
> - `docs/product/ai-project-director/coding-session-lifecycle-design-20260604.md`
> **边界**: 只做设计审计，不改代码，不创建/删除 worktree/branch
> **状态**: 设计审计完成

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator (10 个)

| 文件 | 用途 |
|------|------|
| `app/domain/worktree_create.py` | WorktreeWriteCommandPreview + WorktreeCreateResult (3 factory methods) |
| `app/services/worktree_write_command_runner.py` | 唯一 allowlisted 写命令: `git worktree add -b` |
| `app/services/worktree_create_service.py` | 17-guard 链 + 真实 worktree 创建 + AgentSession 写回 |
| `app/services/worktree_git_preflight_service.py` | 5 只读 preflight 命令 |
| `app/services/worktree_plan_service.py` | BranchNamePolicy + WorktreeGuardService + WorktreePlanService |
| `app/domain/agent_session.py` | WorkspaceType (IN_PLACE/WORKTREE) + 10 workspace/branch/error 字段 |
| `app/repositories/agent_session_repository.py` | update_status 支持所有 workspace 字段 |
| `app/api/routes/agent_threads.py` | POST /workspace/create endpoint |
| `tests/test_worktree_plan_dry_run.py` | 47 tests pass (含 11 create 测试) |
| `tests/test_agent_session_p0_coding_fields.py` | 13 P0 字段测试 |

### Agent Orchestrator (8 个)

| 文件 | 参考要点 |
|------|---------|
| `README.md` | `autoCleanupOnMerge`, PR merge → cleanup |
| `ARCHITECTURE.md` | hash-based 目录结构, worktree 布局, archive 目录 |
| `docs/PLUGIN_SPEC.md` | Workspace interface 契约: `create()`, `destroy()`, `list()` |
| `packages/core/src/types.ts` | Workspace, CleanupResult, KillResult, Session 接口 |
| `packages/plugins/workspace-worktree/src/index.ts` | `destroy()`: git worktree remove --force; 不删 branch; fallback rmSync |
| `packages/core/src/session-manager.ts` | `kill()` → runtime.destroy → workspace.destroy → lifecycle terminated; `cleanup()` |
| `packages/core/src/lifecycle-manager.ts` | auto-cleanup on merge; lifecycle polling |
| `packages/core/src/lifecycle-state.ts` | CanonicalSessionLifecycle; `"cleanup"` status |

---

## 1. 当前 P1-D-E-B 已具备什么

| 能力 | 状态 | 代码位置 |
|------|------|----------|
| real `git worktree add -b` 执行 | ✅ | `worktree_write_command_runner.py:44-70` |
| per-AgentSession worktree 创建 | ✅ | `worktree_create_service.py:151` |
| per-AgentSession branch 创建 | ✅ | 同一 `git worktree add -b` 原子操作 |
| AgentSession workspace 字段写回 (5 字段) | ✅ | `worktree_create_service.py:171-178` |
| last_workspace_error 成功清空 / 失败写入 | ✅ | L177: None on success; L207-213: error on failure |
| 0-guard 链 (plan_hash + user_confirmed + preflight) | ✅ | 17-guard in `create_workspace()` |
| **当前明确没有 cleanup** | ❌ | 无 worktree remove / branch delete / AgentSession 回退字段 |
| **当前明确没有 回滚** | ❌ | 无 CleanupStack / rollback 机制 |

---

## 2. 为什么 cleanup / rollback 必须先做

### 2.1 worktree 和 branch 的持久性

`git worktree add -b` 创建的 worktree 目录和 branch ref 是**持久资源**:

- worktree 目录会长期留在磁盘，占用空间
- branch 会长期留在 repo refs (`refs/heads/session/*`)
- 多次 create 会产生累积垃圾 (如测试多次运行)
- **当前没有任何自动清理机制**

### 2.2 AI runtime 接入前的安全障碍

在 AI runtime (Claude Code / Codex) 进入 worktree 改代码之前，必须确保:

1. **可以安全清理失败的 worktree** — 如果 create 成功但 AgentSession 写回失败，worktree 会成为孤立资源
2. **可以清理已完成的 session worktree** — coding session 完成后，worktree 不再需要
3. **可以回滚部分成功的 create** — 如果 git worktree add 成功但后续步骤失败

### 2.3 不能依赖人工 rm -rf

| 人工做法 | 风险 |
|---------|------|
| `rm -rf <worktree_path>` | 不更新 git worktree 注册表 → `git worktree list` 仍显示 stale entry |
| `git branch -D <branch>` | 如果 branch 被其他 worktree 使用 → 数据丢失 |
| `git worktree remove <path>` | 需要知道正确路径 → 人工易出错 |
| 不清理 | 磁盘空间浪费 + `git worktree list` 膨胀 + session branch 累积 |

---

## 3. cleanup 最小目标

### 3.1 P1-E 只做

| 操作 | 说明 |
|------|------|
| 删除系统创建的 worktree (`git worktree remove`) | 仅限 `workspace_path` 在 `allowed_workspace_root` 下 |
| 可选删除系统创建的 session branch (`git branch -d`) | 默认不自动删 branch (参考 agent-orchestrator 的设计选择) |
| 写回 AgentSession workspace 字段 | workspace_type → IN_PLACE, workspace_path → None, workspace_clean → None |
| 写回 cleanup 状态 / last_workspace_error | 成功或失败信息 |
| 记录 AgentMessage timeline event | 审计记录 |

### 3.2 P1-E 不做

| 禁止操作 | 原因 |
|---------|------|
| 不删除主仓库 | 路径 guard |
| 不删除非系统创建路径 | 路径必须在 `allowed_workspace_root` 下 |
| 不删除含未提交修改的 worktree (默认) | `force=false` 默认 blocked |
| 不 `git push` | 不涉及 remote |
| 不 `rm -rf` | git 命令优先 |
| 不 `git branch -D` (force delete) | P1-E 只用 `git branch -d` (safe delete) |

---

## 4. 必须设计的安全 guard

### 4.1 cleanup guard 链

```
cleanup_workspace():
  1. AgentSession.workspace_type 必须是 WORKTREE → 否则 blocked
  2. AgentSession.workspace_path 必须非空且在 allowed_workspace_root 下 → 否则 blocked
  3. workspace_path 不能等于 repository root → 否则 blocked
  4. workspace_path 不能包含 repository root → 否则 blocked
  5. workspace_path 必须在 git worktree list 中注册 → 否则 warning (可能已 orphan)
  6. workspace_path 必须在磁盘存在 → 否则 idempotent skip (已清理)
  7. worktree 必须 clean (git status --porcelain 空) → 否则 blocked (force=false)
  8. branch_name 必须匹配 session/* pattern → 否则仅删 worktree 不删 branch
  9. branch 不能被其他 worktree 使用 → 否则仅删 worktree 不删 branch
  10. branch 必须是 session branch → 否则不删 branch
```

### 4.2 guard 详细规则表

| # | Guard | 触发条件 | 拒绝行为 |
|---|-------|---------|---------|
| 1 | workspace_type != WORKTREE | IN_PLACE / READ_ONLY / CLONE | blocked: "session is not in a worktree" |
| 2 | workspace_path is None | 从未创建 | 404: "no workspace to clean up" |
| 3 | workspace_path 不在 allowed_root 下 | 路径越界 | blocked: "path outside allowed root" |
| 4 | workspace_path == repo root | 危险路径 | blocked: "cannot remove repository root" |
| 5 | workspace_path 包含 repo root | 反向嵌套 | blocked: "path contains repository" |
| 6 | worktree 未在 git worktree list 中 | 已 orphan | warning → 仅清理目录 + AgentSession 字段，不执行 git worktree remove |
| 7 | worktree 不 clean (dirty) | 未提交修改 | blocked (force=false): "worktree has uncommitted changes" |
| 8 | force=true + dirty | 用户授权 | 允许删除但写 warning event |
| 9 | branch_name 不匹配 session/* | 非系统 branch | 仅删 worktree，不删 branch |
| 10 | branch 被其他 worktree 使用 | 共享 branch | 仅删 worktree，不删 branch |

### 4.3 path safety guard (复用现有 WorktreeGuardService)

```python
# 复用现有 guard，反向验证：
# - worktree_path 必须在 allowed_workspace_root 下
# - worktree_path 不能是 repository root
# - worktree_path 不能包含 repository root
# - worktree_path 必须是绝对路径
```

### 4.4 agent-orchestrator 参考: 不删 branch 的设计选择

agent-orchestrator `workspace-worktree` 的 `destroy()` 明确说明:

```typescript
// packages/plugins/workspace-worktree/src/index.ts L466-470
// NOTE: We intentionally do NOT delete the branch here. The worktree
// removal is sufficient. Auto-deleting branches risks removing
// pre-existing local branches unrelated to this workspace (any branch
// containing "/" would have been deleted).
```

**建议 AI-Dev P1-E 跟随此设计**: 默认 cleanup 只删 worktree，不删 branch。branch 清理留到后续 `git branch --merged` 批量清理阶段。

---

## 5. cleanup Git 命令边界

### 5.1 允许设计但不实现的命令

| 命令 | 用途 | 安全条件 |
|------|------|---------|
| `git worktree list --porcelain` | 验证 worktree 注册状态 | 只读 |
| `git status --porcelain` | 验证 worktree clean | 只读 |
| `git worktree remove <path>` | 删除 worktree 注册 + 目录 | 默认 `--force` 仅在 P1-E 可控范围内 |
| `git branch -d <branch>` | 安全删除已合并 branch | git 内置安全: 拒绝删除未合并 branch |
| `git worktree prune` | 清理 stale worktree 注册 | 只清理已删除目录的注册 |

### 5.2 必须禁止的命令

| 禁止命令 | 原因 |
|---------|------|
| `rm -rf <path>` | 绕过 git worktree 注册表，导致 stale entry |
| `git clean -fd` | 删除 untracked files，可能丢用户数据 |
| `git reset --hard` | 可能丢提交 |
| `git push` | 不涉及 remote |
| `git rebase` | 不涉及 |
| `git merge` | 不涉及 |
| `git branch -D` (force) | P1-E 只允许 `-d` (safe)；`-D` 需后续阶段 |
| 删除任意目录 | 仅限 `workspace_path` 匹配路径 |
| 删除非 session branch | branch_name 必须通过 BranchNamePolicy 验证 |

---

## 6. cleanup service 设计

### 6.1 是否需要独立组件

| 组件 | 需要? | 说明 |
|------|-------|------|
| `WorktreeCleanupService` | **是** | 核心 orchestration: guard 检查 + git 执行 + AgentSession 写回 |
| `WorktreeWriteCommandRunner` 扩展 | **是** | 在现有 write runner 上增加 `git_worktree_remove()` + `git_branch_delete_safe()` |
| `WorktreeCleanupResult` (domain) | **是** | 类似 WorktreeCreateResult: 返回 cleanup 状态 + guard 字段 |
| `CleanupGuardService` | **不需要** | guard 逻辑内联在 CleanupService 中；WorktreeGuardService 已有 path guard |
| `CleanupStack` (rollback) | **P1-E 暂不需要** | 当前 create 是单步 git 操作；rollback 可在 create 失败后手动调用 cleanup |
| `AgentMessage` audit event | **是** | 复用 AgentConversationService._append_message() |

### 6.2 WorktreeCleanupService

```
输入:
  - agent_session_id: UUID
  - user_confirmed: bool = True
  - force: bool = False  (默认不强制)
  - delete_branch: bool = False  (默认不删 branch)

输出:
  - WorktreeCleanupResult:
      cleanup_status: "cleaned" | "blocked" | "partial" | "failed"
      removed_worktree: bool
      removed_branch: bool
      writes_agent_session: bool
      removes_worktree_directory: bool
      removes_branch_ref: bool
      last_workspace_error: str | None
      blockers: list[str]
      warnings: list[str]

执行:
  1. fetch AgentSession
  2. validate guards (10 项)
  3. git worktree remove <path> (非 force 时只对 clean worktree)
  4. 可选: git branch -d <branch> (仅 session/* branch 且无其他 worktree 使用)
  5. write AgentSession: workspace_type=IN_PLACE, workspace_path=None, ...
  6. write AgentMessage timeline
```

### 6.3 WorktreeWriteCommandRunner 扩展

在现有 `WorktreeWriteCommandRunner` 上增加两个 spec 方法:

```python
class WorktreeWriteCommandRunner:
    # 现有:
    def git_worktree_add_new_branch(...) -> WorktreeWriteCommandPreview  # 已有
    def run(preview) -> WorktreeCommandResult                              # 已有

    # P1-E 新增:
    def git_worktree_remove(self, *, worktree_path: str) -> WorktreeWriteCommandPreview
        """git worktree remove <worktree_path>"""

    def git_branch_delete_safe(self, *, repository_path: str, branch_name: str) -> WorktreeWriteCommandPreview
        """git branch -d <branch_name>  (safe delete, not -D)"""
```

`_ensure_write_allowlisted()` 需要扩展 allowlist:

```python
# 新增 allowlisted command_kind:
# - "git_worktree_remove"       → argv: ("git", "worktree", "remove", worktree_path)
# - "git_branch_delete_safe"    → argv: ("git", "branch", "-d", branch_name)
```

**必须的安全检查**:
- `git_worktree_remove`: validate worktree_path is absolute, not repo root, under allowed root
- `git_branch_delete_safe`: validate branch_name matches `session/*`, no "-" prefix

### 6.4 WorktreeCleanupResult domain model

```python
class WorktreeCleanupResult(DomainModel):
    agent_session_id: UUID
    project_id: UUID
    cleanup_status: str                    # "cleaned" | "blocked" | "partial" | "failed"
    blocked_reason: str | None
    removed_worktree: bool                 # git worktree remove 成功
    removed_branch: bool                   # git branch -d 成功
    worktree_was_registered: bool          # worktree 在 git worktree list 中
    worktree_was_clean: bool | None        # git status --porcelain 结果
    worktree_path: str | None              # 被清理的路径
    branch_name: str | None                # 被删除的分支
    writes_agent_session: bool             # AgentSession 字段被重置
    blockers: list[str]
    warnings: list[str]
    next_action: str
```

---

## 7. AgentSession 字段策略

### 7.1 当前已有字段 (可复用)

| 字段 | cleanup 后写入值 |
|------|-----------------|
| `workspace_type` | `IN_PLACE` (回退到默认) |
| `workspace_path` | `None` |
| `workspace_clean` | `None` |
| `branch_name` | `None` (或保留，参考 agent-orchestrator) |
| `last_workspace_error` | cleanup 失败时写入错误 |

### 7.2 是否需要新增字段

| 候选字段 | 需要? | 建议 |
|---------|-------|------|
| `cleanup_status` | **不需要** | AgentSession 已有 `workspace_type`/`workspace_path` 足够推导状态: path=None → cleaned |
| `cleanup_error` | **不需要** | 复用 `last_workspace_error` |
| `cleaned_at` | **不需要** | 可从 `AgentSession.updated_at` 推导 |
| `worktree_created_at` | **不需要** | 可从 Audit Message timeline 推导 |
| `workspace_status` (enum) | **不需要** | 当前用 `workspace_clean` boolean + `last_workspace_error` 足够 |
| `workspace_owner` | **不需要** | AgentSession.id 已是 owner |
| `workspace_operation_id` | **不需要** | 过度设计 |

### 7.3 最小建议

**P1-E-A blocked skeleton 阶段: 只复用现有字段，不新增任何 DB column。**

- cleanup 成功: `workspace_type=IN_PLACE`, `workspace_path=None`, `workspace_clean=None`, `last_workspace_error=None`
- cleanup 失败: `last_workspace_error` 写入失败原因
- branch_name: 保留不变或设为 None (取决于设计选择 — 建议保留，参考 agent-orchestrator)

---

## 8. API 设计建议

### 8.1 推荐 endpoint

```
POST /agent-threads/sessions/{session_id}/workspace/cleanup
```

**理由**:
- `POST` 动词表示 action，语义明确
- `cleanup` 后缀表明这是清理操作（非 create/prepare/plan）
- 不容易误触: 必须显式调用

**不推荐**:
- `DELETE /workspace` — REST DELETE 语义暗示资源删除，但 workspace 不是独立资源，容易和 AgentSession 删除混淆

### 8.2 请求体

```python
class WorktreeCleanupRequestBody(BaseModel):
    user_confirmed: bool = True           # 必须显式确认
    force: bool = False                   # 默认不强制；True 时允许删 dirty worktree
    delete_branch: bool = False           # 默认不删 branch
```

### 8.3 响应体

```python
class WorktreeCleanupResponse(BaseModel):
    agent_session_id: UUID
    project_id: UUID
    cleanup_status: str                   # "cleaned" | "blocked" | "partial" | "failed"
    blocked_reason: str | None
    removed_worktree: bool
    removed_branch: bool
    worktree_was_registered: bool
    worktree_was_clean: bool | None
    worktree_path: str | None
    branch_name: str | None
    writes_agent_session: bool
    blockers: list[str]
    warnings: list[str]
    next_action: str
```

### 8.4 HTTP 状态边界

| 场景 | HTTP 状态 | detail |
|------|----------|--------|
| cleanup 成功 | 200 | cleanup_status="cleaned" |
| user_confirmed=False | 422 | "cleanup requires explicit user_confirmed=true" |
| workspace_type != WORKTREE | 422 | "session is not in a worktree" |
| workspace_path 未在 allowed root 下 | 422 | "path outside allowed workspace root" |
| worktree dirty + force=False | 409 | "worktree has uncommitted changes; use force=true to override" |
| workspace_path 不存在 (已清理) | 200 (idempotent) | cleanup_status="cleaned", removed_worktree=False |
| git worktree remove 失败 | 500 | "worktree removal failed: ...error..." |
| AgentSession 不存在 | 404 | "Agent session not found: {id}" |
| workspace never created | 404 | "no workspace to clean up" |

---

## 9. 回滚策略

### 9.1 完整回滚矩阵

| 失败场景 | 触发条件 | AgentSession 状态 | 回滚动作 |
|---------|---------|-------------------|---------|
| worktree add 成功但 AgentSession 写回失败 | DB error after git success | workspace_path=None, worktree 已创建 | cleanup 调用 → git worktree remove |
| worktree remove 成功但 branch delete 失败 | branch 被其他 worktree 使用 | worktree 已删, branch 仍存在 | 返回 partial: removed_worktree=True, removed_branch=False |
| branch delete 成功但 AgentSession 写回失败 | DB error during cleanup write | worktree 已删, branch 已删, AgentSession 脏 | retry update_status OR leave error for manual fix |
| cleanup 中断 | 进程 crash / timeout | 部分清理 | cleanup 应幂等: 再次调用不报错 |
| path 已不存在 | 手动删除 / previous partial cleanup | — | idempotent: skip worktree remove, still reset AgentSession fields |
| branch 已不存在 | 手动删除 / 从未创建 | — | idempotent: skip branch delete |
| dirty worktree + force=False | 未提交修改 | — | blocked: 返回 409 + blockers list |
| git timeout | git worktree remove 超时 | — | 返回 500 + timeout error |
| permission denied | filesystem 权限 | — | 返回 500 + permission error |

### 9.2 幂等设计

```python
def cleanup_workspace(session_id, user_confirmed, force=False, delete_branch=False):
    session = agent_session_repository.get_by_id(session_id)

    # Idempotency: 如果 workspace_path 已经是 None, 返回 already_clean
    if session.workspace_path is None:
        return WorktreeCleanupResult(
            cleanup_status="cleaned",
            removed_worktree=False,
            ...
        )

    # 如果 worktree 路径已不存在 (手动删除)，跳过 git remove
    if not Path(session.workspace_path).exists():
        # 只重置 AgentSession 字段
        write_agent_session_reset(session_id)
        return WorktreeCleanupResult(
            cleanup_status="cleaned",
            removed_worktree=False,
            worktree_was_registered=False,
            ...
        )

    # ... 正常 cleanup 流程 ...
```

### 9.3 agent-orchestrator CleanupStack 模式

agent-orchestrator 使用 `CleanupStack` 模式:

```typescript
const cleanupStack = new CleanupStack();
cleanupStack.push(() => deleteMetadata(...));  // undo: delete metadata
cleanupStack.push(() => ws.destroy(path));     // undo: destroy workspace
// On failure: await cleanupStack.runAll()
// On success: cleanupStack.dismiss()
```

**建议**: P1-E 暂不引入 CleanupStack (当前 create 是单步 git 操作)；在 P2+ spawn 流程中引入。

---

## 10. 第一条 Codex 实现任务建议

### 10.1 候选任务

| 候选 | 描述 | 风险 |
|------|------|------|
| A. WorktreeCleanupService blocked skeleton | 类似 P1-D-E-A 的 skeleton 模式: service 返回 blocked result | 最低 |
| B. cleanup dry-run API | API shape 先定，返回 cleanup plan | 低 |
| C. CleanupGuardService pure validation | 独立 guard 检查，不执行 git | 低 |
| D. cleanup_status 字段 | DB migration + AgentSession 字段扩展 | 中 |
| E. WorktreeWriteCommandRunner 扩展 disabled preview | 新增 git_worktree_remove + git_branch_delete_safe preview (execution_enabled=False) | 低 |

### 10.2 推荐: E + A (合并)

**任务: WorktreeWriteCommandRunner 扩展 + WorktreeCleanupService blocked skeleton**

```
范围:
  1. WorktreeWriteCommandRunner 增加:
     · git_worktree_remove() → WorktreeWriteCommandPreview (execution_enabled=False)
     · git_branch_delete_safe() → WorktreeWriteCommandPreview (execution_enabled=False)
     · _ensure_write_allowlisted() 扩展: 新增 "git_worktree_remove" + "git_branch_delete_safe"

  2. app/domain/worktree_cleanup.py (新文件):
     · WorktreeCleanupResult domain model

  3. app/services/worktree_cleanup_service.py (新文件):
     · WorktreeCleanupService blocked skeleton
     · 接收 session_id + user_confirmed
     · 返回 blocked result (not_implemented, removed_worktree=False, removed_branch=False)
     · 不执行任何 git write

  4. app/api/routes/agent_threads.py:
     · WorktreeCleanupRequestBody + WorktreeCleanupResponse DTO
     · POST /agent-threads/sessions/{id}/workspace/cleanup endpoint
     · 返回 blocked skeleton

  5. tests:
     · WorktreeWriteCommandRunner 新 spec 验证
     · CleanupSpec 的 execution_enabled=False 验证
     · WorktreeCleanupService blocked skeleton 验证

边界:
  - 不执行 git worktree remove
  - 不执行 git branch -d
  - 不删除 worktree
  - 不删除 branch
  - 不写 AgentSession
  - 不新增 DB 表
  - 不改前端
```

### 10.3 为什么选这个

1. **最小增量**: Write runner 只是 spec builder + preview，不执行 git
2. **安全渐进**: blocked skeleton 模式已在 P1-D-E-A 验证安全
3. **API shape 先定义**: 在真实 git 操作前，API 接口和响应结构先确定
4. **与已有基础设施兼容**: 复用 WorktreeWriteCommandRunner、WorktreeGuardService、AgentSessionRepository
5. **agent-orchestrator 对齐**: 先有 `cleanup()` 接口签名，后有真实实现

---

## 11. 明确不建议现在做的事

| 不建议 | 原因 |
|--------|------|
| 让 AI runtime 进入 worktree | P2+ scope |
| 自动改代码 | P2+ scope |
| 自动 git add/commit | P2+ scope |
| 自动 git push | P2 scope |
| 自动创建 PR | P2 scope |
| 接 CI | P2 scope |
| force 删除 dirty worktree | P1-E 默认 force=false |
| `rm -rf` 删除 worktree | git worktree remove 是正确方式 |
| `git branch -D` (force delete) | git branch -d 是安全选择 |
| 复杂前端 | P1 是后端基础设施 |
| 把 AI Project Director 总闭环标记为 Pass | 总闭环仍为 Partial |

---

## 12. 总结

### 当前已有能力

| 能力 | 状态 |
|------|------|
| WorktreePlan dry-run + plan_hash | ✅ |
| BranchNamePolicy (安全分支名) | ✅ |
| WorktreeGuardService (路径安全) | ✅ |
| plan_hash 验证 (stale 拒绝) | ✅ |
| read-only git preflight (5 specs + --is-inside-work-tree) | ✅ |
| 9 blocker 全覆盖 | ✅ |
| AgentSession workspace 字段 (5) | ✅ |
| AgentSessionRepository workspace CRUD | ✅ |
| API: workspace-plan, /confirm, /prepare, /create | ✅ |
| 真实 git worktree add -b 执行 | ✅ |
| AgentSession 写回 + last_workspace_error 修正 | ✅ |
| 测试: 47 tests pass | ✅ |

### 当前仍缺口

| 缺口 | P |
|------|---|
| WorktreeWriteCommandRunner: git_worktree_remove + git_branch_delete_safe | P1-E |
| WorktreeCleanupService | P1-E |
| API POST /workspace/cleanup | P1-E |
| 真实 cleanup 执行 | P1-E |
| 幂等 guard | P1-E |
| AgentMessage timeline (audit event) | P1-E |
| CleanupStack (rollback) | P2+ |
| 后续代码执行 (AI runtime 进入 worktree) | P2+ |
| commit candidate / PR | P2+ |

### 推荐最小路线

1. **P1-E-A**: WorktreeWriteCommandRunner 扩展 + WorktreeCleanupService blocked skeleton (本次建议)
2. **P1-E-B**: Guarded real cleanup execution + API

### Gate 结论

- **Coding Session P1-E cleanup / rollback design audit**: **Pass** ✅ — 设计审计完成，cleanup 命令边界、guard 链、API shape、回滚矩阵、AgentSession 字段策略均已定义。
- **AI Project Director 总闭环**: **仍为 Partial** — cleanup 尚未实现，后续代码执行仍未接入。

### 下一条建议给 Codex 的最小任务

**P1-E-A**: `WorktreeWriteCommandRunner` 扩展 + `WorktreeCleanupService` blocked skeleton。纯新增，不执行 git write，不删除 worktree/branch。API shape 先于实现。

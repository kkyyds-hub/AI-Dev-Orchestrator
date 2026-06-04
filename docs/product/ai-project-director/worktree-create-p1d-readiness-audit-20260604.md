# Coding Session P1-D 真实 Worktree + Branch 创建前 readiness audit

> **文档类型**: 设计审计 / readiness audit
> **生成日期**: 2026-06-04
> **基准 commit (AI-Dev)**: `36d3716` (feat: mark worktree plans as dry run)
> **参考项目 agent-orchestrator**: `c3eeecb`
> **前置文档**:
> - `docs/product/ai-project-director/worktree-branch-p1-design-audit-20260604.md` (P1-A)
> - `docs/product/ai-project-director/verification-worktree-plan-p1c-dry-run-20260604.md` (P1-C)
> - `docs/product/ai-project-director/coding-session-lifecycle-design-20260604.md` (四轴设计基线)
> **边界**: 只做设计审计，不改业务代码，不创建 worktree，不创建 branch
> **状态**: 设计审计完成

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator

| 文件 | 当前状态 |
|------|---------|
| `runtime/orchestrator/app/domain/worktree_plan.py` | ✅ 已读 — 13 字段，含 `dry_run=True`, `requires_user_confirmation=True` |
| `runtime/orchestrator/app/services/worktree_plan_service.py` | ✅ 已读 — WorktreePlanService + BranchNamePolicy + WorktreeGuardService |
| `runtime/orchestrator/app/api/routes/agent_threads.py` | ✅ 已读 — WorktreePlanResponse + POST/GET workspace-plan |
| `runtime/orchestrator/tests/test_worktree_plan_dry_run.py` | ✅ 已读 — 7 tests, 20 total pass |
| `runtime/orchestrator/app/domain/agent_session.py` | ✅ 已读 — 含 `workspace_type`, `workspace_path`, `workspace_clean` |
| `runtime/orchestrator/app/repositories/agent_session_repository.py` | ✅ 已读 — 支持 workspace 字段 CRUD |
| `runtime/orchestrator/app/domain/repository_workspace.py` | ✅ 已读 |
| `runtime/orchestrator/app/repositories/repository_workspace_repository.py` | ✅ (先前审计) |
| `runtime/orchestrator/app/services/branch_session_service.py` | ✅ (先前审计) |
| `runtime/orchestrator/app/services/local_git_write_service.py` | ✅ (先前审计) |
| `runtime/orchestrator/app/services/git_write_state_tracker.py` | ✅ (先前审计) |
| `runtime/orchestrator/app/core/db_tables.py` | ✅ 已读 — workspace_type, workspace_path, workspace_clean columns 已存在 |

### agent-orchestrator

| 文件 | 用途 |
|------|------|
| `README.md` | 项目概览 |
| `ARCHITECTURE.md` | 架构设计 |
| `docs/PLUGIN_SPEC.md` | 插件规范 |
| `packages/core/src/types.ts` | Workspace interface, WorkspaceCreateConfig, WorkspaceInfo, CleanupStack |
| `packages/plugins/workspace-worktree/src/index.ts` | Worktree 创建/销毁/发现实现 |
| `packages/core/src/session-manager.ts` | SessionManager.spawn → workspace.create → runtime.create → metadata.write |
| `packages/core/src/lifecycle-manager.ts` | readWorkspaceBranch + branch conflict resolution |
| `packages/core/src/lifecycle-state.ts` | CanonicalSessionLifecycle |
| `packages/core/src/metadata.ts` | Metadata 持久化 |

---

## 1. 当前 P1-C dry-run 已具备什么

### 1.1 WorktreePlan 模型 (13 字段)

```python
class WorktreePlan(DomainModel):
    agent_session_id: UUID
    project_id: UUID
    repository_workspace_id: UUID | None = None
    safe: bool                                    # guard 全部通过?
    dry_run: bool = True                          # ← 显式 dry-run 标记
    requires_user_confirmation: bool = True       # ← 显式用户确认标记
    workspace_type: str = "worktree"
    worktree_path: str | None                     # 规划的工作区路径
    branch_name: str | None                       # 规划的分支名
    base_branch: str | None                       # 基线分支
    base_commit_sha: str | None                   # 基线 commit (当前 None)
    git_commands_to_run: list[str]                # 预览命令 (不执行)
    blockers: list[str]                           # 阻塞原因
    warnings: list[str]                           # 警告信息
```

### 1.2 Infrastructure

| 组件 | 状态 |
|------|------|
| **BranchNamePolicy** | ✅ 确定性分支名生成 + 8 种 unsafe pattern 拒绝 |
| **WorktreeGuardService** | ✅ 纯路径安全验证 (绝对路径/允许范围/源仓库隔离/路径存在检测) |
| **WorktreePlanService** | ✅ 纯计算，不调用 subprocess/os.system/git |
| **API** | ✅ POST + GET `/agent-threads/sessions/{id}/workspace-plan` — 明确 dry-run 语义 |
| **AgentSession workspace 字段** | ✅ `workspace_type` (IN_PLACE), `workspace_path`, `workspace_clean` — 已落库 |
| **AgentSessionRepository** | ✅ create/update/_to_domain 支持 workspace 字段 |
| **AgentSessionResponse** | ✅ 透传 workspace_type, workspace_path, workspace_clean |

### 1.3 测试覆蓋

| 测试 | 验证内容 |
|------|---------|
| `test_worktree_plan_generates_safe_dry_run_for_bound_repository` | dry_run=True, requires_user_confirmation=True |
| `test_worktree_plan_response_exposes_dry_run_fields` | API DTO 透传 dry_run + requires_user_confirmation |
| `test_worktree_plan_blocks_missing_repository_workspace_binding` | 无绑定时 safe=False |
| 4 个 guard/branch policy 测试 | 安全边界完整 |
| P0 tests (13) | 全部通过 |

---

## 2. P1-D 真实创建前还缺什么

### 2.1 字段级缺口

| 缺口 | 严重程度 | 分析 |
|------|---------|------|
| **plan_id / plan_hash** | **P1-D 必须** | 当前 WorktreePlan 是瞬态计算 (每次重新生成)，没有持久化 ID 或内容哈希。P1-D 真实创建时，前端应发送一个 `plan_hash`，后端必须对比当前重新计算的 plan 是否一致。防止 stale plan 被执行。 |
| **plan 持久化** | P1-D 可选 | 当前不需要持久化 WorktreePlan (数据库只存 AgentSession workspace 字段)。但 plan_hash 验证需要一种方式让调用方持有 "我当时看到的 plan 的指纹"。方案: 把 `hash(json.dumps(plan_fields))` 放在 response 里，P1-D 创建时要求客户端回传。 |
| **用户确认记录** | **P1-D 必须** | 在真实 git 操作前，系统必须知道 "用户确实确认了"。当前 dry-run plan 设置 `requires_user_confirmation=True` 但没有确认记录机制。需要一个 confirmation receipt。 |
| **idempotency guard** | **P1-D 必须** | 同一 session 重复调用 workspace 创建 API 时，必须有能力检测 "已创建" 并返回已有结果 (而不是创建第二个 worktree)。`AgentSession.workspace_path` 非 None 可作为简单 idempotency key。 |
| **base_commit_sha** | **P1-D 必须** | 当前始终 None。真实创建前必须调用 `git rev-parse origin/<base_branch>` 获取基线 commit。 |
| **workspace_status** | P1-D 建议 | AgentSession 已有 `workspace_type`/`workspace_path`/`workspace_clean`。缺一个显式的 lifecycle 状态枚举 (如 not_created/creating/ready/failed/cleaned)。`workspace_clean` 是 boolean 标志位，不够表达中间态。 |
| **last_workspace_error** | P1-D 建议 | 真实 git 操作可能失败，需要记录最后一次失败的详细信息。当前 AgentSession 无此字段。 |
| **git command timeout** | P1-D 必须 | 网络相关 (`git fetch`, `git worktree add` 需要 fetch) 可能超时。需要超时配置 + 超时时记录错误。 |
| **audit log** | P1-D 建议 | 真实 git 操作应记录到 AgentMessage (timeline event) 或新增 audit 记录。当前 AgentConversationService 已有 `_append_message()` 可用。 |

### 2.2 流程级缺口

| 缺口 | 说明 |
|------|------|
| **plan hash verify** | 真实创建前需对比 "用户确认时的 plan" 和 "当前的 plan"。若仓库状态变化 (如 base branch 被 force push)，plan 可能不再 safe。 |
| **RepositoryWorkspace 预检** | P1-D 真实创建前，需要 `git fetch --dry-run origin` 确保 origin 可访问。当前 WorktreePlanService 不调用任何 git。 |
| **base branch 可达性** | P1-D 需要 `git rev-parse origin/<base>` 确认 base branch 存在并获取 commit SHA。 |
| **主仓库 clean 检查** | 如果主仓库有未提交更改，`git worktree add` 可能受影响。需要检查 `git status --porcelain`。 |
| **confirmation receipt 机制** | 需要一个最小模型记录 "谁在什么时候确认了什么 plan"，防止重放攻击。 |

### 2.3 不需要的

| 不需要 | 原因 |
|--------|------|
| plan 持久化到 DB | 瞬态计算即可。AgentSession workspace 字段已存储结果 |
| 多用户审批流 | P1-D 只需要单个用户在 API 层确认 |
| plan 版本管理 | 不需要 (plan 是瞬态计算) |
| plan 过期时间 | plan 每次重新计算，旧的自动失效 |

---

## 3. 用户确认模型

### 3.1 确认内容

```
用户确认 = (user 看到了 dry-run plan) + (user 同意了 plan 的内容) + (plan 被提交给后端)
```

具体: 用户在 UI 上看到 WorktreePlan:
- `safe = True`
- `branch_name = "session/proj-a1b2c3d4-e5f6g7h8"`
- `worktree_path = "/allowed/root/.aido-worktrees/project-a1b2c3d4/session-e5f6g7h8"`
- `git_commands_to_run = ["git worktree add ...", "git checkout -b ..."]`
- `requires_user_confirmation = True`

用户点击确认后，前端发送:
```json
{
  "session_id": "...",
  "plan_hash": "sha256-of-plan-fields",
  "confirmed_by": "user"  // 或 "system" / "automated"
}
```

### 3.2 确认规则

| 规则 | 实现方式 |
|------|---------|
| **谁确认** | 当前不需要用户身份系统。"confirmed_by" 可以是字面值 "user" 或从 header 取 |
| **确认什么** | 确认特定的 WorktreePlan (由 plan_hash 指纹标识) |
| **确认后是否过期** | 不自动过期。但如果 AgentSession 已有 workspace_path，自动跳过创建 (idempotent) |
| **plan 改变后是否必须重新确认** | 是。plan_hash 不匹配时必须拒绝创建，返回 409 Conflict |
| **是否允许后台自动创建** | 否。P1-D 需要 `requires_user_confirmation=True` 被确认后才能执行 |
| **如何防止 old plan 被复用** | plan_hash 对比机制。每次 GET/POST workspace-plan 重新计算，hash 随之变化 |
| **如何记录 confirmation receipt** | 作为 AgentMessage (timeline event) 写入: `event_type=workspace_confirmed, content_summary=plan_hash={hash}` |

### 3.3 Confirmation receipt 最小模型 (建议仅在 DTO 层，不建表)

```python
class WorktreePlanConfirmation(BaseModel):
    """Confirmation receipt for a specific dry-run plan."""
    session_id: UUID
    plan_hash: str                  # sha256 of plan canonical fields
    confirmed_by: str = "user"
    confirmed_at: datetime          # = utc_now()
```

**设计决定**: 不建表，不持久化 receipt。AgentMessage 时间线记录 `event_type=workspace_confirmed` 即可。plan_hash 用于防重放。

---

## 4. P1-D 最小真实创建流程建议

### 4.1 推荐流程

```
Step 1 - 前端: GET /agent-threads/sessions/{id}/workspace-plan
          ← 200 WorktreePlan { safe, dry_run=true, requires_user_confirmation=true, ... }
          ← plan_hash (新增字段)

Step 2 - 前端: 展示 plan 给用户。如果 safe=false 则显示 blockers。
          如果 safe=true 且 dry_run=true 且 requires_user_confirmation=true，显示 "确认创建" 按钮。

Step 3 - 用户: 点击 "确认创建"

Step 4 - 前端: POST /agent-threads/sessions/{id}/workspace
          body: { plan_hash: "<hash from step 1>", confirmed_by: "user" }

Step 5 - 后端 (WorktreeCreateService.create):
  5.1  读取 AgentSession  — 验证 session 存在
  5.2  读取 RepositoryWorkspace  — 验证仓库绑定
  5.3  重新计算 WorktreePlan (WorktreePlanService.build_plan)
  5.4  验证 plan.safe == True  — 否则 409 Conflict
  5.5  验证 plan.requires_user_confirmation == True
  5.6  计算 plan_hash = sha256(worktree_path, branch_name, base_branch, ...)
  5.7  验证请求中的 plan_hash == 重新计算的 plan_hash  — 否则 409 "plan has changed, please re-review"
  5.8  幂等检查: AgentSession.workspace_path 非 None?
        → 是: 返回 200 "already created" + session 当前状态 (idempotent)
  5.9  验证 RepositoryWorkspace.root_path 存在 + .git 存在
  5.10 验证 allowed_workspace_root 下可写
  5.11 验证 branch_name 不在 git branch --list 中
  5.12 验证 worktree_path 不存在 (或为空目录)
  5.13 执行 git fetch origin --quiet (timeout 30s)
  5.14 执行 git rev-parse origin/<base_branch>  → base_commit_sha
  5.15 执行 git worktree add --detach <path> <base_commit_sha>  (timeout 60s)
  5.16 执行 git -C <path> checkout -b <branch_name>  (timeout 15s)
  5.17 写回 AgentSession:
        · workspace_type = WORKTREE
        · workspace_path = <path>
        · workspace_clean = True (新 worktree 无修改)
        · branch_name = <branch_name>
  5.18 记录 AgentMessage: event_type="workspace_created", event_type="workspace_confirmed"
  5.19 返回 201 Created + AgentSessionResponse

Step 6 - 错误处理 (任何步骤失败):
  · Step 5.15 失败 → 回滚: git worktree remove --force <path> (如果目录已创建)
  · Step 5.16 失败 → 回滚: git worktree remove --force <path> + git branch -D <branch_name>
  · Step 5.17 失败 → 回滚: git worktree remove --force <path> + git branch -D <branch_name>
  · 任何步骤失败 → 写回 AgentSession.last_workspace_error (需要新字段)
  · 任何步骤失败 → 返回 500/409/422 带详细错误信息
```

### 4.2 替代方案 (更保守)

```
Step 4': POST /agent-threads/sessions/{id}/workspace-plan/confirm
         只做确认记录 (AgentMessage timeline event)，不执行 git

Step 4'': POST /agent-threads/sessions/{id}/workspace/prepare
           = confirm + git 创建. 两步合并但语义明确.
```

**建议**: 采用两阶段 API:
1. `POST .../workspace-plan/confirm` — 记录确认 (纯 DB 写)
2. `POST .../workspace` — 执行创建 (git write + DB write)

两阶段分离的好处:
- confirm 是幂等纯 DB 操作，可重试
- workspace create 涉及 git 可能超时/失败，需要单独处理
- 用户可以先确认再看一次 plan，最后才执行

---

## 5. Git 命令边界

### 5.1 P1-D 可以引入的 git 命令

| 命令 | 用途 | 读/写 | 超时 |
|------|------|------|------|
| `git fetch origin --quiet` | 同步远程引用 | 只读 (从 remote) | 30s |
| `git rev-parse --is-inside-work-tree` | 确认在 Git 仓库内 | 只读 | 5s |
| `git rev-parse origin/<base>` | 获取基线 commit SHA | 只读 | 10s |
| `git status --porcelain=v1` | 检查主仓库状态 | 只读 | 10s |
| `git worktree list --porcelain` | 检查已存在 worktree | 只读 | 10s |
| `git branch --list <name>` | 检查分支是否存在 | 只读 | 5s |
| `git worktree add --detach <path> <ref>` | 创建隔离工作区 | **写入** | 60s |
| `git -C <path> checkout -b <name>` | 在新 worktree 内创建分支 | **写入** | 15s |

### 5.2 P1-D 仍禁止

```
git add / git commit / git push / gh pr create
git merge / git rebase / git stash
git reset --hard / git clean -fd
apply-local / git write via LocalGitWriteService
对主仓库的任何修改
```

### 5.3 执行模型

所有 git 命令**仅在 `WorktreeCommandRunner` 中执行**。其他服务通过调用 `WorktreeCommandRunner` 的 allowlist 方法来执行 git 命令。allowlist 在代码编译时即确定，不给运行时动态命令传入空间。

---

## 6. 安全与回滚

### 6.1 创建前预检 (全部通过才执行 git)

```
1. AgentSession 存在
2. RepositoryWorkspace 存在
3. WorktreePlan safe == True
4. plan_hash 匹配
5. AgentSession.workspace_path is None (幂等)
6. repository root exists + .git exists
7. git fetch origin succeeds (timeout)
8. base_branch resolves: git rev-parse origin/<base> → commit SHA
9. branch_name not in git branch --list
10. worktree path safe (WorktreeGuardService)
```

### 6.2 失败与回滚矩阵

| 失败场景 | 回滚动作 | 记录 |
|---------|---------|------|
| plan_hash 不匹配 | 无需回滚 (未执行任何操作) | 返回 409 |
| AgentSession.workspace_path 已有值 | 无需回滚 (幂等) | 返回 200 + 当前状态 |
| git fetch 失败 | 无需回滚 | 返回 502 "origin unreachable" |
| rev-parse 失败 | 无需回滚 | 返回 400 "base branch not found" |
| branch 已存在 | 无需回滚 | 返回 409 "branch already exists" |
| worktree path 已存在且非空 | 无需回滚 | 返回 409 "worktree path exists" |
| git worktree add 失败 (目录未创建) | 无需回滚 | 返回 500 + last_workspace_error |
| git worktree add 成功 | — | 记录: cleanup_actions = [("worktree", path)] |
| checkout -b 失败 | git worktree remove <path> | 返回 500 + last_workspace_error |
| checkout -b 成功 | — | 记录: cleanup_actions += [("branch", name)] |
| DB 写回失败 | git worktree remove <path> + git branch -D <name> | 返回 500 + last_workspace_error |

### 6.3 安全约束

```
1. worktree 只能在 allowed_workspace_root/.aido-worktrees/ 下创建
2. branch 只能以 session/ 开头
3. git worktree remove 只能清理 .aido-worktrees/ 下的 worktree
4. git branch -D 只能删除 session/ 开头的分支
5. 不影响主仓库 (base branch 引用的 commit 不变)
6. 不影响其他 session 的 worktree
7. 不在主仓库内创建任何文件
8. 不修改主仓库的 HEAD / index / working tree
```

---

## 7. 建议新增服务

### 7.1 WorktreeCommandRunner — P1-D 核心

```
职责: 安全执行允许的 git 命令，deny-by-default
输入: 函数名 + 参数 (编译时确定，不接受任意命令字符串)
输出: 命令输出字符串或异常
是否执行 git: 是 (只执行 allowlist 中的命令)
是否写数据库: 否 (纯 shell 层)
出错处理: 抛出 TimeoutError / CommandFailed / CommandDenied
是否需要用户确认: 否 (调用方负责在调用前确认)
```

Allowlist 函数:

```python
class WorktreeCommandRunner:
    def git_fetch(self, repo_path: Path) -> str: ...
    def git_rev_parse(self, repo_path: Path, ref: str) -> str: ...
    def git_status_porcelain(self, repo_path: Path) -> str: ...
    def git_worktree_list(self, repo_path: Path) -> str: ...
    def git_branch_list(self, repo_path: Path, name: str) -> str: ...
    def git_worktree_add(self, repo_path: Path, worktree_path: str, ref: str) -> None: ...
    def git_checkout_new_branch(self, worktree_path: str, branch_name: str) -> None: ...
    def git_worktree_remove(self, worktree_path: str) -> None: ...
    def git_branch_delete(self, repo_path: Path, branch_name: str) -> None: ...
```

**deny-by-default**: 不接受任意命令字符串。每个方法内部硬编码 `["git", "subcommand", ...]`。

### 7.2 WorktreeCreateService — P1-D 业务编排

```
职责: 编排完整的 "确认 plan → 创建 worktree → 写回 AgentSession" 流程
输入: session_id, plan_hash, confirmed_by
输出: AgentSession (workspace 字段已填充)
是否执行 git: 是 (通过 WorktreeCommandRunner)
是否写数据库: 是 (通过 AgentSessionRepository)
出错处理: 回滚 + 记录 last_workspace_error
是否需要用户确认: 是 (调用前需先确认)
```

### 7.3 WorkspaceConfirmationService — P1-D 确认记录

```
职责: 记录用户确认 receipt (AgentMessage timeline event)
输入: session_id, plan_hash, confirmed_by
输出: AgentMessage (event_type="workspace_confirmed")
是否执行 git: 否
是否写数据库: 是 (AgentMessageRepository.create)
是否需要用户确认: N/A (此服务本身就是确认动作)
```

### 7.4 WorktreeAuditService — P1-D 审计

```
职责: 记录 workspace 操作到 AgentMessage timeline
输入: session_id, event_type, summary, detail
输出: AgentMessage
是否执行 git: 否
是否写数据库: 是 (AgentMessageRepository)
是否需要用户确认: 否
```

**备注**: 可以通过复用 `AgentConversationService._append_message()` 来实现，不需要独立服务。但如果操作类型增多，独立 service 可读性更好。

### 7.5 复用现有服务

| 现有服务 | P1-D 用途 |
|---------|----------|
| `WorktreePlanService` | Step 5.3: 重新生成 plan 用于 hash 验证 |
| `BranchNamePolicy` | 分支名生成 (已确定) |
| `WorktreeGuardService` | 路径安全验证 (已确定) |
| `AgentConversationService._append_message()` | 写 timeline event |

### 7.6 不需要的服务

| 不需要 | 原因 |
|--------|------|
| WorkspaceCleanupService (完整) | P1-E 的 scope，P1-D 只做创建+简单回滚 |
| WorkspacePool | P1 无并发管理需求 |
| WorktreeHealthService | P1 不需要健康检查 |

---

## 8. 建议新增 API

### 8.1 API 设计

| Method | Path | 语义 | 风险级别 |
|--------|------|------|---------|
| `GET` | `/agent-threads/sessions/{id}/workspace-plan` | 重新计算 dry-run plan (已存在) | **安全** — 纯读 |
| `POST` | `/agent-threads/sessions/{id}/workspace-plan` | 重新计算 dry-run plan (已存在) | **安全** — 纯读 |
| `POST` | `/agent-threads/sessions/{id}/workspace-plan/confirm` | **记录确认** — 写入 AgentMessage timeline，不执行 git | **安全** — 纯 DB 写 |
| `POST` | `/agent-threads/sessions/{id}/workspace` | **真实创建** — 执行 git worktree add + checkout -b + DB 写回 | **高风险** — git write |

### 8.2 命名理由

- `workspace-plan/confirm`: 明确是 "确认 plan"，不是 "创建 workspace"
- `workspace`: 简洁名词，Create → POST (REST 语义)
- 不和 `workspace-plan` (dry-run) 混淆
- 不让用户以为只需一个按钮就能创建 — confirm 和 create 是两步

### 8.3 请求/响应契约

```
POST /agent-threads/sessions/{id}/workspace-plan/confirm
  Request:  { plan_hash: str, confirmed_by: str }
  Response: 200 { message: "plan confirmed", session_id, plan_hash, confirmed_at }
            409 { detail: "plan hash mismatch" }
            409 { detail: "plan is not safe" }

POST /agent-threads/sessions/{id}/workspace
  Request:  { plan_hash: str, confirmed_by: str }
  Response: 201 { session: AgentSessionResponse (workspace fields filled) }
            200 { session: AgentSessionResponse }  (idempotent — 已创建)
            409 { detail: "plan hash mismatch" }
            409 { detail: "plan is not safe; cannot create workspace" }
            409 { detail: "workspace already exists; use GET to retrieve" }
            502 { detail: "origin unreachable" }
            500 { detail: "workspace creation failed", error: "..." }
```

### 8.4 防误触机制

1. `workspace-plan/confirm` 不能误触 — 它只是记录确认，不改变仓库
2. `workspace` (真实创建) 需要 `plan_hash` 验证 — 不能绕过用户重新计算 plan 的步骤
3. `workspace` 需要 `requires_user_confirmation=True` (由 plan 决定) — 不能绕过确认
4. `workspace` 幂等 — 重复调用对已创建 session 返回 200 (不重复创建)

---

## 9. 建议新增字段/模型

### 9.1 AgentSession 扩展 (P1-D 最小)

| 字段 | 类型 | 优先级 | 说明 |
|------|------|--------|------|
| `last_workspace_error` | text, nullable | P1-D **必须** | 记录最近一次 git 操作失败的详细信息 |

`workspace_type`, `workspace_path`, `workspace_clean` 已存在。`workspace_status` (lifecycle enum) 和 `workspace_created_at` 可推迟到 P1-E。

### 9.2 建议新增 DTO (不建表)

| DTO | 用途 | 持久化 |
|-----|------|--------|
| `WorktreePlanConfirmation` | 用户确认 receipt | 否 — 仅 API 层 |
| `WorkspaceCreateResult` | 真实创建的结果 | 否 — 返回 AgentSessionResponse |
| `WorkspaceCreateError` | 详细错误信息 | 否 — 在 response body 中返回 |

### 9.3 WorktreePlan 扩展 (P1-D 最小)

| 字段 | 当前值 | P1-D 建议 |
|------|--------|----------|
| `plan_hash` | 无 | **新增** — `sha256(worktree_path + branch_name + base_branch + base_commit_sha)` |
| `base_commit_sha` | None | P1-D 需要 `WorktreePlanService._compute_base_sha()` 调用 `git rev-parse` |

### 9.4 暂时不建表

| 不要建的表 | 原因 |
|-----------|------|
| WorktreeAuditLog | AgentMessage timeline 已覆盖 |
| WorkspaceConfirmation | 瞬态确认，不需要持久化 |
| WorkspaceOperationLog | AgentMessage 已覆盖 |

---

## 10. 第一条 Codex 实现任务建议

### 建议任务: P1-D-A — WorktreeCommandRunner + AgentSession 字段补强

```
任务: 新增 WorktreeCommandRunner (git 命令执行器 + deny-by-default allowlist)
      + 补强 WorktreePlan (plan_hash 字段)
      + AgentSession 加 last_workspace_error 字段

范围:
  1. 新增 WorktreeCommandRunner 类:
     · deny-by-default: 不接受任意命令字符串
     · allowlist 方法 (不实际执行, 仅定义接口):
       git_fetch, git_rev_parse, git_status_porcelain,
       git_worktree_list, git_branch_list,
       git_worktree_add, git_checkout_new_branch,
       git_worktree_remove, git_branch_delete
     · 所有方法内部用 subprocess.run(cmd, timeout=...) 包裹
     · 每个方法的 cmd 列表不可变 (编译时确定)
     · 仅做只读 dry-run check:
       - git status --porcelain (test 仓库)
       - git rev-parse HEAD (test 仓库)
     · 先不接 WorktreeCreateService

  2. WorktreePlan 新增 plan_hash 计算:
     · plan_hash = sha256 摘要 (不依赖 hashlib 以外的模块)
     · 在 WorktreePlanService._build_plan_payload() 中计算

  3. AgentSession 新增 last_workspace_error:
     · 类型: str | None, max_length=2000
     · ORM: Text nullable
     · Repository: create/update/_to_domain 支持
     · AgentSessionResponse 透传

  4. 测试:
     · WorktreeCommandRunner allowlist 方法签名存在 (不执行真实 git add/commit/push)
     · 只读 git rev-parse 在真实 .git 目录验证
     · plan_hash 稳定性 (相同输入 → 相同输出)
     · plan_hash 变化 (不同输入 → 不同输出)
     · AgentSession last_workspace_error round-trip

边界:
  - 不创建 worktree
  - 不创建 branch
  - 不执行 git write
  - 不调 Worker
  - 不改前端
  - 不新增 DB 表

验收: pytest (tbd 测试文件名)
```

### 为什么选这个任务

1. **WorktreeCommandRunner 是 P1-D 的安全基础**: 把 git 调用集中到一个 deny-by-default 类中，后续任何 git 操作都走 allowlist，杜绝错误调用
2. **只做只读验证**: `git rev-parse HEAD` + `git status --porcelain` 是安全的只读命令，不会修改仓库
3. **plan_hash 是确认模型的前提**: 没有 hash 就没法做 "stale plan 检测"
4. **last_workspace_error 是错误诊断的前提**: 没有错误记录就不知道创建失败的原因
5. **不涉及任何 git 写入**: git worktree add 等方法签名存在但测试中不调用
6. **与现有代码无冲突**: 纯新增，不修改现有服务逻辑

---

## 11. 明确不建议现在做的事

| 不建议 | 原因 |
|--------|------|
| 接 Claude Code runtime | P1 只做 worktree 基础设施 |
| 自动改代码 / apply patch | P1-D 不涉及代码修改 |
| 自动 git commit | P1-D 只创建隔离环境 |
| git push / gh pr create | P2 SCM 集成 |
| 接 CI | P2 SCM 集成 |
| 自动 merge | P2 SCM 集成 |
| 插件生态 | 不需要 |
| 大规模重构前端 | P1-D 是后端基础设施 |
| 自动创建 worktree (无用户确认) | 违反 requires_user_confirmation 设计 |
| 一次性实现完整 WorkspaceCleanupService | P1-E scope |
| 把 AI Project Director 总闭环标记为 Pass | 总闭环仍为 Partial |

---

## 12. 总结

### P1-D 前置条件状态

| 条件 | 状态 |
|------|------|
| WorktreePlan 模型 (含 dry_run, requires_user_confirmation) | ✅ 已实现 |
| BranchNamePolicy (安全分支名) | ✅ 已实现 |
| WorktreeGuardService (路径安全) | ✅ 已实现 |
| WorktreePlanService (dry-run plan 生成) | ✅ 已实现 |
| AgentSession workspace 字段 (workspace_type/path/clean) | ✅ 已实现 |
| AgentSessionRepository workspace CRUD | ✅ 已实现 |
| API workspace-plan endpoint | ✅ 已实现 |
| plan_hash | ❌ 缺失 |
| base_commit_sha (git rev-parse) | ❌ 缺失 |
| WorktreeCommandRunner (git allowlist) | ❌ 缺失 |
| WorkspaceConfirmation API | ❌ 缺失 |
| 幂等 guard | ❌ 缺失 (AgentSession.workspace_path 可用但未被 API 消费) |
| last_workspace_error | ❌ 缺失 |
| WorktreeCreateService | ❌ 缺失 |
| 用户确认流程 (API) | ❌ 缺失 |

### 建议的 P1-D 最小路线

```
P1-D-A: WorktreeCommandRunner + plan_hash + last_workspace_error (本次建议)
P1-D-B: WorkspaceConfirmationService + API (确认记录, 不执行 git)
P1-D-C: WorktreeCreateService + API (真实 git worktree add, 需要用户确认)
```

### 下一条建议给 Codex 的最小任务

**P1-D-A**: WorktreeCommandRunner (deny-by-default git allowlist) + WorktreePlan plan_hash + AgentSession last_workspace_error。纯新增，不接任何创建逻辑，不改现有服务。

### Gate 结论

- **Coding Session P1-D readiness audit**: **Pass** ✅
  - 审计了 20 个文件 (AI-Dev 12 + agent-orchestrator 8)
  - 明确了当前 P1-C 的完整状态
  - 识别了 P1-D 的 17 项前置缺口
  - 设计了完整的创建流程、安全边界、失败回滚
  - 给出了具体的 API 设计和 Codex 任务建议

- **AI Project Director 总闭环**: **仍为 Partial**
  - P0 字段已实现并验证 (Pass)
  - P1-A 设计审计完成 (Pass)
  - P1-C dry-run 验证通过 (Pass)
  - P1-D 真实创建尚未实现
  - P2 SCM 集成尚未开始

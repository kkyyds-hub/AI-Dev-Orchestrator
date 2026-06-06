# Coding Session P1 Worktree / Branch 最小实现审计与设计

> **文档类型**: 设计审计 / gap analysis
> **生成日期**: 2026-06-04
> **基准 commit (AI-Dev)**: `c6391f7` (chore: refine coding session status copy)
> **参考项目 agent-orchestrator**: `c3eeecb` (merge fork, 25 May - 2 June, #2086)
> **前置设计基线**: `docs/product/ai-project-director/coding-session-lifecycle-design-20260604.md`
> **P0 验证**: `docs/product/ai-project-director/verification-coding-session-p0-fields-20260604.md`
> **边界**: 只做设计和只读推导，不改代码、不建表、不加 API、不启动服务、不运行 git write
> **状态**: 设计审计完成

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator

| 文件 | 用途 |
|------|------|
| `.kkr/skills/ai-project-director-command-governance/SKILL.md` | 指令治理规范 |
| `docs/product/ai-project-director/coding-session-lifecycle-design-20260604.md` | 四轴生命周期设计基线 |
| `docs/product/ai-project-director/verification-coding-session-p0-fields-20260604.md` | P0 字段验证 |
| `docs/product/ai-project-director/page-information-architecture-20260518.md` | 主产品基线 |
| `docs/product/ai-project-director/closure-flow-20260518.md` | 闭环流程 |
| `docs/product/ai-project-director/closure-checklist-20260518.md` | 闭环验收清单 |
| `runtime/orchestrator/app/domain/agent_session.py` | AgentSession (含已定义的 WorkspaceType 枚举) |
| `runtime/orchestrator/app/domain/change_batch.py` | ChangeBatch 领域模型 |
| `runtime/orchestrator/app/domain/commit_candidate.py` | CommitCandidate 领域模型 |
| `runtime/orchestrator/app/domain/change_session.py` | ChangeSession 领域模型 |
| `runtime/orchestrator/app/domain/repository_workspace.py` | RepositoryWorkspace 领域模型 |
| `runtime/orchestrator/app/core/db_tables.py` | 全部 DB 表定义 |
| `runtime/orchestrator/app/api/routes/repositories.py` | Repository API |
| `runtime/orchestrator/app/api/routes/agent_threads.py` | AgentSession API |
| `runtime/orchestrator/app/api/routes/workers.py` | Worker API |
| `runtime/orchestrator/app/services/local_git_write_service.py` | 本地 Git 写入服务 |
| `runtime/orchestrator/app/services/git_write_state_tracker.py` | Git 写入状态追踪 |
| `runtime/orchestrator/app/services/branch_session_service.py` | 分支会话服务 |
| `runtime/orchestrator/app/services/change_batch_service.py` | 变更批次服务 |
| `runtime/orchestrator/app/services/commit_candidate_service.py` | 提交草案服务 |
| `runtime/orchestrator/app/services/repository_workspace_service.py` | 仓库工作区服务 |
| `runtime/orchestrator/app/workers/task_worker.py` | TaskWorker |
| 全量 grep: `git worktree`, `git branch`, `worktree_path`, `workspace_type`, `cleanup` 相关代码 |

### agent-orchestrator

| 文件 | 用途 |
|------|------|
| `README.md` | 项目概览 |
| `CLAUDE.md` | 开发文档 |
| `ARCHITECTURE.md` | 架构设计 |
| `docs/PLUGIN_SPEC.md` | 插件规范 |
| `packages/core/src/types.ts` | 核心类型 (Workspace interface, WorkspaceCreateConfig) |
| `packages/plugins/workspace-worktree/src/index.ts` | Worktree 工作区插件实现 |
| `packages/core/src/lifecycle-manager.ts` | 生命周期管理器 (workspace branch probe) |
| `packages/core/src/lifecycle-state.ts` | 生命周期状态解析 |
| `packages/core/src/session-manager.ts` | 会话管理器 (workspace create/destroy) |
| `packages/core/src/metadata.ts` | 元数据持久化 |

---

## 1. 当前 AI-Dev 仓库链路真实现状

### 1.1 逐模块审计

| 模块 | 表名 | 是什么 | 是否真实创建 worktree/branch | 是否调用 git write |
|------|------|--------|--------------------------|-------------------|
| **RepositoryWorkspace** | `repository_workspaces` | 项目级仓库绑定。1 个 Project = 1 个 RepositoryWorkspace。`root_path` 指向本地 Git 仓库根路径。`access_mode` 始终为 `read_only`。`default_base_branch` 包含基线分支名 (如 "main")。 | **否** — 仅记录路径和配置 | **否** — 只读 |
| **RepositorySnapshot** | `repository_snapshots` | 项目级仓库快照。包含 `tree_json` (目录树)、`language_breakdown_json` (语言分布)、`file_count` 等。通过 `RepositoryScanService` (`git ls-tree`) 只读采集。 | **否** — 只读扫描 | **否** — 只读 |
| **ChangeSession** | `change_sessions` | 项目级分支/工作区状态快照。`current_branch`、`head_commit_sha`、`baseline_branch`、`baseline_commit_sha`、`workspace_status` (clean/dirty)、`dirty_files` 列表。通过 `BranchSessionService.capture_project_change_session()` 使用 `git symbolic-ref`、`git rev-parse`、`git status --porcelain` 只读采集。 | **否** — 只读检测 | **否** — 只读 |
| **ChangePlan** | `change_plans` | 变更方案。与 Task 关联。包含 `intent_summary`、`target_files`、`expected_actions`、`verification_commands` 等。 | **否** — 纯数据 | **否** — 纯数据 |
| **ChangeBatch** | `change_batches` | 变更批次。聚合多个 ChangePlan。包含 `preflight` (预检结果，含风险发现)。 | **否** — 纯数据 | **否** — 纯数据 |
| **CommitCandidate** | `commit_candidates` | 提交草案。**只有 DRAFT 状态**。包含 `versions` (CommitCandidateVersion 列表，含 `message_title`、`message_body`、`related_files`、`verification_summary`)。设计明确标注为 review-only draft。 | **否** — 纯数据 (review-only) | **否** — 不触发 git commit |
| **LocalGitWriteService** | — (服务) | 本地 Git 写入服务。**可以执行** `apply-local` (写文件到仓库) 和 `git-commit` (创建提交)。受多层 guard 保护: workspace binding → change batch → preflight → release gate → commit candidate。需要通过 `RepositoryReleaseGate` 放行判断。 | **否** — 不使用 worktree | **是** — 可调用 `git add` + `git commit` |
| **branch_session_service** | — (服务) | 分支会话服务。**只读**检测 Git 状态。`_inspect_git_repository()` 调用 `git symbolic-ref`、`git rev-parse`、`git status --porcelain`。**永不**创建分支或 worktree。 | **否** — 只读检测 | **否** — 只读 |

### 1.2 真实现状结论

```
AI-Dev 当前仓库链路:

  ✅ 已实现:
    - 项目级仓库绑定 (RepositoryWorkspace, read_only)
    - 只读仓库扫描 (RepositorySnapshot)
    - 只读 Git 状态检测 (ChangeSession)
    - 变更方案的 structured representation (ChangePlan)
    - 变更批次数据建模 (ChangeBatch + Preflight)
    - 提交草案数据建模 (CommitCandidate, draft only)
    - 受控本地 Git 写入 (LocalGitWriteService, 需要显式调用)
    - 只读分支检测 (BranchSessionService)

  ❌ 未实现:
    - git worktree add (创建隔离工作区)
    - git worktree remove (清理隔离工作区)
    - per-session 分支创建
    - 任何形式的 push / PR / merge
    - 任何形式的 workspace cleanup
```

**关键发现**: `git grep` 全量搜索确认代码库中 **不存在** `git worktree add`、`git worktree remove`、`git branch -d` 等写操作。`WorkspaceType.WORKTREE` 枚举值已在 `agent_session.py:89` 定义，但 `AgentSession` 模型中没有对应的字段来存储它——它目前只是枚举声明，没有任何消费方。

---

## 2. P0 AgentSession 字段与 P1 worktree/branch 的关系

### 2.1 P0 字段现状

| P0 字段 | 当前默认值 | 为什么只是可观测字段 |
|---------|-----------|-------------------|
| `agent_type` | `openai_provider` | 枚举值正确，但 `AgentConversationService` 硬编码填充。没有 Runtime 插件机制 |
| `runtime_type` | `subprocess` | 正确反映当前执行模型，但 subprocess 不是长期运行的 runtime |
| `runtime_handle_id` | `None` | 没有 tmux session / container ID。subprocess 在 `TaskWorker` 内部同步创建和销毁 |
| `coding_status` | `working` → `completed`/`failed`/`terminated` | 正确反映了 TaskWorker 的同步执行模型 |
| `activity_state` | `active` → `exited` | 正确反映了 subprocess 一次性执行的特性 |
| `branch_name` | `None` | **永远是 None**。因为没有 per-session 分支创建机制 |

### 2.2 缺失的 P1 字段

| 缺失字段 | 类型 | 说明 |
|---------|------|------|
| `workspace_type` | WorkspaceType enum | 工作区隔离策略。当前场景应该是 `IN_PLACE` (直接在项目根目录下执行) |
| `workspace_path` | text | 工作区实际路径。当前是 `RepositoryWorkspace.root_path` (项目绑定路径) |
| `workspace_status` | enum (not_created/creating/ready/dirty/cleaned) | 工作区生命周期状态 |
| `base_branch` | string(200) | 基线分支。从 `RepositoryWorkspace.default_base_branch` 获取 |
| `cleanup_status` | enum (not_needed/pending/completed/failed) | 清理状态 |
| `last_workspace_error` | text | 最近一次工作区操作的错误信息 |
| `worktree_created_at` | datetime | 工作区创建时间 |
| `worktree_cleaned_at` | datetime | 工作区清理时间 |

### 2.3 建议: 扩展 AgentSession，不新建表

**明确结论: 继续扩展 AgentSession，新增 P1 workspace 字段，不新建独立表。**

理由:
1. `AgentSession` 已经是 "一次 Run 的执行会话" — workspace 是这次执行的隔离环境，属于 session 的自然维度
2. FK 链 `project_id → task_id → run_id` 已存在，不需要重复建立
3. agent-orchestrator 也是在一个 Session 对象上承载 session/runtime/workspace 三维信息
4. 所有 P1 字段仍然 nullable，保持与 P0 相同的渐进增强模式
5. 新建表会增加 JOIN 复杂度，且概念上是 1:1 关系，不应拆表

**例外**: 如果未来需要支持 "一个 session 多 worktree"（如并行修改多个仓库），那时才应独立建模。但 P1 不需要。

### 2.4 P1 字段清单 (AgentSession 扩展)

```
P1-A (workspace identity):   workspace_type, workspace_path, base_branch
P1-B (workspace lifecycle):  workspace_status, worktree_created_at
P1-C (cleanup):              cleanup_status, worktree_cleaned_at, last_workspace_error
```

---

## 3. Agent Orchestrator 可复用机制

### 3.1 workspace-worktree 插件机制

agent-orchestrator 的 workspace worktree 插件 (`workspace-worktree/src/index.ts`) 提供了完整的 worktree 生命周期:

```typescript
// create: git worktree add + git checkout -b
async function create(config): Promise<WorkspaceInfo> {
  // 1. fetch origin
  // 2. try checkout existing branch → 如果存在就复用
  // 3. git worktree add --detach <path>
  // 4. git checkout -b <branch>
  // 5. return WorkspaceInfo { path, branch, sessionId, projectId }
}

// destroy: git worktree remove + branch cleanup
async function destroy(workspacePath): Promise<void> {
  // 1. git worktree remove <path>
  // 2. git branch -D <branch>
}

// findManagedWorkspace: check if worktree already exists for this branch
async function findManagedWorkspace(config): Promise<WorkspaceInfo | null> {
  // 1. git worktree list --porcelain
  // 2. match by branch name
}
```

### 3.2 可复用点

| 机制 | 借鉴程度 | AI-Dev 适配方式 |
|------|---------|---------------|
| `git worktree add --detach` + `git checkout -b` 两阶段创建 | ⭐⭐⭐⭐⭐ | 直接借鉴。先 detach 创建隔离目录，再 checkout 新分支。 |
| `git worktree list --porcelain` 检测已存在 worktree | ⭐⭐⭐⭐⭐ | 直接借鉴。防止重复创建。 |
| `git worktree remove` + retry (Windows 兼容) | ⭐⭐⭐⭐ | 借鉴 remove + 重试逻辑。 |
| `WorkspaceCreateConfig { projectId, sessionId, branch, worktreeDir }` | ⭐⭐⭐⭐ | 用现有 `RepositoryWorkspace.root_path` + AgentSession.id 构造 worktree 路径。 |
| `WorkspaceInfo { path, branch, sessionId, projectId }` | ⭐⭐⭐⭐ | 映射到 AgentSession.workspace_path + workspace_type。 |
| SessionManager 中的 CleanupStack | ⭐⭐⭐⭐ | 创建 worktree 失败时回滚 (remove worktree + delete branch)。 |
| lifecycle-manager 中的 `readWorkspaceBranch()` | ⭐⭐⭐ | 读取 worktree 的当前分支检测是否漂移。 |
| workspace 的 `preflight()` 检查 | ⭐⭐⭐ | 创建前检查: .git 存在、origin 可访问、无同名 branch 冲突。 |
| Clone workspace 模式 (独立 clone) | ⭐⭐ | P1 不需要。worktree 更轻量。 |
| `findManagedWorkspace()` | ⭐⭐ | P1 暂不需要。P1 以创建新 worktree 为主。 |

### 3.3 不适合照搬的

| 机制 | 原因 |
|------|------|
| 插件注册/发现系统 (PluginRegistry) | AI-Dev 不需要插件市场 |
| workspace hooks (postCreate, symlinks) | AI-Dev 的工作区 setup 简单得多 |
| Windows PTY 兼容 | AI-Dev 当前仅需支持 macOS/Linux |
| workspace agent hooks setup (setupWorkspaceHooks) | 涉及 Claude Code PostToolUse hook，P1 不需要 |

---

## 4. P1 最小数据模型建议

### 4.1 直接补到 AgentSession 的字段 (P1-A: workspace identity)

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `workspace_type` | `WorkspaceType` enum, nullable | `None` | 当前填 `IN_PLACE`。创建 worktree 时填 `WORKTREE` |
| `workspace_path` | text, nullable | `None` | 当前填 `RepositoryWorkspace.root_path`。创建 worktree 时填实际路径 |
| `base_branch` | varchar(200), nullable | `None` | 从 `RepositoryWorkspace.default_base_branch` 复制。不可变 |
| `branch_name` | varchar(200), nullable | `None` | P0 已有。创建 worktree 后从 `git branch --show-current` 获取 |

### 4.2 直接补到 AgentSession 的字段 (P1-B: workspace lifecycle)

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `workspace_status` | varchar(40), nullable | `None` | not_created / creating / ready / dirty / cleannup_pending / cleaned / failed |
| `worktree_created_at` | datetime, nullable | `None` | worktree 创建成功的时间 |

### 4.3 直接补到 AgentSession 的字段 (P1-C: cleanup)

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `cleanup_status` | varchar(40), nullable | `None` | not_needed / pending / completed / failed |
| `worktree_cleaned_at` | datetime, nullable | `None` | worktree 清理成功的时间 |
| `last_workspace_error` | text, nullable | `None` | 最近一次创建/清理/操作失败的详细错误信息 |

### 4.4 应该新增独立模型的字段

**P1 不需要。** 所有 workspace 字段放 AgentSession 即可。独立表在 P1 阶段是过度设计。

### 4.5 暂时不做的字段

| 字段 | 原因 |
|------|------|
| `worktree_git_state_json` | ChangeSession 已覆盖 dirty file 检测 |
| `worktree_resource_usage` | P1 不需要资源监控 |
| `worktree_lock_holder` | P1 没有并发 worktree 冲突场景 |
| `base_commit_sha` | ChangeSession 已覆盖 |
| `pr_number`, `pr_url`, `ci_status`, `review_decision` | P2 字段，P1 不做 |

---

## 5. P1 最小服务设计

### 5.1 建议新增的服务

#### A. CodingWorkspaceService — P1 核心服务 (P1-C/D 创建)

```
职责: 管理 per-AgentSession 的隔离 worktree 生命周期

输入:
  - agent_session_id: UUID
  - project_id: UUID
  - workspace_type: WorkspaceType  (WORKTREE)

输出:
  - AgentSession (已填充 workspace_path, workspace_type, workspace_status,
    branch_name, base_branch, worktree_created_at)

只读/写入边界:
  - 只读: 读取 RepositoryWorkspace (获取 root_path, default_base_branch)
  - 只读: git worktree list --porcelain (检测已有 worktree)
  - 写入: git fetch origin
  - 写入: git worktree add --detach <path>
  - 写入: git checkout -b <branch_name>
  - 写入: 更新 AgentSession P1 workspace 字段

是否调用 git: 是 (fetch, worktree add, checkout -b)
出错回滚: 删除已创建的 worktree (git worktree remove)，删除已创建的分支 (git branch -D)
是否需要用户确认: P1-D 阶段需要 (用户审批 CommitCandidate 后)
```

#### B. BranchNamePolicy — P1 辅助服务 (P1-B 创建)

```
职责: 生成可预测、安全、可清理的 per-session 分支名

输入:
  - project_prefix: str (项目 ID 派生)
  - agent_session_id: UUID

输出:
  - branch_name: str  (如 "session/proj-<short>-<session_short>")

规则:
  - 格式: session/<project_short>-<session_uuid_short>
  - 示例: session/ai-dev-orc-a1b2c3d4
  - 必须使用 git-safe 字符 (字母/数字/./-/_)
  - 前 8 位 UUID 作为唯一性保证
  - 长度 ≤ 50 字符 (git branch name limit 255)

是否调用 git: 否 (纯字符串计算)
```

#### C. WorktreePlanService — P1 dry-run 服务 (P1-C 创建)

```
职责: 在执行真实 git 操作前做 dry-run 检查，生成 WorktreePlan

输入:
  - Project 的 RepositoryWorkspace
  - agent_session_id: UUID

输出:
  - WorktreePlan {
      safe: bool,
      worktree_path: str,
      branch_name: str,
      base_branch: str,
      base_commit_sha: str,
      blocking_reasons: list[str],
      git_commands_to_run: list[str],  # 只展示，不执行
    }

检查:
  - .git 存在
  - origin 可访问 (git fetch --dry-run)
  - 无同名 branch (git branch --list)
  - worktree 路径不在允许范围外
  - worktree 路径不覆盖已有文件/目录
  - base_branch 可解析 (git rev-parse origin/<base>)
  - 主仓库不 dirty (ChangeSession.workspace_status)

是否调用 git: 是 (只读命令: fetch --dry-run, rev-parse, branch --list, status)
出错回滚: N/A (纯 dry-run, 无副作用)
是否需要用户确认: 否 (dry-run 是确认前的检查步骤)
```

#### D. WorkspaceCleanupService — P1 cleanup 服务 (P1-E 创建)

```
职责: 安全清理 per-session worktree 和关联分支

输入:
  - agent_session_id: UUID
  - workspace_path: str
  - branch_name: str

输出:
  - cleanup_result: { success: bool, cleaned: bool, errors: list[str] }

清理步骤:
  1. 验证路径属于系统管理的 worktree 目录 (安全检查)
  2. git worktree remove --force <path>
  3. git branch -D <branch_name>
  4. 更新 AgentSession.workspace_status = "cleaned"
  5. 更新 AgentSession.cleanup_status = "completed"
  6. 更新 AgentSession.worktree_cleaned_at

失败处理:
  - worktree remove 失败 → 记录 last_workspace_error, cleanup_status = "failed"
  - branch delete 失败 → 记录但不清除 (leave stale branch, manual cleanup)
  - 只清理系统创建的 worktree (路径前缀检查)

是否调用 git: 是 (worktree remove, branch -D)
是否需要用户确认: 否 (cleanup 是自动操作，但应记录审计)
```

#### E. WorkspaceGuardService — P1 安全服务 (P1-C 创建)

```
职责: 验证 worktree 操作的安全性，防止路径穿越和意外覆盖

输入:
  - workspace_path: str
  - allowed_root: str (从 RepositoryWorkspaceSettingsService 获取)
  - branch_name: str

输出:
  - guard_result: { safe: bool, reasons: list[str] }

检查:
  - workspace_path 在 allowed_root 下
  - branch_name 符合 git ref 规范
  - 无路径穿越 (../)
  - 无 shell 注入字符
  - worktree 路径不与已有 worktree 冲突
  - worktree 路径不包含主仓库路径

是否调用 git: 否 (纯路径验证)
```

### 5.2 不需要新增的服务

| 不需要的服务 | 原因 |
|------------|------|
| WorktreeManager (万能管理器) | 过度设计。按职责拆分到 CodingWorkspaceService / WorktreePlanService / WorkspaceCleanupService 即可 |
| RuntimeManager | P1 不改 runtime 模型。当前 subprocess 足够 |
| WorkspacePool | 无并发 worktree 管理需求 |

---

## 6. Git 命令边界

### 6.1 P1 允许的 git 只读命令 (P1-A/B/C 阶段)

```
git worktree list --porcelain     # 检测已有 worktree
git fetch --dry-run               # 检查 origin 可访问性
git branch --list <name>          # 检查分支是否已存在
git rev-parse origin/<base>       # 解析基线 commit
git rev-parse HEAD                # 获取当前 commit SHA
git status --porcelain=v1         # 检查主仓库 dirty 状态
git symbolic-ref --short HEAD     # 读取当前分支名
git remote get-url origin         # 验证 remote
```

### 6.2 P1 允许的 git 写入命令 (P1-D/E 阶段, 需要用户确认)

```
git worktree add --detach <path>  # 创建隔离工作区
git checkout -b <branch_name>     # 在 worktree 中创建分支
git worktree remove --force <path> # 移除工作区 (cleanup)
git branch -D <branch_name>       # 删除分支 (cleanup)
git fetch origin                  # 同步远程引用
```

### 6.3 P1 明确不允许的 git 命令

```
git add                          # 不在 worktree 内做文件变更
git commit                       # 不在 P1 做提交
git push                         # 不推送
git push --force                 # 绝不
gh pr create                     # 不创建 PR
git merge                        # 不合并
git rebase                       # 不变基
git stash                        # 不 stash
git reset --hard                 # 不强制重置
git clean -fd                    # 不清理 worktree 内文件
git checkout <existing_branch>   # 不切换已有分支
```

**核心边界**: P1 只做 "创建隔离环境" 和 "清理隔离环境"。不做任何代码修改、提交或推送。

---

## 7. 安全边界

### 7.1 Worktree 路径安全

```
1. worktree_root = <allowed_workspace_root>/worktrees/
   (从 RepositoryWorkspaceSettingsService 获取 allowed_workspace_root)

2. worktree_path = worktree_root/<session_id_short>/
   示例: /Users/kk/projects/.worktrees/a1b2c3d4/

3. 验证步骤:
   - worktree_path.resolve() 必须在 worktree_root.resolve() 下
   - worktree_path 不能等于或包含主仓库路径
   - worktree_path 不能存在于 git worktree list 中 (除非是同一个 session 的 restore)
   - worktree_path 不能是已存在的非空目录
```

### 7.2 Branch name 安全

```
规则:
  - 格式: session/<project_prefix>-<uuid_short>
  - 允许字符: [a-zA-Z0-9._/-]  (git ref 安全子集)
  - 禁止: shell 元字符 (!@#$%^&*(){}[]|;'"<>?~`)
  - 禁止: .. (路径穿越)
  - 禁止: - (leading dash)
  - 长度: ≤ 50 (保守, git limit 255)
  - 通过正则验证: ^session/[a-z][a-z0-9._-]{0,47}[a-z0-9]$

生成策略:
  - project_prefix = basename(repository_path).lower()[:8]
  - uuid_short = str(agent_session_id).replace('-', '')[:8]
  - branch = f"session/{project_prefix}-{uuid_short}"
```

### 7.3 操作安全

```
创建前检查 (all-or-nothing):
  1. 主仓库 .git 存在
  2. 主仓库不 dirty (ChangeSession.workspace_status = CLEAN)
  3. base_branch 可解析
  4. worktree 路径安全 (在允许范围内)
  5. 无同名 branch 冲突
  6. 无同名 worktree 路径冲突

清理前检查:
  1. worktree 路径属于系统管理的 worktrees 目录
  2. 不删除主仓库路径
  3. 不删除非系统创建的目录

审计要求:
  - 所有 worktree 操作记录到 AgentSession.last_workspace_error
  - worktree 创建时间记录到 AgentSession.worktree_created_at
  - worktree 清理时间记录到 AgentSession.worktree_cleaned_at
```

---

## 8. 失败与回滚

### 8.1 创建失败场景

| 场景 | 检测方式 | 回滚动作 | 记录 |
|------|---------|---------|------|
| origin 不可访问 | `git fetch --dry-run` 失败 | 无需回滚 (未创建任何东西) | `last_workspace_error = "origin unreachable: {error}"` |
| base_branch 不可解析 | `git rev-parse origin/<base>` 失败 | 无需回滚 | `last_workspace_error = "base branch not found: {base}"` |
| branch 名已存在 | `git branch --list` 返回非空 | 无需回滚 | `last_workspace_error = "branch already exists: {name}"` |
| worktree 路径已存在 | `os.path.exists(worktree_path)` | 无需回滚 | `last_workspace_error = "worktree path exists: {path}"` |
| worktree add 失败 (中途) | `git worktree add` 抛出异常 | `git worktree remove --force` (如果目录已创建) | `last_workspace_error = "worktree add failed: {error}"` |
| checkout -b 失败 | `git checkout -b` 抛出异常 | `git worktree remove --force` + `git branch -D` (如果已创建) | `last_workspace_error = "branch create failed: {error}"` |

### 8.2 清理失败场景

| 场景 | 回滚动作 | 记录 |
|------|---------|------|
| worktree remove 失败 | 不删除分支 (leave stale, manual cleanup) | `cleanup_status = "failed"`, `last_workspace_error = "worktree remove failed: {error}"` |
| branch -D 失败 | 无影响 (worktree 可能已删除或不存在) | 追加 `last_workspace_error`，但 `cleanup_status` 可标 `completed` |
| worktree 路径不存在 | 跳过 (可能已手动清理) | `cleanup_status = "completed"` (idempotent) |

### 8.3 创建流程伪代码 (含回滚)

```python
def create_worktree_for_session(agent_session, repository_workspace):
    worktree_path = _compute_worktree_path(agent_session.id)
    branch_name = _generate_branch_name(agent_session.id)
    cleanup_actions = []
    try:
        # Step 1: Preflight
        _check_origin_accessible(repository_workspace.root_path)
        _check_branch_available(repository_workspace.root_path, branch_name)
        _check_worktree_path_available(worktree_path)
        _check_main_repo_clean(repository_workspace.root_path)
        _check_base_branch_resolvable(
            repository_workspace.root_path,
            repository_workspace.default_base_branch,
        )
        # Step 2: Fetch
        _git_fetch(repository_workspace.root_path)
        # Step 3: Create worktree
        _git_worktree_add_detach(
            repository_workspace.root_path,
            worktree_path,
            repository_workspace.default_base_branch,
        )
        cleanup_actions.append(("worktree", worktree_path))
        # Step 4: Create branch
        _git_checkout_new_branch(worktree_path, branch_name)
        cleanup_actions.append(("branch", branch_name))
        # Step 5: Update AgentSession
        _update_agent_session_workspace_fields(
            agent_session,
            workspace_type=WorkspaceType.WORKTREE,
            workspace_path=worktree_path,
            base_branch=repository_workspace.default_base_branch,
            branch_name=branch_name,
            workspace_status="ready",
            worktree_created_at=utc_now(),
        )
    except Exception as e:
        # Rollback in reverse order
        for action_type, action_target in reversed(cleanup_actions):
            try:
                if action_type == "worktree":
                    _git_worktree_remove(action_target)
                elif action_type == "branch":
                    _git_branch_delete(repository_workspace.root_path, action_target)
            except Exception:
                pass
        _update_agent_session_workspace_fields(
            agent_session,
            workspace_status="failed",
            last_workspace_error=str(e)[:2000],
        )
        raise
```

---

## 9. P1 分阶段路线

### P1-A: 只读审计与设计文档 (本次) ✅

**产出**: 本文档
**验证**: 全量代码搜索确认无 worktree/branch 写操作

### P1-B: 数据模型字段 + 只读 API (最小代码任务)

**范围**:
- `AgentSession` 新增 8 个 P1 nullable 字段: workspace_type, workspace_path, base_branch, workspace_status, worktree_created_at, cleanup_status, worktree_cleaned_at, last_workspace_error
- `AgentSessionTable` 新增 8 个 nullable columns
- `AgentSessionRepository` 支持创建/更新这些字段
- `AgentSessionResponse` 透传这些字段
- `WorkerRunOnceResponse` 透传这些字段
- **新增仅存在于 Test 层的 BranchNamePolicy 和 WorktreeGuardService 单元测试** (dry-run only, no git)

**不改**: 不创建 worktree, 不调用 git write

**测试**: 8+ 单元测试 (model/ORM/repository/API DTO round-trip)

### P1-C: WorktreePlan dry-run / plan (最小服务)

**范围**:
- `WorktreePlanService`: 只读检查 + 生成 WorktreePlan (dry-run only)
- `WorktreeGuardService`: 路径安全检查
- `BranchNamePolicy`: 分支名生成策略
- API: `POST /agent-sessions/{id}/workspace-plan` (dry-run)
- API: `GET /agent-sessions/{id}/workspace-plan` (readback)

**不改**: 不执行 git write, 不创建 worktree

**测试**: 用真实本地仓库做 dry-run 测试

### P1-D: 用户确认后真实创建 (需要用户确认)

**范围**:
- `CodingWorkspaceService.create_worktree()`: 真实 git worktree add + checkout -b
- API: `POST /agent-sessions/{id}/workspace` (创建 worktree + branch)
- `AgentSession` workspace 字段填充

**前提**: `CommitCandidate.status` 需要新增 `CONFIRMED` 状态，且用户已完成人工确认

**测试**: 需要真实 GitHub 仓库 (已配置 remote)，至少 1 个 smoke test

### P1-E: Cleanup 与恢复

**范围**:
- `WorkspaceCleanupService`: 安全清理 worktree + branch
- API: `DELETE /agent-sessions/{id}/workspace` (清理)
- `git worktree remove --force` + `git branch -D`

**测试**: 创建 → 使用 → 清理 全链路测试

### P1-F: 前端只读展示串联

**范围**:
- `ExecutionRepositoryTab` 展示 AgentSession workspace 状态
- `AgentThreadPanel` 展示 worktree 路径和分支信息
- Coding Session 详情面板展示 workspace lifecycle

**不改**: 不提供前端创建/清理按钮 (这些通过 API 手动触发或以 workflow 形式执行)

---

## 10. 第一条 Codex 最小代码任务建议

### 建议任务: P1-B 数据模型字段 + 只读 API

```
任务: AgentSession P1 workspace 字段扩展

范围:
  - AgentSession 新增 8 个 nullable 字段:
    workspace_type, workspace_path, base_branch, workspace_status,
    worktree_created_at, cleanup_status, worktree_cleaned_at,
    last_workspace_error

  - AgentSessionTable 新增 8 个 nullable columns (String/Text/DateTime)

  - AgentSessionRepository:
    · create 接受 8 个新字段 (全部 optional, 默认 None)
    · update_status 接受 8 个新字段 (全部 optional)
    · _to_domain 回读 8 个新字段

  - AgentSessionResponse (agent_threads.py): 透传 8 个新字段
  - WorkerRunOnceResponse (workers.py): 透传 8 个新字段 (string)

  - 新增 BranchNamePolicy (纯计算, 无 git):
    · generate(project_prefix, session_id) → branch_name
    · validate(branch_name) → bool

  - 新增 WorktreeGuardService (纯验证, 无 git):
    · validate_path(worktree_path, allowed_root) → GuardResult
    · validate_branch_name(branch_name) → bool

  - tests/test_agent_session_p1_workspace_fields.py: 8+ 测试
    · DB columns exist
    · Repository round-trip
    · BranchNamePolicy generate/validate
    · WorktreeGuardService validate_path/validate_branch_name

边界:
  - 不创建 worktree
  - 不调用 git
  - 不调用 fetch
  - 不新增 API endpoint (只扩展 response DTO)
  - 不改前端
  - 字段全部 nullable

验收: pytest runtime/orchestrator/tests/test_agent_session_p1_workspace_fields.py -q
```

### 为什么选 P1-B 而不是 P1-C

1. **P1-B 是纯数据模型层**: 不动 git, 不出错, 不会影响主仓库
2. **P1-B 是 P1-C 的前置依赖**: WorktreePlanService 的干跑检查结果需要字段来存储
3. **BranchNamePolicy 和 WorktreeGuardService 是后续安全的基础**: 先建立安全规则, 再执行 git 操作
4. **P1-B 保持与 P0 相同的渐进模式**: 字段先存在, 后填充

---

## 11. 明确不建议现在做的事

| 不建议 | 原因 |
|--------|------|
| 接 Claude Code runtime | P1 只做 worktree/branch 隔离, 不改 runtime 模型 |
| 自动改代码 | `git add` / `git commit` 是后续阶段的事 |
| 自动 apply patch | 需要完整的审批→确认→执行→验证链路 |
| 自动 git commit | 需要 CommitCandidate CONFIRMED 状态 |
| git push | 需要 SCM 集成 (P2) |
| 创建 PR (gh pr create) | 需要 SCM 集成 (P2) |
| 接 CI | 需要 SCM 集成 (P2) |
| 接 review comments | 需要 SCM 集成 (P2) |
| 插件生态 | AI-Dev 不需要插件系统 |
| 大规模重构前端 | P1 是后端基础设施 |
| WorktreePool / 并发管理 | 无并发需求 |
| 自动创建 agent tmux session | P1 只做 worktree, 不改 runtime |
| session restore (恢复已有 worktree) | P1-E cleanup 之后再做 |
| 把 AI Project Director 总闭环标记为 Pass | 总闭环仍为 Partial |

---

## 12. 总结

### 当前已有能力

| 能力 | 状态 |
|------|------|
| 项目级仓库绑定 (RepositoryWorkspace, read_only) | ✅ 完整 |
| 只读仓库扫描 (RepositorySnapshot) | ✅ 完整 |
| 只读 Git 状态检测 (ChangeSession, BranchSessionService) | ✅ 完整 |
| 变更链路数据建模 (ChangePlan → ChangeBatch → CommitCandidate draft) | ✅ 完整 |
| 受控本地 Git 写入 (LocalGitWriteService, guard-protected) | ✅ 完整 |
| P0 coding session 字段 (agent_type, runtime_type, coding_status, activity_state, branch_name) | ✅ 完整 |
| WorkspaceType 枚举 (WORKTREE, CLONE, IN_PLACE, READ_ONLY) | ✅ 枚举已定义 |

### 当前缺口

| 缺口 | 严重程度 | P |
|------|---------|---|
| AgentSession 无 workspace 字段 (workspace_type, workspace_path 等) | 阻塞 | P1 |
| 无 worktree 创建/清理机制 | 阻塞 | P1 |
| 无 per-session 分支创建/删除 | 阻塞 | P1 |
| 无 WorktreePlan dry-run 能力 | 阻塞 | P1 |
| 无 BranchNamePolicy | 阻塞 | P1 |
| 无安全验证层 (WorktreeGuardService) | 阻塞 | P1 |
| 无 cleanup 机制 | 阻塞 | P1 |
| CommitCandidate 只有 DRAFT 状态 | 阻塞 | P1-D 需要新增 CONFIRMED + APPLIED |
| RepositoryAccessMode 只有 READ_ONLY | 阻塞 | P1-D 需要新增 READ_WRITE |

### P1 最小路线

```
P1-A (本次) ✅ 设计审计文档
P1-B → AgentSession 8 字段 + BranchNamePolicy + WorktreeGuardService (只读)
P1-C → WorktreePlan dry-run (只读 git check)
P1-D → 用户确认后真实创建 worktree + branch
P1-E → Cleanup 与恢复
P1-F → 前端只读展示
```

### 下一条建议给 Codex 的最小任务

**P1-B**: AgentSession workspace 字段扩展 (8 字段 + 2 纯计算服务)，不改 git，不上线。

### Gate 结论

- **Worktree / Branch P1 设计审计**: **Pass** ✅
  - 审计了 24 个文件 (AI-Dev 17 + agent-orchestrator 7)
  - 确认当前无 worktree/branch 创建能力
  - 明确了 AgentSession P1 字段清单 (8 个)、P1 服务设计 (5 个服务)、Git 命令边界、安全策略、失败回滚
  - 给出了 P1-B 到 P1-F 的分阶段路线

- **AI Project Director 总闭环**: **仍为 Partial**
  - P0 字段已实现 (Pass)
  - P1 worktree/branch 设计完成 (Pass) 但未实现
  - P2 SCM 集成尚未设计
  - 真实 provider 运行尚未验证

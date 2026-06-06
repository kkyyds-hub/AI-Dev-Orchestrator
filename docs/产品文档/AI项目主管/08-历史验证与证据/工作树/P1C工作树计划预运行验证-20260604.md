# Coding Session P1-C Worktree Plan dry-run 验证

> **文档类型**: 运行证据验证
> **生成日期**: 2026-06-04
> **验证基准 commit**: `009c1fb75a4b8aeeef5a8cc86a19d35428a292b4` (feat: add worktree plan dry run)
> **前置设计基线**: `docs/product/ai-project-director/worktree-branch-p1-design-audit-20260604.md`
> **P0 验证**: `docs/product/ai-project-director/verification-coding-session-p0-fields-20260604.md`
> **验证模型**: DeepSeek (Claude Code CLI)
> **状态**: Pass

---

## 1. 验证基准

| 项目 | 值 |
|------|-----|
| origin/main HEAD | `009c1fb75a4b8aeeef5a8cc86a19d35428a292b4` |
| 提交信息 | `feat: add worktree plan dry run` |
| 验证时间 | 2026-06-04 |
| 变更文件数 | 4 files (+440 −2) |

---

## 2. 新增/修改文件清单

| 文件 | 新增 | 变更 | 说明 |
|------|------|------|------|
| `runtime/orchestrator/app/domain/worktree_plan.py` | ✨ 新增 | — | WorktreePlan 领域模型 |
| `runtime/orchestrator/app/services/worktree_plan_service.py` | ✨ 新增 | — | WorktreePlanService + BranchNamePolicy + WorktreeGuardService |
| `runtime/orchestrator/app/api/routes/agent_threads.py` | — | ✅ 变更 | 新增 WorktreePlanResponse + 2 个 endpoint |
| `runtime/orchestrator/tests/test_worktree_plan_dry_run.py` | ✨ 新增 | — | 6 个测试 |

---

## 3. WorktreePlan 字段清单

| 字段 | 类型 | 说明 | 验证状态 |
|------|------|------|---------|
| `agent_session_id` | UUID | 关联的 AgentSession | ✅ |
| `project_id` | UUID | 关联的项目 | ✅ |
| `repository_workspace_id` | `UUID \| None` | 仓库工作区 ID (无绑定时 None) | ✅ |
| `safe` | bool | 是否所有 guard 通过 | ✅ |
| `workspace_type` | str | 固定为 `"worktree"` | ✅ |
| `worktree_path` | `str \| None` | 规划的工作区路径 | ✅ |
| `branch_name` | `str \| None` | 规划的分支名 | ✅ |
| `base_branch` | `str \| None` | 基线分支 (来自 RepositoryWorkspace) | ✅ |
| `base_commit_sha` | `str \| None` | 基线提交 SHA (当前始终 None) | ✅ (P1-C 设计如此) |
| `git_commands_to_run` | `list[str]` | 未来执行的命令预览 (不执行) | ✅ |
| `blockers` | `list[str]` | 阻塞原因列表 | ✅ |
| `warnings` | `list[str]` | 警告信息列表 | ✅ |

---

## 4. API Endpoint 清单

| Method | Path | Purpose | 验证状态 |
|--------|------|---------|---------|
| `POST` | `/agent-threads/sessions/{session_id}/workspace-plan` | 生成并返回 dry-run plan | ✅ |
| `GET` | `/agent-threads/sessions/{session_id}/workspace-plan` | 重新计算并返回 dry-run plan (不改变状态) | ✅ |

**命名验证**: endpoint 使用 `workspace-plan` (名词)，不是 `workspace` 或 `create-workspace`。response 定义为 "pure dry-run plan"，summary 明确说明 "no git command or filesystem write is executed"。

---

## 5. dry-run 边界证明

### 5.1 代码级证明

**WorktreePlanService** (`worktree_plan_service.py`):

```
分析: 整个模块 import 清单不含 subprocess, os.system, pathlib.Path().write
     不含任何 ORM commit/flush 调用
     不含任何 AgentSession update

纯计算步骤:
  1. AgentSessionRepository.get_by_id()        ← 只读 DB 查询
  2. RepositoryWorkspaceRepository.get_by_project_id() ← 只读 DB 查询
  3. Path.exists() / Path.is_dir()              ← 只读文件系统
  4. Path.iterdir()                              ← 只读文件系统
  5. BranchNamePolicy.generate()                 ← 纯字符串计算
  6. WorktreeGuardService.validate_path()        ← 纯路径计算
  7. WorktreeGuardService.validate_branch_name() ← 纯正则验证
  8. shlex.quote()                               ← 纯字符串转义 (用于预览)

输出: WorktreePlan 实例 (不可变 Pydantic model)
```

**关键发现**: `git_commands_to_run` 中的命令**仅**在 `_build_plan_payload()` 中通过 `shlex.quote()` 组装为字符串，**不传入** `subprocess.run()` 或 `os.system()`。

**Grep 验证**:
```
rg "subprocess|os\.system" worktree_plan_service.py worktree_plan.py → 无匹配
rg "git worktree add" — 仅匹配到预览字符串组装代码，非执行代码
rg "git checkout -b" — 仅匹配到 preview 字符串中
```

### 5.2 不执行的操作确认

| 操作 | 是否执行 | 证据 |
|------|---------|------|
| `git worktree add` | ❌ 不执行 | 仅出现在 `git_commands_to_run` 列表中作为字符串 |
| `git checkout -b` | ❌ 不执行 | 同上 |
| `git branch` (创建/删除) | ❌ 不执行 | 无调用 |
| `git commit` | ❌ 不执行 | 无调用 |
| `git push` | ❌ 不执行 | 无调用 |
| `gh pr create` | ❌ 不执行 | 无调用 |
| `subprocess.run()` | ❌ 不执行 | 无 import，无调用 |
| `os.system()` | ❌ 不执行 | 无 import，无调用 |
| `Path.mkdir()` | ❌ 不执行 | 无目录创建调用 |
| AgentSession update | ❌ 不执行 | 不调用 `agent_session_repository.update_status()` |
| RepositoryWorkspace update | ❌ 不执行 | 不调用 `repository_workspace_repository.upsert()` |
| DB commit/flush | ❌ 不执行 | 无 flush/commit 调用 |

---

## 6. Blockers / Warnings 规则清单

### 6.1 Blockers (阻塞 dry-run plan)

| 条件 | 触发位置 | 消息 |
|------|---------|------|
| 项目无仓库绑定 | `build_plan` L194-203 | "repository workspace is not bound for this project" |
| 分支名不安全 | `validate_branch_name` L86-92 | "invalid branch name: {name}" |
| 仓库根路径不存在 | `build_plan` L213-214 | "repository root path does not exist" |
| 仓库根路径无 .git | `build_plan` L215-216 | "repository root path does not contain .git" |
| worktree path 非绝对路径 | `validate_path` L109-110 | "worktree path must be absolute" |
| allowed root 非绝对路径 | `validate_path` L111-112 | "allowed workspace root must be absolute" |
| repository root 非绝对路径 | `validate_path` L113-114 | "repository root path must be absolute" |
| worktree path 等于 allowed root | `validate_path` L122-123 | "worktree path cannot equal allowed workspace root" |
| worktree path 在 allowed root 外 | `validate_path` L124-125 | "worktree path is outside allowed workspace root" |
| worktree path 在源仓库内 | `validate_path` L126-130 | "worktree path cannot be inside the source repository" |
| worktree path 包含源仓库 | `validate_path` L131-132 | "worktree path cannot contain the source repository" |
| worktree path 已存在且非空 | `validate_path` L141-142 | "worktree path already exists and is not empty" |
| worktree path 已存在且非目录 | `validate_path` L143-144 | "worktree path already exists and is not a directory" |

### 6.2 Warnings (不阻塞，但提示)

| 条件 | 触发位置 | 消息 |
|------|---------|------|
| worktree path 已存在为空目录 | `validate_path` L139-140 | "worktree path already exists as an empty directory" |
| session 已有 branch_name | `build_plan` L230-233 | "agent session already has a branch_name; dry-run plan will not mutate it" |
| session 已有 workspace_path | `build_plan` L234-237 | "agent session already has a workspace_path; dry-run plan will not mutate it" |

---

## 7. 测试覆蓋

### 7.1 测试结果

```
$ python -m pytest runtime/orchestrator/tests/test_worktree_plan_dry_run.py \
    runtime/orchestrator/tests/test_agent_session_p0_coding_fields.py -q

20 passed in 0.46s
```

| 测试 | 验证内容 | 结果 |
|------|---------|------|
| `test_branch_name_policy_generates_stable_safe_session_branch` | 分支名稳定、安全、可重复 | ✅ PASS |
| `test_branch_name_policy_rejects_unsafe_branch_names` | 8 种 unsafe 分支名被拒绝 | ✅ PASS |
| `test_worktree_guard_blocks_path_outside_allowed_root` | 路径在允许范围外被 blocker | ✅ PASS |
| `test_worktree_guard_blocks_path_inside_source_repository` | 路径在源仓库内被 blocker | ✅ PASS |
| `test_worktree_plan_blocks_missing_repository_workspace_binding` | 无仓库绑定时 safe=False + `git_commands_to_run` 为空 | ✅ PASS |
| `test_worktree_plan_generates_safe_dry_run_for_bound_repository` | 有绑定时生成完整 plan + 2 条预览命令 | ✅ PASS |
| `test_worktree_plan_response_exposes_dry_run_fields` | API DTO 正确透传所有字段 | ✅ PASS |
| P0 tests (13 个) | P0 AgentSession 字段、Repository、Service、API | ✅ PASS |

### 7.2 补充验证

```
$ python -m compileall -q runtime/orchestrator/app runtime/orchestrator/tests
(no output — all files compiled successfully)

$ git diff --check
(no output — no whitespace issues)
```

---

## 8. 未触发项确认

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 未创建 worktree | ✅ | 无 `git worktree add` 执行，无 `Path.mkdir()` 调用 |
| 未创建 branch | ✅ | 无 `git branch` 执行 |
| 未执行 git write | ✅ | 无任何 git 写命令执行 |
| 未运行 worker | ✅ | 无 TaskWorker 调用 |
| 未启动服务 | ✅ | 所有测试使用 `tmp_path` 隔离 SQLite |
| 未改前端 | ✅ | 4 个变更文件全部在 `runtime/orchestrator/` 下 |
| 未创建 PR | ✅ | 无 `gh pr` 调用 |
| 未触发 apply-local | ✅ | 无 `local_git_write_service` import |
| 未触发 git-commit | ✅ | 无 git commit 调用 |
| 未修改 AgentSession | ✅ | WorktreePlanService 不调用 update_status |
| 未修改 RepositoryWorkspace | ✅ | 不调用 upsert |

---

## 9. 已发现缺口

### 9.1 设计级缺口 (P1-D 前需要解决)

| 缺口 | 严重程度 | 建议 |
|------|---------|------|
| **无 `requires_user_confirmation` 字段** | P1-D 前置 | `WorktreePlan` 缺少一个明确标记 "此 plan 需要用户确认后才能执行" 的布尔字段。当前由前端/调用方自行判断 safe=True 时是否需要确认。建议在 P1-D 创建 WorktreePlan 时新增此字段 |
| **无 `dry_run` 标记字段** | 低 | `WorktreePlan` 本身隐含 dry-run 语义 (名称 "Plan", API summary 说明)，但模型中无显式的 `dry_run: bool` 字段。当前命名已足以防止误用 |
| **`base_commit_sha` 始终为 None** | P1-D 前置 | P1-C 不调用 `git rev-parse`，因此无法填充 base_commit_sha。P1-D 真实执行前需要调用 `git rev-parse origin/<base>` 填充 |
| **缺少 workspace root 配置项可读性验证** | 中 | `WorktreeGuardService` 依赖 `RepositoryWorkspace.allowed_workspace_root` 已正确配置。如果配置错误 (如允许根目录为 `/`)，计划会不安全。当前需要运营侧保证正确配置 |
| **缺少 cleanup 计划** | P1-E 前置 | 当前只规划创建，不规划清理。P1-E 时需要 `WorktreeCleanupPlan` 或类似模型 |
| **缺少 idempotency guard** | P1-D 前置 | 如果同一个 session 重复调用 POST workspace-plan，每次都返回新 plan。P1-D 真实创建前需要检查 "session 是否已有 worktree" |

### 9.2 已正确处理的设计项

| 设计项 | 状态 |
|--------|------|
| 分支名安全策略 (BranchNamePolicy) | ✅ 完整 — 长度限制、字符验证、无空格、无 `..`、无 shell 特殊字符 |
| worktree path 安全边界 (WorktreeGuardService) | ✅ 完整 — 绝对路径、允许范围、不覆盖源仓库 |
| API 命名 (workspace-plan, 名词) | ✅ 清晰 — 不会与真实创建 API 混淆 |
| dry-run 语义 (不执行 git) | ✅ 已验证 — 无 subprocess.call/os.system |

---

## 10. Gate 结论

### Coding Session P1-C Worktree Plan dry-run 验证: **Pass** ✅

**证据**:
1. ✅ WorktreePlan 字段完整 (11 个字段)
2. ✅ WorktreePlanService 纯计算 — 无 subprocess, 无 os.system, 无 git write
3. ✅ API endpoint 命名清晰 (`workspace-plan`, 名词) + summary 明确说明 dry-run
4. ✅ BranchNamePolicy 安全 — 确定性、git-safe、无 shell 注入
5. ✅ WorktreeGuardService 安全 — 绝对路径检查、允许范围检查、源仓库冲突检查
6. ✅ 6 个测试覆盖: 正常 plan + 无绑定 blocker + 路径 blocker + 分支名安全 + DTO 透传
7. ✅ P0 测试全部通过 (13 tests)
8. ✅ compileall clean, git diff clean
9. ✅ 未创建 worktree, 未创建 branch, 未执行 git write
10. ✅ 不改 AgentSession, 不改 RepositoryWorkspace

### AI Project Director 总闭环: **仍为 Partial**

**原因**:
- P0 字段实现并验证通过 (Pass)
- P1-A 设计审计完成 (Pass)
- P1-C dry-run 验证通过 (Pass) — 但仅是 plan, 不是真实创建
- P1-D 真实 worktree 创建尚未实现
- P1-E cleanup 尚未实现
- P2 SCM 集成尚未实现
- 真实 provider 运行尚未验证

# Coding Session P1-D-D-2 preflight blocker tightening 验证

> **文档类型**: 运行证据验证
> **生成日期**: 2026-06-05
> **验证基准 commit**: `112b124` (Coding Session P1-D-D-2 preflight blocker tightening)
> **前置文档**:
> - `docs/product/ai-project-director/verification-worktree-prepare-p1dd-readonly-preflight-20260605.md`
> - `docs/product/ai-project-director/worktree-create-p1d-readiness-audit-20260604.md`
> **验证模型**: DeepSeek (Claude Code CLI)
> **状态**: Pass

---

## 1. 验证基准

| 项目 | 值 |
|------|-----|
| origin/main HEAD | `112b12450f4a044ead4637de346dd16b34943929` |
| 提交信息 | `Coding Session P1-D-D-2 preflight blocker tightening` |
| 验证时间 | 2026-06-05 |
| 变更 | 2 files (+92 −0) |

---

## 2. 新增/修改文件清单

| 文件 | 变更 | 说明 |
|------|------|------|
| `app/services/worktree_prepare_service.py` | 4 行新增 (L99-106) | 4 个新 blocker 条件 |
| `tests/test_worktree_plan_dry_run.py` | 88 行新增 | 4 个 parametrized test case + 新 conftest fixture |

---

## 3. blocker 规则清单 (完整)

### 3.1 新增 blocker (4 个)

| 条件 | blocker 消息 | 触发来源 |
|------|-------------|---------|
| `repository_is_git_worktree is False` | "repository root is not a git worktree" | `git rev-parse --is-inside-work-tree` 失败 |
| `repository_clean is False` | "repository has uncommitted changes" | `git status --porcelain` 非空 |
| `planned_branch_exists` | "planned branch already exists" | `git branch --list <planned>` 返回非空 |
| `planned_worktree_registered` | "planned worktree path is already registered" | `git worktree list --porcelain` 包含路径 |

### 3.2 全部 blocker (共 9 个)

```
1. "workspace prepare execution is not implemented in P1-D-D"  (始终)
2. plan.blockers (合并 plan 不安全的 blockers)
3. "workspace prepare only accepts dry-run plans"               (plan.dry_run=False)
4. "workspace prepare requires a user-confirmed plan"           (plan.requires_user_confirmation=False)
5. "repository workspace is not bound for this project"         (无绑定时)
6. "repository root is not a git worktree"                      (新增 P1-D-D-2)
7. "repository has uncommitted changes"                         (新增 P1-D-D-2)
8. "planned branch already exists"                              (新增 P1-D-D-2)
9. "planned worktree path is already registered"                (新增 P1-D-D-2)
```

### 3.3 参数化测试覆盖

```
@pytest.mark.parametrize("preflight_overrides,expected_blocker", [
    ({"repository_is_git_worktree": False}, "repository root is not a git worktree"),
    ({"repository_clean": False},           "repository has uncommitted changes"),
    ({"planned_branch_exists": True},       "planned branch already exists"),
    ({"planned_worktree_registered": True}, "planned worktree path is already registered"),
])
```

**每个 case 验证**:
- `prepare_status == "blocked"`
- `expected_blocker in result.blockers`
- `creates_worktree is False`
- `creates_branch is False`
- `runs_write_git is False`
- `mutates_agent_session_workspace is False`
- `unchanged_session.workspace_path is None`
- `unchanged_session.branch_name is None`

---

## 4. read-only Git Allowlist (更新后)

| Spec 方法 | argv | mutates_repository |
|-----------|------|--------------------|
| `git_rev_parse_is_inside_work_tree()` | `("git", "rev-parse", "--is-inside-work-tree")` | **False** |
| `git_rev_parse(ref="HEAD")` | `("git", "rev-parse", "HEAD")` | **False** |
| `git_status_porcelain()` | `("git", "status", "--porcelain")` | **False** |
| `git_worktree_list()` | `("git", "worktree", "list", "--porcelain")` | **False** |
| `git_branch_list(pattern)` | `("git", "branch", "--list", pattern)` | **False** |

**5 个只读 spec, 全部 `mutates_repository=False`**

---

## 5. forbidden Git 命令确认

```
rg "shell=True|os\.system|git worktree add|git checkout -b|git switch -c|
    git branch -D|git branch -d|git add |git commit|git push|gh pr|
    apply-local|workspace_path\s*=|branch_name\s*=" <5 target files>

结果: 零匹配 (4 个命中均为字段读取, 非写操作)
```

---

## 6. API Guard 字段确认

| 字段 | 值 | 语义 |
|------|-----|------|
| `prepare_status` | `"blocked"` | 仍未实现 |
| `creates_worktree` | **False** | 不创建 worktree |
| `creates_branch` | **False** | 不创建 branch |
| `runs_git` | **True** (preflight 时) | 只读 git 已执行 |
| `runs_write_git` | **False** | 不执行写 git |
| `mutates_agent_session_workspace` | **False** | 不修改 AgentSession |

---

## 7. 未触发项确认

| 检查项 | 状态 |
|--------|------|
| 未执行写 Git | ✅ allowlist 5 个 spec 全部 mutates_repository=False |
| 未创建 worktree | ✅ creates_worktree=False, 无 git_worktree_add 方法 |
| 未创建 branch | ✅ creates_branch=False, 无 git_checkout_new_branch 方法 |
| 未修改 AgentSession.workspace_path | ✅ mutates_agent_session_workspace=False, 测试验证 None 不变 |
| 未修改 AgentSession.branch_name | ✅ 测试验证 None 不变 |
| 未修改 RepositoryWorkspace | ✅ 无 upsert 调用 |
| 未运行 worker | ✅ 无 TaskWorker 调用 |
| 未启动服务 | ✅ tmp_path 隔离 |
| 未改前端 | ✅ 2 文件全部在 backend |

---

## 8. 测试命令与结果

```
$ python -m pytest runtime/orchestrator/tests/test_worktree_plan_dry_run.py \
    runtime/orchestrator/tests/test_agent_session_p0_coding_fields.py -q

39 passed in 0.73s
```

| 分类 | 测试数 | 关键验证 |
|------|--------|---------|
| P1-C dry-run plan | 10 | plan/hash/API |
| P1-D command runner | 3 | deny-by-default specs, 只读 args, 无写方法 |
| P1-D-B confirmation | 4 | receipt hash/block validation |
| P1-D-C prepare skeleton | 5 | blocked/guard/stale hash |
| **P1-D-D-2 blocker tightening** | **4** | **非 git worktree / dirty repo / 已有 branch / 已有 worktree 全部 blocker** |
| P0 coding fields | 13 | 全链路通过 |

---

## 9. 已发现缺口

| 缺口 | 状态 |
|------|------|
| 真实创建 worktree 仍未实现 | P1-D-D-2 预期 — 安全门控更严格 |
| 真实创建 branch 仍未实现 | 同上 |
| cleanup 仍未实现 | P1-E scope |
| audit event 仍未实现 | 未写 AgentMessage |
| base_commit_sha 仍未填充 | WorktreePlan 始终 None |

---

## 10. Gate 结论

### Coding Session P1-D-D-2 preflight blocker tightening 验证: **Pass** ✅

**证据**:
1. ✅ 4 个新 blocker: 非 git worktree / dirty repo / 已有 branch / 已有 worktree — 全部从 warning 升级为 blocker
2. ✅ 4 个参数化测试覆盖每种 unsafe 状态, 每个验证 7 项 guard 断言
3. ✅ 仍然只读: 5 个 `mutates_repository=False` allowlist spec, 零写 git
4. ✅ 仍然 blocked: `prepare_status="blocked"`, `blocked_reason` 未变
5. ✅ 零 AgentSession 变异: `workspace_path`/`branch_name` 保持 None
6. ✅ 39 tests pass, compileall clean, grep zero forbidden calls
7. ✅ 安全门控收紧: dirty repo / existing branch / existing worktree 在真实创建前被拦截

### AI Project Director 总闭环: **仍为 Partial**

P0 → P1-A → P1-B → P1-C → P1-D-A → P1-D-B → P1-D-C → P1-D-D → **P1-D-D-2** 全部 Pass。真实 worktree 创建仍未实现。

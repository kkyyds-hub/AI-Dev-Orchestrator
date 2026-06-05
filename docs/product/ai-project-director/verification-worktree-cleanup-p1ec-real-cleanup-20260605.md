# Coding Session P1-E-C real worktree cleanup minimal execution 验证

> **文档类型**: 运行证据验证 / Gate 审计  
> **生成日期**: 2026-06-05  
> **验证基准 commit**: `ebb90e41594861e8ae8264c839ef4c6d8115d80b`  
> **前置文档**:  
> - `docs/product/ai-project-director/verification-worktree-cleanup-p1ea-blocked-skeleton-20260605.md`  
> - `docs/product/ai-project-director/verification-worktree-cleanup-p1eb-readonly-preflight-20260605.md`  
> - `docs/product/ai-project-director/worktree-cleanup-p1e-design-audit-20260605.md`  
> **验证模型**: Codex  
> **状态**: Partial

---

## 1. Git 基准核对

| 项目 | 结果 |
|------|------|
| HEAD | `ebb90e41594861e8ae8264c839ef4c6d8115d80b` |
| origin/main | `ebb90e41594861e8ae8264c839ef4c6d8115d80b` |
| `ls-remote origin refs/heads/main` | `ebb90e41594861e8ae8264c839ef4c6d8115d80b` |
| HEAD 是否等于 origin/main | 是 |
| ls-remote origin main 是否等于 HEAD | 是 |
| 验证前工作树 | 干净 |

---

## 2. 核对过的文件列表

| 文件 | 核对点 |
|------|--------|
| `runtime/orchestrator/app/domain/worktree_cleanup.py` | cleanup result 成功状态、删除/分支/目录 flags、`cleaned` 语义 |
| `runtime/orchestrator/app/services/worktree_cleanup_service.py` | user confirmation、plan_hash、preflight blocker、执行路径、失败写回 |
| `runtime/orchestrator/app/services/worktree_cleanup_write_command_runner.py` | 唯一写命令 allowlist: `git worktree remove <absolute-path>` |
| `runtime/orchestrator/app/repositories/agent_session_repository.py` | `mark_workspace_cleaned()` 成功后清空 workspace/branch 绑定 |
| `runtime/orchestrator/app/api/routes/agent_threads.py` | cleanup endpoint response DTO 与 API 入口 |
| `runtime/orchestrator/tests/test_worktree_plan_dry_run.py` | clean/dirty/missing/write-failure/command-runner 目标测试覆盖 |

---

## 3. 真实 worktree cleanup 执行结论

P1-E-C 真实 worktree cleanup 只在以下条件同时满足时执行写 git：

1. `user_confirmed=True`
2. `plan_hash` 与当前 recomputed plan hash 一致
3. AgentSession 已绑定 `workspace_path` 与 `branch_name`
4. repository workspace 已绑定
5. cleanup read-only preflight 无 blocker
6. `worktree_path_exists=True`
7. `worktree_path_is_directory=True`
8. `worktree_path_safe=True`，路径位于 `allowed_workspace_root`
9. `worktree_registered=True`
10. `worktree_clean=True`

满足后仅执行：

```text
git worktree remove <workspace_path>
```

不执行：

```text
git branch -d/-D
rm -rf
shutil.rmtree
unlink
rmdir
worker / AI runtime
```

---

## 4. AgentSession 写回策略

### 4.1 成功路径

成功后调用 `AgentSessionRepository.mark_workspace_cleaned()`，写回策略：

| 字段 | 成功后值 |
|------|----------|
| `workspace_path` | `None` |
| `branch_name` | `None` |
| `workspace_type` | `WorkspaceType.IN_PLACE` |
| `workspace_clean` | `None` |
| `last_workspace_error` | `None` |

说明：branch 绑定字段清空，但 git branch 本身不删除。

### 4.2 失败/blocked 路径

失败或 preflight blocked 时：

- 只写回 `last_workspace_error`
- 不清空 `workspace_path`
- 不清空 `branch_name`
- 不修改 `workspace_type`
- 不执行 `git worktree remove`，除非已进入写命令且写命令失败

---

## 5. Command allowlist 审计

`WorktreeCleanupWriteCommandRunner` 只接受以下 shape：

```python
argv == ("git", "worktree", "remove", <absolute_path>)
command_kind == "git_worktree_remove"
execution_enabled is True
mutates_repository is True
len(argv) == 4
```

拒绝：

- disabled preview
- 非 mutating 标记不一致
- 任意非 `git worktree remove` argv
- 非 absolute worktree path
- branch delete command kind

Branch delete 只存在于 disabled preview：

```python
("git", "branch", "-d", branch_name), execution_enabled=False
```

---

## 6. 静态禁用项 grep

对 cleanup 相关文件执行静态核对：

```text
grep -R "shutil.rmtree\|\.unlink(\|\.rmdir(\|rm -rf\|git branch -d\|git branch -D" \
  runtime/orchestrator/app/domain/worktree_cleanup.py \
  runtime/orchestrator/app/services/worktree_cleanup_service.py \
  runtime/orchestrator/app/services/worktree_cleanup_write_command_runner.py \
  runtime/orchestrator/app/repositories/agent_session_repository.py \
  runtime/orchestrator/tests/test_worktree_plan_dry_run.py
```

结果：无命中。

对 cleanup service / write runner 核对 worker/runtime 触发：

```text
grep -R "worker\|AI runtime\|runtime" \
  runtime/orchestrator/app/services/worktree_cleanup_service.py \
  runtime/orchestrator/app/services/worktree_cleanup_write_command_runner.py
```

结果：无命中。

---

## 7. 测试命令与结果

未跑全量 pytest。只跑目标测试和必要相邻 allowlist 测试：

```bash
runtime/orchestrator/.venv/bin/pytest \
  runtime/orchestrator/tests/test_worktree_plan_dry_run.py \
  -q -k "worktree_cleanup or worktree_command_runner"
```

结果：

```text
12 passed, 38 deselected in 1.46s
```

覆盖点：

- unbound AgentSession blocked + 只写 `last_workspace_error`
- stale `plan_hash` rejected
- API blocked guard fields
- endpoint blocked path
- clean + registered + safe tmp_path worktree 被 `git worktree remove` 清理
- 成功后 `workspace_path=None`, `branch_name=None`, `workspace_type=IN_PLACE`
- branch 未删除（测试中 `git branch --list <branch>` 仍可见）
- dirty bound worktree blocked，workspace 绑定保留
- missing path blocked，跳过 worktree cwd `git status`
- write failure 只写 `last_workspace_error`，workspace 绑定保留
- read-only command runner 仍拒绝 arbitrary/mutating specs

---

## 8. 禁止项确认

| 项目 | 结论 |
|------|------|
| 是否跑全量 pytest | 否 |
| 是否删除 branch | 否 |
| 是否执行 `git branch -d/-D` | 否 |
| 是否执行 `rm-rf/rmtree/unlink/rmdir` | 否 |
| 是否创建/删除业务主仓库 worktree | 否 |
| 是否创建业务主仓库 `session/*` branch | 否 |
| 是否运行 worker/AI runtime | 否 |

说明：测试中的真实 `git worktree remove` 仅发生在 pytest `tmp_path` 内的临时 git fixture。

---

## 9. 已发现缺口

1. 当前 verification 是后端 service/API 函数级验证，尚未覆盖前端调用路径。
2. 尚未做真实用户 API 端到端手动演练；本轮只允许目标测试与必要相邻测试。
3. P1-E-C minimal execution 已满足 clean/registered/safe worktree cleanup，但 AI Project Director 总闭环仍未完成。

---

## 10. Gate 结论

| Gate | 结论 |
|------|------|
| Coding Session P1-E-C real worktree cleanup minimal execution 验证 | **Pass** |
| AI Project Director 总闭环 | **Partial** |

AI Project Director 总闭环不能标记 Pass。

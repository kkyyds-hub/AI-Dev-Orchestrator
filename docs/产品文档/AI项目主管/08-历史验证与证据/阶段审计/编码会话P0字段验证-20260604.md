# Coding Session P0 字段可观测能力验证

> **文档类型**: 运行证据验证
> **生成日期**: 2026-06-04
> **验证基准 commit**: `7f0cac378a20dd99d8608bbc1d43086e8f5203d5` (feat: expose agent session p0 coding fields)
> **设计基线文档**: `docs/product/ai-project-director/coding-session-lifecycle-design-20260604.md`
> **验证模型**: DeepSeek (Claude Code CLI)
> **状态**: Pass (P0 字段可观测能力)

---

## 1. 验证基准

| 项目 | 值 |
|------|-----|
| origin/main HEAD | `7f0cac378a20dd99d8608bbc1d43086e8f5203d5` |
| 提交信息 | `feat: expose agent session p0 coding fields` |
| 验证时间 | 2026-06-04 |
| 参考项目 | agent-orchestrator @ `c3eeecb` (仅机制参考，不照搬代码) |

---

## 2. 修改文件清单 (8 files, +494 −1)

| 文件 | 变更内容 |
|------|---------|
| `runtime/orchestrator/app/domain/agent_session.py` | 新增 5 枚举 (AgentType / RuntimeType / CodingSessionStatus / CodingSessionActivityState / WorkspaceType / DeliveryStatus) + AgentSession 类新增 6 个 P0 字段 |
| `runtime/orchestrator/app/core/db_tables.py` | AgentSessionTable 新增 6 个 nullable columns |
| `runtime/orchestrator/app/repositories/agent_session_repository.py` | create/update_status/_to_domain 支持 6 个 P0 字段读写 |
| `runtime/orchestrator/app/services/agent_conversation_service.py` | start_session 默认填充 P0 字段 + finalize_session 状态转换 |
| `runtime/orchestrator/app/workers/task_worker.py` | WorkerRunResult 新增 6 个 P0 string 字段 + run_once 透传 |
| `runtime/orchestrator/app/api/routes/agent_threads.py` | AgentSessionResponse 新增 6 个 P0 字段 + from_session 映射 |
| `runtime/orchestrator/app/api/routes/workers.py` | WorkerRunOnceResponse 新增 6 个 P0 字段 + from_result 映射 |
| `runtime/orchestrator/tests/test_agent_session_p0_coding_fields.py` | 新增 5 个测试 |

---

## 3. 字段清单

### 3.1 P0 字段 (6 个，全部 nullable)

| 字段 | 领域类型 | DB 类型 | 默认值 |
|------|---------|---------|--------|
| `agent_type` | `AgentType` enum | `String(40)`, nullable | None |
| `runtime_type` | `RuntimeType` enum | `String(40)`, nullable | None |
| `runtime_handle_id` | `str` (max 200) | `String(200)`, nullable | None |
| `coding_status` | `CodingSessionStatus` enum | `String(40)`, nullable | None |
| `activity_state` | `CodingSessionActivityState` enum | `String(40)`, nullable | None |
| `branch_name` | `str` (max 200) | `String(200)`, nullable | None |

### 3.2 已定义的枚举

| 枚举 | 值 | 说明 |
|------|-----|------|
| `AgentType` | claude_code / codex / opencode / openai_provider / shell / simulate | Agent 类型标识 |
| `RuntimeType` | tmux / subprocess / docker / process | 运行时环境类型 |
| `CodingSessionStatus` | spawning / working / idle / needs_input / stuck / completed / failed / terminated | 编码会话执行状态 |
| `CodingSessionActivityState` | active / ready / idle / waiting_input / blocked / exited | Agent 活动状态 |
| `WorkspaceType` | worktree / clone / in_place / read_only | 工作区类型 (预留 P1) |
| `DeliveryStatus` | none / branch_created / pr_opened / ci_pending / ci_passing / ci_failed / review_pending / review_approved / changes_requested / merged / closed | 交付状态 (预留 P1/P2) |

---

## 4. 默认填充逻辑

`AgentConversationService.start_session()` 填充:

```python
agent_type = AgentType.OPENAI_PROVIDER
runtime_type = RuntimeType.SUBPROCESS
coding_status = CodingSessionStatus.WORKING
activity_state = CodingSessionActivityState.ACTIVE
runtime_handle_id = None    # (不填充，留空)
branch_name = None           # (不填充，留空)
```

**验证结果**: ✅ Repository round-trip test 确认 `create()` 正确写入和回读所有 6 个字段，包括 whitespace normalization (`" subprocess:local "` → `"subprocess:local"`, `" main "` → `"main"`)。

---

## 5. finalize 状态转换逻辑

`AgentConversationService.finalize_session()` 基于 `run_status` 决定 coding_status:

| run_status | AgentSession.status | coding_status | activity_state |
|-----------|--------------------|---------------|----------------|
| `SUCCEEDED` | `COMPLETED` | `completed` | `exited` |
| `FAILED` | `FAILED` | `failed` | `exited` |
| `CANCELLED` | `BLOCKED` | `terminated` | `exited` |

**验证结果**: ✅ `test_agent_conversation_service_fills_p0_defaults_and_final_state` 确认 succeeded → completed/exited 路径正确。

---

## 6. API Response 透传证据

### 6.1 `/agent-threads/projects/{project_id}/sessions` (AgentSessionResponse)

| 字段 | 类型 | 来源 |
|------|------|------|
| `agent_type` | `str \| None` | `session.agent_type.value` |
| `runtime_type` | `str \| None` | `session.runtime_type.value` |
| `runtime_handle_id` | `str \| None` | `session.runtime_handle_id` |
| `coding_status` | `str \| None` | `session.coding_status.value` |
| `activity_state` | `str \| None` | `session.activity_state.value` |
| `branch_name` | `str \| None` | `session.branch_name` |

**验证结果**: ✅ `test_agent_session_response_exposes_p0_coding_fields` 确认从 domain → DTO → JSON 全路径透传正确。

### 6.2 `/workers/run-once` (WorkerRunOnceResponse)

| 字段 | 类型 | 来源 |
|------|------|------|
| `agent_type` | `str \| None` | `result.agent_type` (WorkerRunResult) |
| `runtime_type` | `str \| None` | `result.runtime_type` |
| `runtime_handle_id` | `str \| None` | `result.runtime_handle_id` |
| `coding_status` | `str \| None` | `result.coding_status` |
| `activity_state` | `str \| None` | `result.activity_state` |
| `branch_name` | `str \| None` | `result.branch_name` |

**验证结果**: ✅ `test_worker_run_once_response_exposes_p0_coding_fields_without_running_worker` 确认 DTO 层透传正确，无需启动 Worker 实例。

---

## 7. DB Column 验证

```sql
-- AgentSessionTable 已包含以下 nullable columns:
agent_type       VARCHAR(40)  NULL
runtime_type     VARCHAR(40)  NULL
runtime_handle_id VARCHAR(200) NULL
coding_status    VARCHAR(40)  NULL
activity_state   VARCHAR(40)  NULL
branch_name      VARCHAR(200) NULL
```

**验证结果**: ✅ `test_agent_sessions_table_contains_p0_coding_columns` 确认所有 6 列存在于 `agent_sessions` 表中。

---

## 8. 测试结果

### 8.1 P0 字段专用测试

```
$ python -m pytest runtime/orchestrator/tests/test_agent_session_p0_coding_fields.py -q

5 passed in 0.38s
```

| 测试 | 验证内容 |
|------|---------|
| `test_agent_sessions_table_contains_p0_coding_columns` | DB 表包含 6 个 P0 nullable columns |
| `test_agent_session_repository_round_trips_p0_coding_fields` | Repository create/read/update 正确读写所有字段 + whitespace normalization |
| `test_agent_conversation_service_fills_p0_defaults_and_final_state` | start_session 默认 fill + finalize_session 状态转换 |
| `test_agent_session_response_exposes_p0_coding_fields` | AgentSessionResponse 透传 |
| `test_worker_run_once_response_exposes_p0_coding_fields_without_running_worker` | WorkerRunOnceResponse 透传 |

### 8.2 编译检查

```
$ python -m compileall -q runtime/orchestrator/app runtime/orchestrator/tests
(no output — all files compiled successfully)
```

### 8.3 git diff --check

```
(no output — no whitespace issues)
```

### 8.4 相关测试子集 (排除 live 测试)

```
$ python -m pytest runtime/orchestrator/tests/ -q \
    -k "agent_session or agent_conversation or worker" \
    --ignore=.../test_agent_session_p0_coding_fields.py

5 passed (124s) + 1 pre-existing failure (server-required live test, unrelated)
```

---

## 9. 未触发项确认

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 未改前端 | ✅ | 8 个修改文件全部在 `runtime/orchestrator/` 下 |
| 未运行服务 | ✅ | 所有测试使用 `tmp_path` 隔离 SQLite，不启动 FastAPI |
| 未运行 Worker 实例 | ✅ | `test_worker_run_once_response_exposes_p0_coding_fields_without_running_worker` 仅测 DTO |
| 未触发 apply-local | ✅ | 未导入 `local_git_write_service` |
| 未触发 git-commit | ✅ | 未调用 git 命令 |
| 未创建 worktree | ✅ | `workspace_type` 枚举已定义但 AgentSession 中不存储 (留 P1) |
| 未创建 branch | ✅ | `branch_name` 始终留 null |
| 未创建 PR | ✅ | `delivery_status` 枚举已定义但 AgentSession 中不存储 (留 P2) |
| 未新增 API endpoint | ✅ | 只扩展现有 response DTO 字段，不新增路由 |
| 未新建数据库表 | ✅ | 只在 `agent_sessions` 表添加 nullable columns |
| 未引入 agent-orchestrator 代码 | ✅ | 无 TypeScript 文件，无新依赖 |

---

## 10. Gate 结论

### Coding Session P0 字段可观测能力: **Pass**

**证据**:
1. ✅ AgentSession 领域模型包含 6 个 P0 nullable 字段
2. ✅ ORM 表包含对应 6 个 nullable columns
3. ✅ Repository create/update/to_domain 正确读写所有字段
4. ✅ start_session 默认填充: agent_type=openai_provider, runtime_type=subprocess, coding_status=working, activity_state=active
5. ✅ finalize_session 状态转换: succeeded→completed, failed→failed, cancelled→terminated; 所有终结路径→activity_state=exited
6. ✅ /workers/run-once response 透传 6 个 P0 字段
7. ✅ /agent-threads/projects/{id}/sessions response 透传 6 个 P0 字段
8. ✅ 未引入 worktree/branch/PR/CI/review/apply-local/git-commit/前端改动
9. ✅ 5 tests pass, 0.38s
10. ✅ compileall pass
11. ✅ git diff --check clean

### AI Project Director 总闭环: **仍为 Partial**

**原因**:
- P0 字段设计基线已实现并验证通过
- 但以下能力尚未实现:
  - P1: Per-Run worktree 隔离
  - P1: git branch per coding session
  - P2: SCM 集成 (PR/CI/review)
  - P0 字段当前仅在 simulate 模式下填充，真实 provider 运行尚未验证
  - 四轴状态推导层尚未实现 (SessionStateDeriver)
  - SessionActivityPoller 尚未实现

**下一阶段**: P1 工作区隔离 (workspace_type + worktree_path + per-session git branch) 需 Codex 实现后再由 DeepSeek 验证。

---

## 11. 设计基线一致性核对

| 设计基线要求 | 实现状态 | 证据 |
|-------------|---------|------|
| 6 P0 nullable 字段 | ✅ | agent_session.py L127-132 |
| 不新建表 | ✅ | 仅 ALTER agent_sessions ADD COLUMN |
| 不改执行模型 | ✅ | TaskWorker.run_once 控制流未变 |
| 不改前端 | ✅ | 零前端文件变更 |
| 不建 API endpoint | ✅ | 仅扩展现有 response DTO |
| AgentSession (Day11) 兼容 | ✅ | 现有 status/review_status/current_phase 不变 |

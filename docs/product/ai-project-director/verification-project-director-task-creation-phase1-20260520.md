# AI Project Director Task Creation Phase1 — 验收文档

> 文档日期：2026-05-20
> 仓库：kkyyds-hub/AI-Dev-Orchestrator
> 阶段：BCG-04A Phase1 后端闭环补齐
> 性质：后端实现级验收
> 配套文档：
> - `backend-closure-gap-freeze-20260519-v2.md`
> - `execution-plan-backfill-ledger-20260519.md`
> - `verification-project-director-session-phase1-20260519.md`
> - `verification-project-director-plan-version-phase1-20260519.md`
> - `verification-project-director-confirmation-inbox-phase1-20260519.md`

---

## 1. 实现范围

本阶段新增 confirmed plan version → real task queue 的后端闭环。

Phase1 只做任务创建和入队，不做 Worker 调度，不做任务执行，不做仓库写入。

---

## 2. 新增 API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/project-director/plan-versions/{plan_version_id}/create-tasks` | 从 confirmed plan version 创建真实任务 |
| GET | `/project-director/plan-versions/{plan_version_id}/created-tasks` | 查询已创建的任务记录 |

响应格式：

```json
{
  "plan_version_id": "...",
  "session_id": "...",
  "project_id": "...",
  "created_task_ids": ["...", "..."],
  "task_count": N,
  "status": "created",
  "next_action": "任务已创建并进入队列。后续需手动触发 Worker 调度执行任务。当前阶段不自动执行。",
  "forbidden_actions": [
    "不自动调用 Worker",
    "不自动执行任务",
    "不调用 planning/apply",
    "不写仓库",
    "不把任务创建等同于任务执行"
  ],
  "gate_conclusion": "Partial（任务创建闭环 Pass，Worker 执行未完成）"
}
```

---

## 3. 状态约束

| 条件 | HTTP 状态 | 说明 |
|---|---|---|
| plan version 不存在 | 404 | |
| plan version 未 confirmed | 409 | 只有 confirmed 才能创建任务 |
| plan version 无 project_id | 409 | 任务必须归属项目 |
| 重复创建 | 409 | 一个 plan version 只能创建一次任务 |
| project 不存在 | 422 | 关联项目已被删除 |

---

## 4. 任务来源追溯方式

采用非侵入设计，不改动 Task 领域模型：

| 追溯手段 | 存储位置 | 内容 |
|---|---|---|
| `source_draft_id` | Task 表（已有字段） | `pdv:{plan_version_id}:{version_no}` |
| `TaskCreationRecord` | 新表 `project_director_task_creation_records` | `source_type`, `plan_version_id`, `session_id`, `version_no`, `task_ids[]` |

---

## 5. Plan Version → Task 映射规则

| ProposedTask 字段 | Task 字段 | 映射 |
|---|---|---|
| `title` | `title` | 直接复制 |
| `description` | `input_summary` | 直接复制 |
| `suggested_role_code` | `owner_role_code` | 直接复制 |
| `priority_hint` | `priority` | high→HIGH, urgent→URGENT, low→LOW, 默认→NORMAL |
| — | `project_id` | 来自 plan_version.project_id |
| — | `status` | pending |
| — | `source_draft_id` | `pdv:{plan_version_id}:{version_no}` |

---

## 6. 新增文件

| 文件 | 说明 |
|---|---|
| `app/domain/project_director_task_creation.py` | TaskCreationRecord 领域模型 |
| `app/repositories/project_director_task_creation_repository.py` | TaskCreationRecord 仓库 |
| `app/services/project_director_task_creation_service.py` | Plan-to-Task 服务 |
| `tests/test_project_director_task_creation.py` | 13 个测试 |

### 修改文件

| 文件 | 变更 |
|---|---|
| `app/core/db_tables.py` | 新增 `ProjectDirectorTaskCreationRecordTable` |
| `app/api/routes/project_director.py` | 新增 2 个路由 + TaskCreationResponse DTO + 依赖注入 |

---

## 7. 测试命令

```bash
cd runtime/orchestrator
python -m pytest tests/test_project_director_task_creation.py -v
```

## 8. 测试结果

```
============================= 13 passed =============================
```

全局回归：

```
python -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py -v
============================= 90 passed =============================
```

### 测试覆盖

| 测试 | 覆盖内容 |
|---|---|
| `test_create_tasks_from_confirmed_plan_with_project` | 完整 happy path |
| `test_create_tasks_plan_version_not_found_returns_404` | 不存在的 plan version |
| `test_create_tasks_unconfirmed_plan_version_returns_409` | pending_confirmation 拒绝 |
| `test_create_tasks_plan_version_without_project_id_returns_409` | 缺少 project_id 拒绝 |
| `test_duplicate_create_tasks_returns_409` | 重复创建拒绝 |
| `test_created_task_count_equals_proposed_task_count` | 任务数量断言 |
| `test_task_source_draft_id_is_set` | source_draft_id 追溯 |
| `test_task_role_code_aligns_with_proposed_task` | role code 对齐 |
| `test_task_priority_mapping_correct` | priority 映射 |
| `test_get_created_tasks_returns_task_ids` | GET 端点读取 |
| `test_get_created_tasks_before_creation_returns_404` | 未创建时 GET |
| `test_create_tasks_does_not_create_runs` | 不产生 run |
| `test_all_response_fields_present` | 9 个必需字段齐全 |

---

## 9. 未覆盖范围

- 前端页面（本阶段未改前端）
- Worker 调度与执行
- planning/apply 调用
- 仓库写入
- AI Provider 调用
- 运行证据（截图、E2E 联调）
- 阶段性依赖编排（task dependencies 未从 plan 推导）

---

## 10. Gate 结论

```text
Gate 结论：Partial
后端实现：Backend Pass
运行证据：Runtime Evidence Missing
总闭环：Partial（BCG-04A Phase1 仅完成 confirmed plan → task queue 创建，不代表 Worker 执行，不代表 AI Project Director 总闭环 Pass）
```

### 理由

- 2 个 API（POST create-tasks + GET created-tasks）
- confirmed plan version → real task queue 映射完整
- 状态约束（404/409）覆盖全面
- 重复创建防护（409 idempotency guard）
- project_id 缺失防护（409）
- source_draft_id + TaskCreationRecord 双追溯
- 13 个测试全部通过，原有 77 个测试无回归
- 未改前端、未接 AI、未调用 Worker、未写仓库

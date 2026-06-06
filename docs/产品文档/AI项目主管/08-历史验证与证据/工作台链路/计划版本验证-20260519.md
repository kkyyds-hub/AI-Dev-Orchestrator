# AI Project Director Plan Version Phase1 — 验收文档

> 文档日期：2026-05-19
> 仓库：kkyyds-hub/AI-Dev-Orchestrator
> 阶段：BCG-02 Phase1 后端闭环补齐
> 性质：后端实现级验收
> 配套文档：
> - `backend-closure-gap-freeze-20260519-v2.md`
> - `execution-plan-backfill-ledger-20260519.md`
> - `verification-project-director-session-phase1-20260519.md`

---

## 1. 实现范围

本阶段新增 Plan Version / Plan Approval Phase1，让"已确认目标"可以生成可审阅的计划版本。

```
confirmed session → 生成 plan version (pending_confirmation) → 用户确认 → confirmed
                                                                    ↓
                                                          旧 confirmed → superseded
```

计划版本必须经过 pending_confirmation → confirmed 流程。确认后不创建任务、不调用 worker、不调用 planning/apply。

---

## 2. 新增 API

| 方法 | 路径 | 状态码 | 说明 |
|---|---|---|---|
| POST | `/project-director/sessions/{session_id}/plan-versions` | 201 | 从 confirmed session 生成 plan version |
| GET | `/project-director/sessions/{session_id}/plan-versions` | 200 | 列出 session 的所有 plan versions |
| GET | `/project-director/plan-versions/{plan_version_id}` | 200 | 读取单个 plan version |
| POST | `/project-director/plan-versions/{plan_version_id}/confirm` | 200 | 确认 plan version，supersede 旧 confirmed |

### 流程约束

| 条件 | 响应 |
|---|---|
| session 不存在 | 404 |
| session 非 confirmed | 409 (Only confirmed sessions...) |
| plan version 不存在 | 404 |
| plan version 非 pending_confirmation 时确认 | 409 |
| 新版本确认 → 旧 confirmed 版本 | superseded |

---

## 3. 状态机

```
draft → pending_confirmation → confirmed
                                   ↓ (新版本确认时)
                              superseded

pending_confirmation → rejected (手动拒绝，Phase1 暂未实现 API)
```

| 状态 | 含义 |
|---|---|
| draft | 初始草稿（Phase1 不直接进入此状态，直接进入 pending_confirmation） |
| pending_confirmation | 待用户确认 |
| confirmed | 已确认，当前生效的计划版本 |
| superseded | 已被新版本取代 |
| rejected | 已拒绝（Phase1 未实现独立的 reject API） |

---

## 4. Plan Version 内容

每个 plan version 包含：

- `plan_summary` — 作战计划摘要（目标 + 约束 + 关键决策依据）
- `phases` — 阶段列表（sequence, name, goal, task_count_hint）
- `proposed_tasks` — 建议任务列表（title, description, suggested_role_code, priority_hint）
- `acceptance_criteria` — 验收标准列表
- `risks` — 风险列表
- `forbidden_actions` — 禁止动作列表（"不自动创建任务"、"不自动调用 Worker"、"不写仓库"、"不把计划确认等同于执行完成"、"不调用 planning/apply"）

---

## 5. 新增文件

| 文件 | 说明 |
|---|---|
| `app/domain/project_director_plan_version.py` | PlanVersion 领域模型（5 状态枚举 + PlanPhase + ProposedTask + PlanVersion） |
| `app/repositories/project_director_plan_version_repository.py` | 数据仓库（CRUD + list_by_session_id + get_active_confirmed + get_next_version_no） |
| `app/services/project_director_plan_service.py` | 业务逻辑（确定性计划生成 + 确认 + supersede 逻辑） |
| `tests/test_project_director_plan_versions.py` | 21 个测试 |

### 修改文件

| 文件 | 变更 |
|---|---|
| `app/core/db_tables.py` | 新增 ProjectDirectorPlanVersionTable |
| `app/api/routes/project_director.py` | 新增 4 个 plan version 端点 + DTOs + 契约计算 |

---

## 6. 测试命令

```bash
cd runtime/orchestrator
python -m pytest tests/test_project_director_plan_versions.py -v
```

## 7. 测试结果

```
============================= 21 passed in 8.66s ==============================
```

完整回归测试：

```
python -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py -v
============================= 59 passed in 22.78s ==============================
```

### 测试覆盖

| 测试类 | 用例数 | 覆盖内容 |
|---|---|---|
| TestCreatePlanVersion | 5 | 从 confirmed session 创建、未 confirmed → 409、session 404、version_no 递增、字段完整性 |
| TestListPlanVersions | 3 | 空列表、多版本排序、session 404 |
| TestGetPlanVersion | 2 | 读取存在/不存在 |
| TestConfirmPlanVersion | 7 | 确认转换、幂等、404、非 pending 状态 409、supersede、契约字段、确认后禁止动作 |
| TestPlanService | 4 | 完整流程、版本递增、未 confirmed 不可创建、404 |

---

## 8. 未覆盖范围

- 前端页面（本阶段未改前端）
- 真实 AI 调用（Phase1 使用确定性规则）
- Provider 集成
- Worker 调度
- 任务创建（plan 确认后不创建任务）
- planning/apply 调用
- 仓库写入
- 运行证据（截图、E2E 联调）
- reject plan version API（Phase1 未实现）

---

## 8.5 Hardening Patch（2026-05-19）

### role code 对齐

`ProposedTask.suggested_role_code` 从 `str` 改为 `ProjectRoleCode` 枚举，确保只使用合法角色。

| 旧值 | 新值 |
|---|---|
| `developer` | `engineer` (ProjectRoleCode.ENGINEER) |
| `frontend_developer` | `engineer` (ProjectRoleCode.ENGINEER) |
| `tester` | `reviewer` (ProjectRoleCode.REVIEWER) |
| `architect` | 不变 (ProjectRoleCode.ARCHITECT) |

### TaskTable 验证

`test_confirmed_plan_does_not_create_tasks` 现在真实查询数据库 `TaskTable` 行数：
- 确认前 count → 确认后 count 必须相等且为 0

### 新增测试

- `test_frontend_task_uses_engineer_role` — 前端任务使用 engineer
- `test_testing_task_uses_reviewer_role` — 测试任务使用 reviewer
- `test_no_developer_or_tester_role_codes` — 无非法 role code
- `test_create_from_confirmed_session` 新增 role code 合法性断言

### 测试更新

- 24 个测试全部通过（原 21 + 新增 3）
- 62/62 完整回归（含 session 38 个测试）

---

## 9. Gate 结论

```text
Gate 结论：Partial
后端实现：Backend Pass
运行证据：Runtime Evidence Missing
总闭环：Partial（BCG-02 Phase1 仅覆盖 plan version 生成与确认，不代表任务创建，不代表 AI Project Director 总闭环 Pass）
```

### 理由

- 4 个 API 真实读写数据库，状态机完整（pending_confirmation→confirmed/superseded）
- 确定性计划生成基于 session 的 goal_text、constraints、clarifying_answers
- 版本递增正确，同一 session 只有一个 active confirmed
- 确认后不创建任务、不调用 planning/apply、不调用 worker
- forbidden_actions 明确列出 5 项禁止动作
- 24 个测试全部通过（含 role code 校验 + TaskTable 行数检查），原有 38 个 session 测试无回归
- 未改前端、未接 AI、未创建任务、未调度 Worker、未写仓库

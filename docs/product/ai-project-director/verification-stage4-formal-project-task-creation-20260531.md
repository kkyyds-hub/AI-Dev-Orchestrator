# Stage 4-B3-A 从已确认草案创建正式 Project + Task 队列 Runtime Evidence

> 文档类型：Stage 4-B3-A 正式项目与任务队列创建 Runtime Evidence 验证
> 审计日期：2026-05-31
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`6eecc1d1ae24c540811c385558db0e6e36a03355`
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> UX 路线图：`docs/product/AI-Dev-Orchestrator-AI-assisted-UX-roadmap-20260517.md`
> 前置阶段：Stage 4-B1 Pass（commit `6b0343cf`：草案审核弹窗）、Stage 4-B2 Pass（commit `e8178ba0f`：草案内容增强）

---

## 1. 基准 commit

```
6eecc1d1ae24c540811c385558db0e6e36a03355
```

确认方式：`git fetch origin && git checkout main && git pull --ff-only origin main && git rev-parse HEAD`，与用户报告的 `origin/main` 一致。

变更范围（v4-B2 `e8178ba0f` → v4-B3-A `6eecc1d`）：

关键变更文件：
- `runtime/orchestrator/app/services/project_director_task_creation_service.py` — 重命名 `create_tasks_from_plan_version` → 新方法 `create_formal_project_from_plan_version`（创正式 Project 或读回已有 Project，不要求 project_id 已存在）
- `runtime/orchestrator/app/api/routes/project_director.py` — 新增 `POST /plan-versions/{id}/create-formal-project` 路由
- `runtime/orchestrator/tests/test_project_director_task_creation.py` — 新增 3 个 create-formal-project 测试
- `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx` — "创建正式项目"按钮 + 结果卡片 + warnings 展示
- `apps/web/src/features/project-director/api.ts` — `createProjectDirectorTaskQueue` 改为调用 `/create-formal-project`
- `apps/web/src/features/project-director/types.ts` — `TaskCreationResponse` 新增 `already_created`、`project_name` 字段
- `apps/web/src/features/project-director/hooks.ts` — `onSuccess` 中 invalidateQueries 更新为 `project-detail` (含 project_id)

---

## 2. 验证范围

验证 Stage 4-B3-A：用户显式点击"创建正式项目"按钮后，从 confirmed Project Director plan version 创建正式 Project + pending Task 队列。

覆盖：
- 后端 `POST /project-director/plan-versions/{plan_version_id}/create-formal-project` API
- 创建前条件验证（plan version 状态、proposed_tasks 非空）
- 创建结果验证（Project readback、Task 队列、source_draft_id 追溯）
- 幂等保护验证
- Response 字段完整性验证
- Project name 命名规则验证
- Warnings / forbidden_actions 内容验证
- 不执行副作用验证（不创建 Agent Session / Skill / Repository / Run / 不调用 provider）
- 前端按钮与结果卡片验证
- 测试执行与构建

---

## 3. 后端 create-formal-project API 验证结果

### 3.1 路由定义

| 项 | 值 |
|---|---|
| 方法 | `POST` |
| 路由 | `/project-director/plan-versions/{plan_version_id}/create-formal-project` |
| Response | `TaskCreationResponse` |
| 代码位置 | `runtime/orchestrator/app/api/routes/project_director.py:1140-1192` |

### 3.2 创建前条件验证

| 条件 | 状态 | 代码位置 |
|---|---|---|
| plan version 必须存在 | 404 if not found | `project_director.py:1163-1168` |
| plan version.status 必须是 confirmed | 409 if not confirmed | `project_director.py:1169-1173` |
| rejected 不得创建 | 409 | `task_creation_service.py:199-203` (`_require_confirmed_plan_version`) |
| pending_confirmation 不得创建 | 409 | 同上 |
| superseded 不得创建 | 409 | 同上 |
| proposed_tasks 不能为空 | 422 if validation fails | `task_creation_service.py:401-411` (`_ensure_proposed_tasks_are_valid`) |
| approve / confirm 草案本身不得自动创建 Project / Tasks | review approve 仅调 `confirm_plan_version()`，不调 create-formal-project | `project_director.py:900-904` |
| 旧端点 POST /plan-versions/{id}/create-tasks 仍要求 project_id 已存在 | ValueError if None | `task_creation_service.py:119-123` |

### 3.3 confirm_plan_version 不自动创建验证

| 检查项 | 结果 |
|---|---|
| `confirm_plan_version()` 方法 | 仅修改 plan_version 状态（pending_confirmation → confirmed），不调 create_formal_project_from_plan_version |
| review action=approve | 调 `plan_service.confirm_plan_version()`，不调 create-formal-project |
| confirm_plan_version 代码路径 | 仅 `_plan_repo.update()`，无 task 创建、无 project 创建、无 worker 调用 |
| 标记文案 | `"草案已通过，可单独触发任务创建；不会自动执行。"` |

---

## 4. Project 创建与 readback 验证结果

### 4.1 Project 创建

| 条件 | 行为 | 代码位置 |
|---|---|---|
| plan_version.project_id is None | 创建新 Project | `task_creation_service.py:164-168` |
| plan_version.project_id 已存在且有效 | 跳过创建，直接创建 Tasks | `task_creation_service.py:172-176` |
| plan_version.project_id 指向已删除 Project | 报错 | `task_creation_service.py:172-176` |

### 4.2 Project name 验证

| 规则 | 测试断言 | 结果 |
|---|---|---|
| 不以 # 开头 | `assert not project_data["name"].startswith("#")` | Pass |
| 不等于 "作战计划摘要" | `assert project_data["name"] != "作战计划摘要"` | Pass |
| 不等于 "## 作战计划摘要" | 由 `_clean_project_name_line()` 清除 `#` 前缀保证 | Pass |
| 应来自目标摘要 | `assert "用户认证系统" in project_data["name"]` | Pass |
| fallback 为 "AI 项目主管计划 v{version_no}" | `_derive_project_name_from_plan_version()` 末尾 | Pass |
| 用户可见文案为中文 | `project_name` 字段全中文 | Pass |

代码位置：`task_creation_service.py:304-361`

### 4.3 Project readback

| 验证 | 结果 |
|---|---|
| `GET /projects/{project_id}` 返回 200 | Pass |
| `project_data["id"]` 等于 `data["project_id"]` | Pass |
| `project_data["task_stats"]["total_tasks"]` 等于 `data["task_count"]` | Pass |

测试代码：`test_project_director_task_creation.py:382-393`

---

## 5. Task 创建与 source_draft_id 追溯验证结果

### 5.1 Task 创建

| 验证项 | 断言 | 结果 |
|---|---|---|
| created task 数量 | `len(data["created_task_ids"]) == len(confirmed["proposed_tasks"])` | Pass |
| task_count 字段 | `data["task_count"] == len(confirmed["proposed_tasks"])` | Pass |
| 每个 task 通过 GET /tasks/{task_id} readback | HTTP 200 | Pass |
| task.project_id 等于 project_id | `task_data["project_id"] == data["project_id"]` | Pass |

### 5.2 source_draft_id 追溯

| 验证项 | 值 |
|---|---|
| source_draft_id 格式 | `pdv:{plan_version_id}:{version_no}` |
| 每个 Task 的 source_draft_id 一致 | 全部等于 `f"pdv:{pv['id']}:{confirmed['version_no']}"` |
| GET /tasks/{task_id} 返回 source_draft_id | Pass |
| DB 直接查询验证 | `select(TaskTable).where(TaskTable.source_draft_id == source_draft_id)` 返回数量等于 task_count |

代码位置：
- `task_creation_service.py:419` — `source_draft_id = f"pdv:{plan_version.id}:{plan_version.version_no}"`
- 测试：`test_project_director_task_creation.py:399-405, 442-449`

### 5.3 Plan version 追溯 Project 绑定

| 验证 | 结果 |
|---|---|
| `GET /plan-versions/{id}` 返回 `project_id` 等于新创建 Project 的 id | `reread_plan_resp.json()["project_id"] == data["project_id"]` | Pass |

---

## 6. 幂等保护验证结果

| 验证项 | 断言 | 结果 |
|---|---|---|
| 第二次调用不创建重复 Project | `len(project_rows) == 1` | Pass |
| 第二次调用不创建重复 Tasks | `len(task_rows) == first["task_count"]` | Pass |
| 返回同一 project_id | `second["project_id"] == first["project_id"]` | Pass |
| 返回同一 created_task_ids | `second["created_task_ids"] == first["created_task_ids"]` | Pass |
| 返回同一 task_count | `second["task_count"] == first["task_count"]` | Pass |
| status = "already_created" | `second["status"] == "already_created"` | Pass |
| already_created = true | `second["already_created"] is True` | Pass |
| next_action 说明不会重复创建 | `"不会重复创建" in second["next_action"]` | Pass |

代码位置：
- Service：`task_creation_service.py:158-160` — 检查 `self._creation_repo.get_by_plan_version_id()`
- 测试：`test_project_director_task_creation.py:407-450`

---

## 7. Response 字段完整验证

| 字段 | 类型 | 存在 | 内容验证 |
|---|---|---|---|
| `project_id` | UUID string | Pass | 非空 |
| `project_name` | string | Pass | 非空，中文 |
| `created_task_ids` | UUID string[] | Pass | 数量 = task_count |
| `task_count` | int | Pass | > 0 |
| `status` | string | Pass | "created" / "already_created" |
| `already_created` | bool | Pass | true / false |
| `next_action` | string (中文) | Pass | "正式项目与待执行任务队列已创建。" / "该已确认草案已经创建过..." |
| `warnings` | string[] | Pass | 4 条 |
| `forbidden_actions` | string[] | Pass | 9 条 |
| `gate_conclusion` | string (中文) | Pass | "部分通过（正式项目 + 任务队列创建已完成；Worker 执行未开始）" |

---

## 8. Warnings 验证结果

### 8.1 Backend warnings 常量

代码位置：`task_creation_service.py:58-63`

```python
_FORMAL_PROJECT_CREATION_WARNINGS = [
    "Agent 编队建议仅作为草案快照展示，未创建 Agent Session，未自动启动 Worker。",
    "Skill 绑定建议仅作为草案快照展示，未创建真实 Skill 绑定。",
    "仓库绑定建议仅作为草案快照展示，未创建真实仓库绑定，未写入仓库。",
    "验证机制建议仅作为草案快照展示，未执行验证命令。",
]
```

### 8.2 测试断言

| 警告内容 | 后端测试断言 | 结果 |
|---|---|---|
| Agent Session 未创建 | `assert "Agent Session" in warnings_text` | Pass |
| 未自动启动 Worker | `assert "未自动启动 Worker" in warnings_text` | Pass |
| 真实 Skill 绑定未创建 | `assert "真实 Skill 绑定" in warnings_text` | Pass |
| 真实仓库绑定未创建 | `assert "真实仓库绑定" in warnings_text` | Pass |
| 未执行验证命令 | `assert "未执行验证命令" in warnings_text` | Pass |

### 8.3 Forbidden actions

```python
_BOUNDARY_ACTIONS = [
    "不自动调用 Worker",
    "不自动执行任务",
    "不调用 planning/apply",
    "不调用 apply-local",
    "不写入仓库文件",
    "不调用真实 AI provider",
    "不创建 Agent Session",
    "不创建真实 Skill 绑定",
    "不创建真实仓库绑定",
]
```

---

## 9. 无副作用验证结果

### 9.1 不创建执行副作用

| 实体 | 是否创建 | 测试断言 |
|---|---|---|
| Agent Session | 否 | `assert db_session.execute(select(AgentSessionTable)).scalars().all() == []` |
| Skill 绑定 | 否 | `assert db_session.execute(select(ProjectRoleSkillBindingTable)).scalars().all() == []` |
| 仓库绑定 | 否 | `assert db_session.execute(select(RepositoryWorkspaceTable)).scalars().all() == []` |
| Run | 否 | `assert db_session.execute(select(RunTable)).scalars().all() == []` |

### 9.2 不调用外部能力

| 能力 | 是否调用 | 确认方式 |
|---|---|---|
| 真实 AI provider | 否 | Service 无 `import openai`、无 HTTP 调用、无 Provider 引用 |
| Worker Pool | 否 | `_create_task_queue_for_plan_version()` 仅写 DB |
| planning/apply | 否 | 无 `planning` / `apply` 调用 |
| apply-local | 否 | 无文件操作 |
| 产品内 git-commit | 否 | 无 git 相关调用 |
| 验证命令 | 否 | `verification_mechanisms[].command_or_method` 仅为字符串建议，不经过 `os.system()` / `subprocess` |

代码位置：`test_project_director_task_creation.py:452-469`（`test_create_formal_project_does_not_create_execution_side_effects`）

---

## 10. 前端按钮与结果卡片验证结果

### 10.1 "创建正式项目"按钮

| 验证项 | 状态 | 代码位置 |
|---|---|---|
| 不自动创建 | approve 后只更新 planVersion，不调 createTaskQueue | `DirectorChatEntry.tsx:258-287` (handleReviewPlanVersion) |
| 只有 planVersion.status === "confirmed" 时按钮出现 | `canCreateTaskQueue = planVersion?.status === "confirmed" && !taskCreation && !createTaskQueueMutation.isPending` | `DirectorChatEntry.tsx:104-107` |
| 点击后调用 create-formal-project | `createTaskQueueMutation.mutateAsync({ planVersionId })` → `POST /.../create-formal-project` | `DirectorChatEntry.tsx:296-298`, `api.ts:90` |
| 中文 loading 状态 | `"创建正式项目中..."` | `DirectorChatEntry.tsx:114` |
| 中文 error 状态 | `createTaskQueueMutation.isError ? <ErrorLine ...>` | `DirectorChatEntry.tsx:730-732` |
| 创建后 button disabled | `disabled={!canCreateTaskQueue}` → taskCreation 已存在 | `DirectorChatEntry.tsx:104-107` |

### 10.2 结果卡片内容

| 区域 | 内容 | 代码位置 |
|---|---|---|
| 标题 | `"正式项目与任务队列已创建"` | `DirectorChatEntry.tsx:562` |
| 摘要 | 项目名称 + 任务数 + 队列状态 + Gate 结论 | `DirectorChatEntry.tsx:564-568` |
| 查看正式项目 | Link to `/projects/{project_id}` | `DirectorChatEntry.tsx:588-593` |
| 查看执行中心 | Link to `/execution?tab=tasks&projectId={project_id}` | `DirectorChatEntry.tsx:582-587` |
| next_action | 中文文案展示 | `DirectorChatEntry.tsx:597` |
| warnings 卡片 | amber-500 边框 + "创建结果边界提示" 标题 + 4 条 warning | `DirectorChatEntry.tsx:599-609` |
| forbidden_actions | 底部轻提示 "创建边界：..." | `DirectorChatEntry.tsx:701-704` |
| 任务链接列表 | 前 6 个 Task ID + "等 N 个任务"（超过 6 个时） | `DirectorChatEntry.tsx:678-699` |

### 10.3 "启动一次执行"不自动触发

| 验证 | 状态 |
|---|---|
| 按钮独立存在 | 单独按钮 `data-testid="director-chat-run-worker-once"` |
| 需要 taskCreation.project_id | `canRunWorkerOnce = Boolean(taskCreation?.project_id) && !runWorkerOnceMutation.isPending` |
| 手动点击才调用 | `onClick={() => { void handleRunWorkerOnce(); }}` |
| 不嵌入创建流程 | handleCreateTaskQueue 结束后不调 handleRunWorkerOnce |

### 10.4 不把建议展示为已绑定或已执行

- Agent 编队建议在草案弹窗中展示（`ProjectDirectorPlanReviewModal`），创建结果卡片仅显示项目/任务/边界提示
- Skill 绑定建议在草案弹窗中展示为 "建议绑定" / "未绑定"（`formatBindingMode()`）
- 仓库绑定建议在草案弹窗中显示 "仅审阅" + "建议绑定" + "分支：未指定"（`formatBindingType()` / `formatBindingMode()`）
- 验证机制不显示为 "已执行"
- Warnings 明确说明所有建议仅为快照，未真实执行

---

## 11. 测试命令与结果

### 11.1 create-formal-project 专用测试

```bash
cd runtime/orchestrator
python -m pytest tests/test_project_director_task_creation.py -q
```

**结果：21 passed in 13.08s**

测试覆盖：
- `TestCreateTasks`：13 tests（create-tasks 旧端点）
- `TestFormalProjectCreation`：3 tests
  - `test_create_formal_project_from_confirmed_unbound_draft` — 完整创建链路
  - `test_create_formal_project_is_idempotent` — 幂等保护
  - `test_create_formal_project_does_not_create_execution_side_effects` — 不创建副作用
- `TestTaskCreationHardening`：5 tests（原子性、task count 一致性等）

### 11.2 组合测试

```bash
cd runtime/orchestrator
python -m pytest tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py tests/test_project_director_task_creation.py -q
```

**结果：64 passed in 28.94s**

### 11.3 Python 编译检查

```bash
cd runtime/orchestrator
python -m compileall app tests
```

**结果：全部通过，无编译错误**

### 11.4 前端构建

```bash
cd apps/web
npm.cmd run build
```

**结果：501 modules transformed, built in 3.56s，无错误**

---

## 12. 是否确认未创建 Agent Session / Skill 绑定 / 仓库绑定

**是，已确认。** 测试 `test_create_formal_project_does_not_create_execution_side_effects` 显式断言：

- `AgentSessionTable` 查询结果为空
- `ProjectRoleSkillBindingTable` 查询结果为空
- `RepositoryWorkspaceTable` 查询结果为空

---

## 13. 是否确认未执行验证命令 / 未自动启动 Worker / 未创建 run

**是，已确认：**
- `RunTable` 查询结果为空
- `_create_task_queue_for_plan_version()` 仅执行 DB 写入，无 Worker 调度
- `verification_mechanisms[].command_or_method` 仅为字符串建议值，不经过任何执行路径
- `_BOUNDARY_ACTIONS` 明确包含 "不自动调用 Worker"、"不自动执行任务"
- `_FORMAL_PROJECT_CREATION_WARNINGS` 明确告知 "未自动启动 Worker"、"未执行验证命令"

---

## 14. 是否确认未调用真实 provider / Worker Pool / planning/apply / apply-local / 产品内 git-commit

**是，已确认：**

| 调用路径 | 检查结果 |
|---|---|
| `create_formal_project_from_plan_version()` | 仅调 `_require_confirmed_plan_version()` + `_ensure_proposed_tasks_are_valid()` + `_build_project_from_plan_version()` + `_create_task_queue_for_plan_version()` |
| `_create_task_queue_for_plan_version()` | 仅调 `_create_tasks_atomic()` + `_creation_repo.create()` + `_task_repo.publish_created()` |
| `_create_tasks_atomic()` | 仅构造 Task domain 对象 + `_task_repo.add_no_commit()` |
| 所有路径 | 无 `import openai`、无 HTTP 调用、无 Provider 引用、无 `subprocess` / `os.system`、无文件系统写入、无 git 操作 |

`_BOUNDARY_ACTIONS` 确认禁止所有以上行为。

---

## 15. 是否确认未改 Stage 3 / B1 / B2 evidence / checklist / ledger / total gate

**是，已确认。** 本次仅新增 `verification-stage4-formal-project-task-creation-20260531.md` 文档，未修改：
- `docs/product/ai-project-director/stage4-ai-project-draft-review-audit-20260531.md`（Stage 4-A）
- `docs/product/ai-project-director/verification-stage4-draft-review-modal-20260531.md`（Stage 4-B1）
- `docs/product/ai-project-director/verification-stage4-draft-content-enhancement-20260531.md`（Stage 4-B2）
- Checklist / Ledger / Total Gate 文档

---

## 16. 当前限制

1. **只到 Project + pending Tasks**：任务创建后状态为 pending，不自动执行
2. **不执行任务**：需要用户手动点击"启动一次执行"触发 Worker 调度
3. **Agent 编队建议仍为快照**：草案中的 `agent_team_suggestions` 不创建真实 Agent Session
4. **Skill 绑定建议仍为快照**：`binding_mode="suggested"`，不创建真实 Skill 绑定
5. **仓库绑定建议仍为快照**：`binding_mode="suggested"`，不创建真实仓库绑定
6. **验证机制建议仍为快照**：`command_or_method` 仅为字符串，不执行验证命令
7. **未调用真实 AI provider**：草案生成和项目创建均为确定性规则引擎，不调外部 API

---

## 17. Gate 结论

### 17.1 Stage 4-B3-A Gate

**Pass**

判定依据：

1. 后端 `POST /plan-versions/{id}/create-formal-project` API 存在且功能完整
2. confirmed plan version 可创建正式 Project + pending Task 队列
3. 非 confirmed 状态（pending_confirmation / rejected / superseded / draft）返回 409
4. proposed_tasks 为空时返回 422
5. approve / confirm 草案不自动创建 Project / Tasks
6. Project 可通过 `GET /projects/{project_id}` readback
7. Task 可通过 `GET /tasks/{task_id}` readback，含 `source_draft_id` 追溯
8. plan version 可追溯绑定 `project_id`
9. 幂等保护：第二次调用返回 `already_created=true`，不重复创建 Project/Tasks
10. Response 字段完整：project_id / project_name / created_task_ids / task_count / status / already_created / next_action（中文）/ warnings / forbidden_actions / gate_conclusion（中文）
11. Warnings 完整说明 4 项建议快照未真实创建/执行
12. Forbidden actions 完整列出 9 条边界
13. Project name 不以 # 开头，不等于 "作战计划摘要"，来源于目标摘要或 fallback
14. 前端"创建正式项目"按钮仅在 confirmed 状态出现，手动点击后才调用 API
15. 前端中文 loading / error / success 状态完整
16. 前端结果卡片展示项目名称、任务数、查看正式项目入口、查看执行中心入口、warnings 边界提示
17. "启动一次执行"为独立手动按钮，不自动触发
18. 不把 Agent/Skill/Repository/Verification 建议展示为已绑定或已执行
19. 21 测试通过（含 create-formal-project 专用 3 测试）+ 64 组合测试通过
20. 前端 build 通过
21. 不创建 Agent Session / Skill 绑定 / 仓库绑定 / Run
22. 不调用真实 provider / Worker Pool / planning/apply / apply-local / git-commit
23. 不自动执行验证命令
24. 不修改 Stage 3 / B1 / B2 evidence / checklist / ledger / total gate

### 17.2 AI Project Director Total Closure

**不涉及本次判定。** Total closure 仍为 Partial。Stage 4-B3-A 通过不代表总闭环通过。

### 17.3 CL-16

**不涉及本次判定。** CL-16 不得写 Pass。

---

## 18. 附录：关键代码位置速查

| 组件 | 路径 | 行号 |
|---|---|---|
| create-formal-project 路由 | `runtime/orchestrator/app/api/routes/project_director.py` | 1140-1192 |
| TaskCreationResponse DTO | `runtime/orchestrator/app/api/routes/project_director.py` | 1112-1137 |
| create_formal_project_from_plan_version | `runtime/orchestrator/app/services/project_director_task_creation_service.py` | 143-178 |
| _require_confirmed_plan_version | `runtime/orchestrator/app/services/project_director_task_creation_service.py` | 189-204 |
| _create_task_queue_for_plan_version | `runtime/orchestrator/app/services/project_director_task_creation_service.py` | 206-255 |
| _result_from_record | `runtime/orchestrator/app/services/project_director_task_creation_service.py` | 257-285 |
| _build_project_from_plan_version | `runtime/orchestrator/app/services/project_director_task_creation_service.py` | 287-302 |
| _derive_project_name_from_plan_version | `runtime/orchestrator/app/services/project_director_task_creation_service.py` | 304-336 |
| _FORMAL_PROJECT_CREATION_WARNINGS | `runtime/orchestrator/app/services/project_director_task_creation_service.py` | 58-63 |
| _BOUNDARY_ACTIONS | `runtime/orchestrator/app/services/project_director_task_creation_service.py` | 46-56 |
| _create_tasks_atomic (source_draft_id) | `runtime/orchestrator/app/services/project_director_task_creation_service.py` | 414-440 |
| confirm_plan_version (不自动创建) | `runtime/orchestrator/app/services/project_director_plan_service.py` | 623-675 |
| review action=approve (不自动创建) | `runtime/orchestrator/app/api/routes/project_director.py` | 900-904 |
| "创建正式项目"按钮 + 结果卡片 | `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx` | 104-115, 532-543, 557-706 |
| 前端 API createProjectDirectorTaskQueue | `apps/web/src/features/project-director/api.ts` | 86-95 |
| 前端 useCreateProjectDirectorTaskQueue | `apps/web/src/features/project-director/hooks.ts` | 49-64 |
| 前端 TaskCreationResponse types | `apps/web/src/features/project-director/types.ts` | 171-184 |
| 测试 TestFormalProjectCreation | `runtime/orchestrator/tests/test_project_director_task_creation.py` | 342-469 |

# Stage 4-B1 工作台 AI 项目主管草案审核弹窗 Runtime Evidence

> 文档类型：Stage 4-B1 草案审核弹窗 Runtime Evidence 验证
> 审计日期：2026-05-31
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`6b0343cf41d41913a4e146b4a71140cd80a1e0e6`
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> UX 路线图：`docs/product/AI-Dev-Orchestrator-AI-assisted-UX-roadmap-20260517.md`
> 前置审计：`docs/product/ai-project-director/stage4-ai-project-draft-review-audit-20260531.md`（Stage 4-A，commit d7c8092）

---

## 1. 基准 commit

```
6b0343cf41d41913a4e146b4a71140cd80a1e0e6
```

确认方式：`git fetch origin && git checkout main && git pull --ff-only origin main && git rev-parse HEAD`

变更范围（v4-A `d7c8092` → v4-B1 `6b0343cf`）：

```
12 files changed, 1800 insertions(+), 609 deletions(-)
```

关键变更文件：
- `runtime/orchestrator/app/api/routes/project_director.py` (+74 行：新增 review 路由)
- `runtime/orchestrator/app/services/project_director_plan_service.py` (+77 行：新增 reject_plan_version、request_changes)
- `runtime/orchestrator/tests/test_project_director_plan_versions.py` (+84 行：新增 TestReviewPlanVersion)
- `apps/web/src/pages/workbench/components/ProjectDirectorPlanReviewModal.tsx` (新增 215 行：草案审核弹窗)
- `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx` (重构：新增审核弹窗集成 + 动态状态)
- `apps/web/src/pages/workbench/WorkbenchPage.tsx` (+51 行：静默刷新状态)
- `apps/web/src/pages/workbench/components/WorkbenchRightRail.tsx` (+119 行：静默刷新)
- `apps/web/src/features/project-director/types.ts` (+33 行：新增 review 类型)
- `apps/web/src/features/project-director/api.ts` (+19 行：新增 review API)
- `apps/web/src/features/project-director/hooks.ts` (+9 行：新增 review hook)

---

## 2. 验证范围

验证 Stage 4-B1：工作台 AI 项目主管草案审核弹窗 + 拒绝 / 整改最小闭环的后端和前端实现。

覆盖：
- 后端 review API（approve / reject / request_changes）
- 前端草案审核弹窗（ProjectDirectorPlanReviewModal）
- 前端动态思考状态（directorStatusMessage）
- 右侧状态栏静默刷新
- 测试执行
- 安全边界验证

---

## 3. 后端 review API 验证结果

### 3.1 路由定义

| 项 | 值 |
|---|---|
| 方法 | `POST` |
| 路由 | `/project-director/plan-versions/{plan_version_id}/review` |
| Request Body | `{ "action": "approve" \| "reject" \| "request_changes", "feedback": "..." }` |
| Response | `PlanVersionReviewResponse` |
| 代码位置 | `runtime/orchestrator/app/api/routes/project_director.py:702-758` |

### 3.2 action=approve 验证

| 断言 | 预期 | 实际代码 | 结果 |
|---|---|---|---|
| pending_confirmation → confirmed | 转换状态 | 调用 `plan_service.confirm_plan_version()` | Pass |
| 返回中文 next_action | 中文文案 | `"草案已通过，可单独触发任务创建；不会自动执行。"` | Pass |
| 不创建任务 | 无 Task 创建 | 复用 confirm_plan_version，不调 create_tasks | Pass |
| 不调用 provider / Worker / planning/apply | 无 | 仅修改 plan_version 状态 | Pass |
| replacement_plan_version=null | null | `replacement = None` | Pass |

### 3.3 action=reject 验证

| 断言 | 预期 | 实际代码 | 结果 |
|---|---|---|---|
| pending_confirmation → rejected | 转换状态 | `reject_plan_version()` 设置 `status=REJECTED` | Pass |
| 返回中文 next_action | 中文文案 | `"草案已拒绝，可重新生成或调整目标后再提交。"` | Pass |
| replacement_plan_version=null | null | `replacement = None` | Pass |
| 不创建任务 | 无 Task 创建 | 仅修改 plan_version 状态 | Pass |
| reject 已 confirmed 返回 409 | 409 | `"only 'pending_confirmation'"` 判断 | Pass（由 confirm 逻辑保障） |

### 3.4 action=request_changes 验证

| 断言 | 预期 | 实际代码 | 结果 |
|---|---|---|---|
| feedback 必填 | 空字符串报错 | `_plan_repo.get_by_id()` 前 `normalized_feedback.strip()` 检查 | Pass |
| 旧版本被 rejected | 状态=rejected | `reject_plan_version()` → `REJECTED` | Pass |
| 生成 replacement_plan_version | 非 null | `create_plan_version(session_id, revision_notes=feedback)` | Pass |
| replacement version_no 递增 | 旧版 v1 → 新版 v2 | `get_next_version_no(session_id)` 递增 | Pass |
| replacement 为 pending_confirmation | 新草案可审 | `status=PENDING_CONFIRMATION` | Pass |
| 新草案 plan_summary 包含整改说明 | 含"## 整改说明"节 | `_generate_plan_from_session(revision_notes=feedback)` 添加整改说明 | Pass |
| 新草案 risks 含整改反馈 | 首项="整改反馈需重点处理：..." | `risks.insert(0, f"整改反馈需重点处理：...")` | Pass |
| 返回中文 next_action | 中文文案含版本号 | `"已生成整改版 v{version_no}，请重新审阅后再决定。"` | Pass |

### 3.5 无乱码问号验证

| 检查点 | 结果 |
|---|---|
| approve next_action | `"草案已通过，可单独触发任务创建；不会自动执行。"` — 无 `?` |
| reject next_action | `"草案已拒绝，可重新生成或调整目标后再提交。"` — 无 `?` |
| request_changes next_action | `"已生成整改版 v2，请重新审阅后再决定。"` — 无 `?` |
| plan_summary 含 `???` 乱码 | 测试明确断言 `"?" not in payload["next_action"]` |

### 3.6 confirmed plan version 不允许再次 reject

`reject_plan_version()` 和 `confirm_plan_version()` 均有 `status != PENDING_CONFIRMATION` 的 guard：

- `reject_plan_version()`（plan_service.py:277-281）：`only 'pending_confirmation' plan versions can be rejected`
- 路由层 catch `ValueError` → 409

---

## 4. 前端草案审核弹窗验证结果

### 4.1 "查看项目草案"入口

| 断言 | 结果 |
|---|---|
| 工作台 AI 主管对话区存在"查看项目草案"入口 | **Pass** |
| 按钮仅在 `planVersion.status === 'pending_confirmation'` 时出现 | **Pass**（`data-testid="view-project-director-plan-draft"`） |
| 点击后打开草案审核弹窗 | **Pass**（`onClick={() => setIsPlanReviewOpen(true)}`） |
| 草案生成后**自动弹出**弹窗 | **Pass**（`handleCreatePlanVersion` 中 `setIsPlanReviewOpen(true)`） |

代码位置：`DirectorChatEntry.tsx:524-531`（"查看项目草案"按钮）、`DirectorChatEntry.tsx:254`（生成后自动弹出）

### 4.2 弹窗展示内容

| 区域 | 展示内容 | 结果 |
|---|---|---|
| 作战计划摘要 | `planVersion.plan_summary`（Markdown 中文文案） | Pass |
| 阶段拆解 | `planVersion.phases[]`（P1/P2/P3 + name/goal + task_count_hint） | Pass |
| 拟议任务 | `planVersion.proposed_tasks[]`（title/description/priority_hint/suggested_role_code） | Pass |
| 验收标准 | `planVersion.acceptance_criteria[]`（list 展示） | Pass |
| 风险提示 | `planVersion.risks[]`（list 展示） | Pass |
| 审核结论 | 审核操作区（通过/拒绝/整改 + 整改意见 textarea） | Pass |

### 4.3 弹窗操作支持

| 操作 | 按钮标签 | 后端动作 | 结果 |
|---|---|---|---|
| 通过草案 | `"通过草案"` | `action="approve"` | Pass |
| 拒绝草案 | `"拒绝草案"` | `action="reject"` | Pass |
| 要求整改并生成新版本 | `"要求整改并生成新版本"` | `action="request_changes"` + feedback | Pass |

### 4.4 整改 textarea 必填

- `canRequestChanges = reviewFeedback.trim().length > 0 && !isReviewPending`
- 按钮 `disabled={!canRequestChanges}` — 空 feedback 时按钮禁用
- 后端二次验证：`request_changes()` 调用前检查 `normalized_feedback.strip()` 为空则返回 422

### 4.5 整改提交后生成新版本并继续可审阅

- `handleReviewPlanVersion("request_changes")` → 收到 `result.replacement_plan_version` 后 `setIsPlanReviewOpen(true)`
- 弹窗自动刷新为新版本内容，用户可继续审阅

### 4.6 不裸露英文枚举/内部字段

| 字段 | 显示方式 | 结果 |
|---|---|---|
| `planVersion.status` | 通过 `PROJECT_DIRECTOR_PLAN_STATUS_LABELS` 中文化 | Pass（"待审核"/"已通过"/"已拒绝"） |
| `priority_hint` | `TASK_PRIORITY_LABELS` 映射 + "优先级：{label}" 前缀 | Pass |
| `suggested_role_code` | `ROLE_CODE_LABELS` 映射 + "角色：{label}" 前缀 | Pass |
| gate_conclusion | 仅显示文本，不特殊处理 | Acceptable |

### 4.7 无乱码问号

- 所有中文文案均硬编码为字符串，无动态拼接英文枚举
- 未发现 `???` / `????` 乱码

---

## 5. 右侧状态栏静默刷新验证结果

### 5.1 实现方式

`WorkbenchPage.tsx` 改动：
- `stableOverviewData` — 缓存上次成功获取的 overview 数据
- `overviewIsInitialLoading = !stableOverviewData && (overviewQuery.isLoading || overviewQuery.isFetching)` — 仅首次无数据时显示 loading
- `refreshNotice` state — 手动刷新时显示轻提示，1.8 秒后自动消失

### 5.2 验证

| 场景 | 预期 | 实际 | 结果 |
|---|---|---|---|
| 首次无数据 | 显示 skeleton（6 个脉冲占位块） | `overviewIsInitialLoading=true` → 渲染 6 个 `animate-pulse` div | Pass |
| 已有数据后 refetch | 不整块 loading，数据保持显示 | `stableOverviewData` 保持旧值，新数据到达后静默更新 | Pass |
| 手动刷新 | 显示轻提示 "已刷新最新状态" | `refreshNotice` 显示 1.8s 后自动清除 | Pass |
| 不承担 AI 思考状态 | 右侧栏无 AI 思考指示 | 仅主对话区 `DirectorChatEntry` 显示 `directorStatusMessage` | Pass |

---

## 6. 测试命令与结果

### 6.1 后端 plan version 测试

```bash
cd runtime/orchestrator
python -m pytest tests/test_project_director_plan_versions.py -q
```

**结果：28 passed in 8.16s**

测试分解：
- `TestCreatePlanVersion`：7 passed
- `TestListPlanVersions`：3 passed
- `TestGetPlanVersion`：2 passed
- `TestConfirmPlanVersion`：6 passed（含 `test_confirmed_plan_does_not_create_tasks`）
- `TestReviewPlanVersion`：4 passed（新增）
- `TestPlanService`：6 passed

### 6.2 Python 编译检查

```bash
cd runtime/orchestrator
python -m compileall app tests
```

**结果：全部通过，无编译错误**

### 6.3 前端构建

```bash
cd apps/web
npm.cmd run build
```

**结果：501 modules transformed, built in 3.56s，无错误**

### 6.4 测试覆盖的 review 场景

| 测试 | 覆盖 |
|---|---|
| `test_reject_review_transitions_to_rejected` | reject action → status=rejected, replacement=null, Chinese next_action, no `?` |
| `test_approve_review_returns_chinese_next_action` | approve action → status=confirmed, Chinese next_action, no `?` |
| `test_request_changes_rejects_current_and_generates_new_version` | request_changes → old rejected + new version=2 pending_confirmation, plan_summary 含整改说明, risk 含整改反馈, history 列表 correct, no `?` |
| `test_request_changes_requires_feedback` | 空 feedback → 422 |

---

## 7. 是否出现乱码问号

**否。** 所有中文 next_action、plan_summary、UI 文案均为确定性硬编码中文字符串，无动态拼接英文枚举值。测试明确断言 `"?" not in payload["next_action"]`。

---

## 8. 是否调用真实 provider

**否。** 整个 review 流程（approve / reject / request_changes）仅修改 `ProjectDirectorPlanVersion.status` 和创建新 PlanVersion 记录。`_generate_plan_from_session()` 为确定性规则引擎，不调用 OpenAI / DeepSeek / 任何外部 API。

确认依据：
- `project_director_plan_service.py` 无 `import openai`、无 HTTP 调用、无 Provider 引用
- `project_director.py` review 路由只调用 `plan_service.confirm_plan_version()` / `reject_plan_version()` / `request_changes()`

---

## 9. 是否调用 Worker Pool / planning/apply / apply-local / git-commit

**否。** 审查以下代码路径确认：

| 路径 | 检查结果 |
|---|---|
| `plan_service.confirm_plan_version()` | 仅创建 Domain Model + `_plan_repo.update()`，无 worker 调用 |
| `plan_service.reject_plan_version()` | 仅 `_plan_repo.update()` |
| `plan_service.request_changes()` | `reject_plan_version()` + `create_plan_version()`，均仅数据库操作 |
| `plan_service.create_plan_version()` | `_generate_plan_from_session()` + `_plan_repo.create()` |

所有 forbidden_actions 均保持：
```python
"不自动创建任务", "不自动调用 Worker", "不写仓库",
"不把计划确认等同于执行完成", "不调用 planning/apply"
```

---

## 10. 动态思考状态验证结果

### 10.1 directorStatusMessage 实现

`DirectorChatEntry.tsx:120-148`，基于 `useMemo` 计算：

| 触发条件 | 显示文案 | 结果 |
|---|---|---|
| `createPlanVersionMutation.isPending` | "AI 项目主管正在思考项目草案，请稍候。" | Pass |
| `reviewPlanVersionMutation.isPending && action==request_changes` | "AI 项目主管正在根据整改意见重新规划新版本。" | Pass |
| `reviewPlanVersionMutation.isPending && action==approve` | "AI 项目主管正在提交通过结论。" | Pass |
| `reviewPlanVersionMutation.isPending && action==reject` | "AI 项目主管正在记录驳回结论。" | Pass |
| 非 pending 状态 | `planReviewMessage`（后端返回的 next_action） | Pass |

### 10.2 展示位置

`directorStatusMessage` 非空时在主对话区顶部以 cyan-border 卡片展示（`DirectorChatEntry.tsx:345-349`），不混入右侧栏。右侧栏不承担 AI 思考状态。

---

## 11. 当前限制

1. **仍为确定性规则重规划**：`_generate_plan_from_session()` 基于关键词匹配，不调用真实 AI Provider
2. **不调用真实 AI provider**：草案生成和重新规划均为规则引擎
3. **尚未实现 Agent 编队字段**：`PlanVersion` 仅有 `proposed_tasks[].suggested_role_code`，无 Agent 名称/职责/协作关系
4. **尚未实现 Skill 绑定字段**：无 Skill 绑定方案信息
5. **尚未实现验证机制建议字段**：无验证命令/模板建议
6. **尚未实现仓库绑定建议字段**：无仓库 URL/主分支/关注目录建议
7. **尚未实现从草案创建完整 Project**：confirm 后仍需手动 create-tasks，且依赖已有 project_id

---

## 12. Gate 结论

### 12.1 Stage 4-B1 Gate

**Pass**

判定依据：

1. 后端 review API 新增 `POST /plan-versions/{id}/review`，支持 approve/reject/request_changes
2. approve → confirmed，返回中文 next_action，不创建任务
3. reject → rejected，返回中文 next_action，不创建任务
4. request_changes → 旧版 rejected + 新版 pending_confirmation，version_no 递增
5. replacement plan_summary 包含整改说明，risks 含整改反馈
6. feedback 必填验证（后端 422 + 前端 button disabled）
7. 前端 `ProjectDirectorPlanReviewModal` 弹窗完整实现 6 个内容区域 + 3 个操作按钮
8. "查看项目草案"入口在对话区正确显示，草案生成后自动弹出弹窗
9. `directorStatusMessage` 提供 4 种动态思考状态文案
10. 右侧栏静默刷新（skeleton 初始加载 + stableData 缓存 + refreshNotice 轻提示）
11. 弹窗不裸露英文枚举（status/priority_hint/role_code 均有中文映射）
12. 28 测试通过 + 前端 build 通过
13. 无乱码问号
14. 不调用 provider / Worker / planning/apply / apply-local / git-commit

### 12.2 AI Project Director Total Closure

**不涉及本次判定。** Total closure 仍为 Partial（CL-16 Evidence Partial）。Stage 4-B1 通过不代表总闭环通过。

### 12.3 CL-16

**不涉及本次判定。**

### 12.4 不覆盖的 Stage 4-A P0 缺口

以下 Stage 4-A 审计中的 P0 缺口在本阶段已解决：
- P0-1 草案审核弹窗 → **已解决**（ProjectDirectorPlanReviewModal）
- P0-2 拒绝草案能力 → **已解决**（reject action）
- P0-3 整改意见输入与提交 → **已解决**（request_changes + feedback）
- P0-4 根据整改意见生成新版本 → **已解决**（request_changes → replacement_plan_version）

以下仍为未解决（保留到后续阶段）：
- P0-5~P0-10（Agent 编队、Skill 绑定、验证建议、仓库建议、项目创建等）→ **仍开放**
- P1-1 动态思考状态 → **已部分解决**（directorStatusMessage），但仍无 loading dots/skeleton/step progress

---

## 13. 附录：修改文件清单

| 文件 | 变更量 | 变更类型 |
|---|---|---|
| `runtime/orchestrator/app/api/routes/project_director.py` | +74 | 新增 review 路由 + DTO |
| `runtime/orchestrator/app/services/project_director_plan_service.py` | +77 | 新增 reject_plan_version / request_changes |
| `runtime/orchestrator/tests/test_project_director_plan_versions.py` | +84 | 新增 TestReviewPlanVersion (4 tests) |
| `apps/web/src/pages/workbench/components/ProjectDirectorPlanReviewModal.tsx` | +215 | **新文件**：草案审核弹窗 |
| `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx` | 重构 | 集成审核弹窗 + 动态状态 |
| `apps/web/src/pages/workbench/WorkbenchPage.tsx` | +51 | 静默刷新：stableOverviewData + refreshNotice |
| `apps/web/src/pages/workbench/components/WorkbenchRightRail.tsx` | +119 | 静默刷新：initialLoading skeleton + refreshNotice |
| `apps/web/src/features/project-director/types.ts` | +33 | 新增 PlanReviewAction / PlanReviewResponse / status labels |
| `apps/web/src/features/project-director/api.ts` | +19 | 新增 reviewProjectDirectorPlanVersion |
| `apps/web/src/features/project-director/hooks.ts` | +9 | 新增 useReviewProjectDirectorPlanVersion |

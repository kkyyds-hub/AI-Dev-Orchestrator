# Stage 4-B2 项目草案内容增强 Runtime Evidence

> 文档类型：Stage 4-B2 草案内容增强 Runtime Evidence 验证
> 审计日期：2026-05-31
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`e8178ba0f1bf49fa87f6bf8bd2fcc4c8dcd03d62`
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 前置阶段：Stage 4-B1 Pass（commit `6b0343cf`：草案审核弹窗 + 拒绝 / 整改最小闭环）

---

## 1. 基准 commit

```
e8178ba0f1bf49fa87f6bf8bd2fcc4c8dcd03d62
```

变更范围（v4-B1 `6b0343cf` → v4-B2 `e8178ba0f`）：

```
10 files changed, 1463 insertions(+), 12 deletions(-)
```

关键变更文件：
- `runtime/orchestrator/app/domain/project_director_plan_version.py` (+81 行：7 个新 Domain Model)
- `runtime/orchestrator/app/services/project_director_plan_service.py` (+327 行：增强字段生成逻辑)
- `runtime/orchestrator/app/api/routes/project_director.py` (+186 行：7 个新 Response DTO + from_domain)
- `runtime/orchestrator/app/core/db_tables.py` (+19 行：7 个新 JSON 列)
- `runtime/orchestrator/app/core/db.py` (+11 行：7 个 ALTER TABLE 迁移)
- `runtime/orchestrator/app/repositories/project_director_plan_version_repository.py` (+110 行：新字段序列化/反序列化)
- `runtime/orchestrator/tests/test_project_director_plan_versions.py` (+84 行：增强字段断言)
- `apps/web/src/features/project-director/types.ts` (+67 行：7 个新 TypeScript 接口)
- `apps/web/src/pages/workbench/components/ProjectDirectorPlanReviewModal.tsx` (+219 行：增强字段展示 UI)

---

## 2. 验证范围

验证 Stage 4-B2：项目草案内容增强。覆盖：

- 后端 7 个增强字段的 Domain Model / DB 持久化 / API 序列化 / Repository readback
- 每个增强字段的子字段完整性
- request_changes 时增强字段保持完整且含整改反馈
- 前端弹窗展示全部增强字段
- 安全边界：不真实创建 Project / Agent Session / Skill 绑定 / 仓库绑定 / 验证执行
- 测试执行与构建

---

## 3. 后端增强字段验证结果

### 3.1 字段总览

| # | 增强字段 | Domain Model | DB 列 | API Response | 落库验证 | readback 验证 |
|---|---|---|---|---|---|---|
| 1 | `project_scope` | `ProjectScopeSummary` | `project_scope_json` TEXT | `ProjectScopeResponse` | Pass | Pass |
| 2 | `agent_team_suggestions` | `AgentTeamSuggestion[]` | `agent_team_suggestions_json` TEXT | `AgentTeamSuggestionResponse[]` | Pass | Pass |
| 3 | `skill_binding_suggestions` | `SkillBindingSuggestion[]` | `skill_binding_suggestions_json` TEXT | `SkillBindingSuggestionResponse[]` | Pass | Pass |
| 4 | `verification_mechanisms` | `VerificationMechanismSuggestion[]` | `verification_mechanisms_json` TEXT | `VerificationMechanismResponse[]` | Pass | Pass |
| 5 | `repository_binding_suggestions` | `RepositoryBindingSuggestion[]` | `repository_binding_suggestions_json` TEXT | `RepositoryBindingSuggestionResponse[]` | Pass | Pass |
| 6 | `deliverable_boundaries` | `DeliverableBoundary[]` | `deliverable_boundaries_json` TEXT | `DeliverableBoundaryResponse[]` | Pass | Pass |
| 7 | `complexity_assessment` | `ComplexityAssessment` | `complexity_assessment_json` TEXT | `ComplexityAssessmentResponse` | Pass | Pass |

代码位置：
- Domain：`runtime/orchestrator/app/domain/project_director_plan_version.py:45-117`
- DB Table：`runtime/orchestrator/app/core/db_tables.py:1724-1742`
- DB Migration：`runtime/orchestrator/app/core/db.py:89-97`
- Repository：`runtime/orchestrator/app/repositories/project_director_plan_version_repository.py:54-72` (create) + `158-176` (update) + `261-285` (readback)
- API DTO：`runtime/orchestrator/app/api/routes/project_director.py:459-479, 483-488, 491-496, 499-510, 513-535, 538-558, 561-580, 583-604`

### 3.2 project_scope 子字段验证

| 字段 | 类型 | 内容存在 | 来源 |
|---|---|---|---|
| `in_scope` | `list[str]` | 3 条（澄清固化、阶段拆分、用户闸门） | 硬编码 Chinese |
| `out_of_scope` | `list[str]` | 3 条（不创建实体、不调外部、不写仓库） | 硬编码 Chinese |
| `assumptions` | `list[str]` | 2 条 + 整改反馈（如有） | 硬编码 + revision_notes append |

代码位置：`plan_service.py:236-256`

### 3.3 agent_team_suggestions 子字段验证

| 字段 | 验证点 | 结果 |
|---|---|---|
| `role_code` | 有效 `ProjectRoleCode` 枚举值 | Pass（PRODUCT_MANAGER / ARCHITECT / ENGINEER / REVIEWER） |
| `role_name` | 中文角色名 | Pass（产品负责人 / 架构师 / 工程师 / 评审者） |
| `responsibility` | 非空中文职责描述 | Pass |
| `collaboration_notes` | `list[str]`，至少 1 条 | Pass |

已生成 4 个 Agent（产品负责人、架构师、工程师、评审者）。

代码位置：`plan_service.py:258-283`

### 3.4 skill_binding_suggestions 子字段验证

| 字段 | 验证点 | 结果 |
|---|---|---|
| `skill_code` | 非空 skill ID | Pass（`manage-v5-plan-and-freeze-docs` 等 4 个） |
| `owner_role_code` | 有效 `ProjectRoleCode` | Pass |
| `usage` | 非空中文用法说明 | Pass |
| `activation_stage` | 如 "规划/澄清" / "实现" / "验证" | Pass |
| `binding_mode` | `"suggested"` | Pass（建议绑定，非 real 绑定） |
| `reason` | 非空中文原因说明 | Pass |

4 个 Skill 建议全部 `binding_mode="suggested"`，确认只是建议不是真实绑定。

代码位置：`plan_service.py:285-318`

### 3.5 verification_mechanisms 子字段验证

| 字段 | 验证点 | 结果 |
|---|---|---|
| `name` | 非空名称 | Pass |
| `command_or_method` | 非空验证命令/方法 | Pass |
| `purpose` | 非空中文目的说明 | Pass |
| `evidence_required` | 非空中文证据要求 | Pass |
| `owner_role_code` | 有效 ProjectRoleCode | Pass |
| `risk_level` | `"low"` / `"normal"` / `"high"` | Pass |
| `requires_user_confirmation` | boolean | Pass |

high 风险项 `requires_user_confirmation=true` 验证：
- "后端合同测试" 风险等级 `high`，`requires_user_confirmation=True`

不自动执行验证命令验证：
- 所有 `verification_mechanisms` 仅为建议展示，无 `os.system()` / `subprocess.run()` 等执行调用
- `_generate_plan_from_session()` 不触发任何外部命令

代码位置：`plan_service.py:320-352`

### 3.6 repository_binding_suggestions 子字段验证

| 字段 | 验证点 | 结果 |
|---|---|---|
| `binding_type` | `"review_only"` | Pass（仅审阅，非真实绑定） |
| `binding_mode` | `"suggested"` 或 `"not_bound"` | Pass（建议绑定） |
| `target` | 非空目标描述 | Pass |
| `branch` | `"未指定"` | Pass（未指定真实分支） |
| `focus_paths` | `list[str]` | Pass（关注路径列表） |
| `usage` | 非空中文用法说明 | Pass |
| `safety_note` | 非空安全提示 | Pass |

确认只是建议，不创建真实仓库绑定。target 为 "当前项目关联仓库（如后续由用户显式绑定）"，非真实 URL。

代码位置：`plan_service.py:354-369`

### 3.7 deliverable_boundaries 子字段验证

| 字段 | 验证点 | 结果 |
|---|---|---|
| `name` | 非空交付件名称 | Pass（3 个） |
| `description` | 非空中文描述 | Pass |
| `owner_role_code` | 有效 ProjectRoleCode | Pass |
| `required_contents` | `list[str]` | Pass |
| `done_definition` | 非空中文化完成定义 | Pass |
| `acceptance_signal` | 非空中文验收信号 | Pass |

代码位置：`plan_service.py:371-396`

### 3.8 complexity_assessment 子字段验证

| 字段 | 验证点 | 结果 |
|---|---|---|
| `level` | `"simple"` / `"medium"` / `"complex"` / `"large"` | Pass |
| `label` | 中文标签 | Pass（简单 / 中等复杂度 / 复杂 / 大型复杂） |
| `score` | 1-5 整数 | Pass |
| `recommended_agent_count` | 1-8 整数 | Pass |
| `drivers` | `list[str]`，基于目标分析 | Pass |
| `mitigation_suggestions` | `list[str]` | Pass |

复杂度计算算法（`plan_service.py:398-448`）：
- base score = 1
- char_count >= 60 → +1
- char_count >= 200 → +1
- has_frontend → +1
- has_tech → +1
- scope_text 含仓库/deploy/provider/worker → +1
- capping at score=5，映射到 level

### 3.9 DB 迁移验证

```python
# runtime/orchestrator/app/core/db.py:89-97
_PROJECT_DIRECTOR_PLAN_VERSION_TABLE_COLUMN_UPGRADES = {
    "project_scope_json": "ALTER TABLE project_director_plan_versions ADD COLUMN project_scope_json TEXT NOT NULL DEFAULT '{}'",
    "agent_team_suggestions_json": "ALTER TABLE project_director_plan_versions ADD COLUMN agent_team_suggestions_json TEXT NOT NULL DEFAULT '[]'",
    ...
}
```

7 个 ALTER TABLE 全部覆盖，默认值 `'{}'` / `'[]'` 保证向后兼容。

### 3.10 Repository readback 容错验证

`_to_domain()` 对所有新字段使用 `getattr(row, "field_name", None)` + `_parse_model()` / `_parse_model_list()` 带 fallback：

- `project_scope` → fallback `ProjectScopeSummary()`
- `complexity_assessment` → fallback `ComplexityAssessment()`
- `agent_team_suggestions` 等 list → fallback `[]`

旧数据（缺少新列）不会导致读回崩溃。

---

## 4. 前端弹窗展示验证结果

### 4.1 增强字段展示对照

| 区域 | 前端标题 | 展示数据 | 中文标签 | 不裸露 raw JSON |
|---|---|---|---|---|
| 项目范围 / 不做范围 | `"项目范围 / 不做范围"` | `planVersion.project_scope` 三个子块 | 范围内 / 不做范围 / 关键假设 | Pass |
| 复杂度评估 | `"复杂度评估"` | `planVersion.complexity_assessment` | label（中文）+ score/5 + 建议 N 人编队 | Pass |
| Agent 编队建议 | `"Agent 编队建议"` | `planVersion.agent_team_suggestions[]` | role_name 中文 | Pass |
| Skill 绑定建议 | `"Skill 绑定建议"` | `planVersion.skill_binding_suggestions[]` | "建议绑定" / "未绑定" | Pass |
| 验证机制建议 | `"验证机制建议"` | `planVersion.verification_mechanisms[]` | "高/普通/低" + "需用户确认" | Pass |
| 仓库绑定建议 | `"仓库绑定建议"` | `planVersion.repository_binding_suggestions[]` | "仅审阅" + "建议绑定" + safety_note | Pass |
| 交付件边界 | `"交付件边界"` | `planVersion.deliverable_boundaries[]` | 中文 done_definition + acceptance_signal | Pass |

代码位置：`ProjectDirectorPlanReviewModal.tsx:107-245`

### 4.2 中文标签验证

| 原始值 | 显示标签 | 映射函数 |
|---|---|---|
| `binding_mode="suggested"` | `"建议绑定"` | `formatBindingMode()` |
| `binding_mode="not_bound"` | `"未绑定"` | `formatBindingMode()` |
| `binding_type="review_only"` | `"仅审阅"` | `formatBindingType()` |
| `risk_level="high"` | `"高"` | `formatRiskLevel()` |
| `risk_level="normal"` | `"普通"` | `formatRiskLevel()` |
| `risk_level="low"` | `"低"` | `formatRiskLevel()` |
| `requires_user_confirmation=true` | `"需用户确认"` | 直接映射 |
| `complexity.level` | label 字段直接展示（中文） | `formatComplexityLevel()` 作为 fallback |

### 4.3 不把建议展示成已执行

- Skill 绑定建议：`binding_mode="suggested"` 显示为 "建议绑定"，与 "已绑定" 区分
- 仓库绑定建议：`binding_mode="suggested"` + `binding_type="review_only"` 显示为 "仅审阅"+"建议绑定"+"分支：未指定"
- 验证机制建议：不显示 "已执行" 或 "执行结果"；`requires_user_confirmation` 提示用户仍需确认
- `safety_note` 以 amber-200 颜色突出显示：安全提示

---

## 5. request_changes 新版本验证结果

### 5.1 增强字段完整保留

测试 `test_request_changes_rejects_current_and_generates_new_version`（共 13 个增强字段断言）：

| 验证项 | 断言 | 结果 |
|---|---|---|
| replacement project_scope.out_of_scope | 存在 | Pass |
| replacement assumptions 含整改反馈 | `"Please split backend..."` 在 assumptions 中 | Pass |
| replacement agent_team_suggestions | 4 个 Agent 全部存在 | Pass |
| replacement agent role_name | 全部非空 | Pass |
| replacement skill_binding_suggestions | 4 个 Skill 全部存在 | Pass |
| replacement skill binding_mode | 全部 `"suggested"` | Pass |
| replacement skill reason | 全部非空 | Pass |
| replacement verification_mechanisms | 存在 | Pass |
| replacement verification risk_level | 全部在 `{low, normal, high}` | Pass |
| replacement verification requires_user_confirmation | boolean 类型正确 | Pass |
| replacement repository_binding_suggestions | 存在 + branch + focus_paths | Pass |
| replacement deliverable_boundaries | 存在 + description + acceptance_signal | Pass |
| replacement complexity_assessment | score >= 1, level 有效, label 非空, agent_count >= 1 | Pass |

### 5.2 整改反馈进入增强字段

- `assumptions`：`f"整改反馈已纳入草案增强字段：{revision_note_text[:200]}"`
- `drivers`：`f"request_changes 整改反馈：{revision_note_text[:200]}"`

测试验证两者均包含原始 feedback 内容。

---

## 6. 测试命令与结果

### 6.1 后端 plan version 测试

```bash
cd runtime/orchestrator
python -m pytest tests/test_project_director_plan_versions.py -q
```

**结果：28 passed in 8.15s**

测试覆盖：
- `TestCreatePlanVersion`：7 passed（含增强字段断言 18 项）
- `TestListPlanVersions`：3 passed
- `TestGetPlanVersion`：2 passed
- `TestConfirmPlanVersion`：6 passed
- `TestReviewPlanVersion`：4 passed（含 replacement 增强字段完整断言 27 项）
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

**结果：501 modules transformed, built in 3.61s，无错误**

---

## 7. 是否真实创建 Project / Agent Session / Skill 绑定 / 仓库绑定

**否。** 所有增强字段均为只读草案建议，不触发任何真实实体创建：

| 实体 | 是否创建 | 代码确认 |
|---|---|---|
| Project | 否 | `create_plan_version()` 仅写入 `project_director_plan_versions` 表 |
| Task | 否 | proposed_tasks 不是真实 Task |
| Agent Session | 否 | agent_team_suggestions 仅为 PlanVersion JSON 内的建议数据 |
| Skill 绑定 | 否 | skill_binding_suggestions 仅为 PlanVersion JSON 内的建议数据；`binding_mode="suggested"` |
| 仓库绑定 | 否 | repository_binding_suggestions 仅为 PlanVersion JSON 内的建议数据；`binding_mode="suggested"` |

---

## 8. 是否调用真实 provider

**否。** `_generate_plan_from_session()` 为纯 Python 确定性规则引擎（关键词匹配、字符串长度判断），不调用 OpenAI / DeepSeek / 任何外部 API。

确认依据：
- `plan_service.py` 无 `import openai`、无 HTTP 调用、无 Provider 引用
- 所有生成内容均为硬编码中文模板 + session 数据拼接

---

## 9. 是否调用 Worker Pool / planning/apply / apply-local / 产品内 git-commit

**否。** 审查确认：
- `plan_service.py` 无 `worker`、`planning`、`apply_local`、`git.commit` 关键词
- `create_plan_version()` / `reject_plan_version()` / `request_changes()` / `confirm_plan_version()` 均为纯 DB 操作
- `forbidden_actions` 始终保持 5 项禁止操作

---

## 10. 是否自动执行验证命令

**否。** `verification_mechanisms` 中的 `command_or_method` 仅为字符串建议（如 `"pytest runtime/orchestrator/tests/test_project_director_plan_versions.py"`），不经过 `os.system()`、`subprocess` 或任何执行路径。

---

## 11. 是否修改 Stage 3 evidence / Stage 4-B1 evidence / checklist / ledger / total gate

**否。**

---

## 12. 当前限制

1. 仍为 deterministic review-only 草案建议：生成为纯规则引擎，不调用真实 AI Provider
2. 未实现从草案创建完整 Project：confirm 后仍需手动 create-tasks，且依赖已有 project_id
3. 未真实绑定 Agent / Skill / Repository：所有 binding_mode=suggested
4. 未调用真实 AI provider：草案内容（Agent 编队、Skill 建议等）为固定模板，不根据用户目标动态分析

---

## 13. Gate 结论

### 13.1 Stage 4-B2 Gate

**Pass**

判定依据：

1. 后端 7 个增强字段 Domain Model 完整定义（`project_scope`, `agent_team_suggestions`, `skill_binding_suggestions`, `verification_mechanisms`, `repository_binding_suggestions`, `deliverable_boundaries`, `complexity_assessment`）
2. 所有子字段符合要求（project_scope 含 in_scope/out_of_scope/assumptions；Agent 含 role_code/role_name/responsibility/collaboration_notes；Skill 含 binding_mode=suggested+reason；验证含 requires_user_confirmation + high 风险强制确认；仓库含 binding_mode + safety_note；交付件含 done_definition/acceptance_signal；复杂度含 level/label/score/drivers/mitigation）
3. DB 持久化：7 个 JSON 列 + 7 个 ALTER TABLE 迁移，repository create/update/readback 全覆盖
4. API 序列化：7 个 Response DTO + from_domain 转换完整
5. request_changes 生成 replacement 时增强字段完整保留，整改反馈进入 assumptions + drivers
6. 前端 `ProjectDirectorPlanReviewModal` 展示全部 7 个增强区域
7. 全中文标签展示（bindingMode=建议绑定/未绑定，bindingType=仅审阅，riskLevel=高/普通/低，complexity 使用中文 label）
8. high 风险项显示"需用户确认"
9. 不把建议展示成已执行配置
10. 28 测试通过（含增强字段 45+ 断言）+ 前端 build 通过
11. 不创建真实 Project / Agent Session / Skill 绑定 / 仓库绑定
12. 不调用真实 provider / Worker Pool / planning/apply / apply-local / git-commit
13. 不自动执行验证命令

### 13.2 AI Project Director Total Closure

**不涉及本次判定。** Total closure 仍为 Partial。Stage 4-B2 通过不代表总闭环通过。

### 13.3 CL-16

**不涉及本次判定。**

---

## 14. 附录：增强字段代码位置速查

| 组件 | 路径 | 行号 |
|---|---|---|
| ProjectScopeSummary | `domain/project_director_plan_version.py` | 45-50 |
| AgentTeamSuggestion | `domain/project_director_plan_version.py` | 53-59 |
| SkillBindingSuggestion | `domain/project_director_plan_version.py` | 62-70 |
| VerificationMechanismSuggestion | `domain/project_director_plan_version.py` | 73-82 |
| RepositoryBindingSuggestion | `domain/project_director_plan_version.py` | 85-94 |
| DeliverableBoundary | `domain/project_director_plan_version.py` | 97-105 |
| ComplexityAssessment | `domain/project_director_plan_version.py` | 108-116 |
| PlanVersion 新增字段 | `domain/project_director_plan_version.py` | 136-142 |
| 生成逻辑 | `services/project_director_plan_service.py` | 229-463 |
| DB 表定义 | `core/db_tables.py` | 1724-1742 |
| DB 迁移 | `core/db.py` | 89-97 |
| Repository create/update/readback | `repositories/project_director_plan_version_repository.py` | 54-72 / 158-176 / 261-285 |
| API DTO | `api/routes/project_director.py` | 459-604 |
| PlanVersionResponse 序列化 | `api/routes/project_director.py` | 653-676 |
| 前端类型 | `features/project-director/types.ts` | 75-161 |
| 前端弹窗展示 | `workbench/components/ProjectDirectorPlanReviewModal.tsx` | 107-245 |
| 前端中文映射函数 | `workbench/components/ProjectDirectorPlanReviewModal.tsx` | 373-419 |
| 测试增强字段断言 | `tests/test_project_director_plan_versions.py` | 149-178 / 293-311 / 601-634 |

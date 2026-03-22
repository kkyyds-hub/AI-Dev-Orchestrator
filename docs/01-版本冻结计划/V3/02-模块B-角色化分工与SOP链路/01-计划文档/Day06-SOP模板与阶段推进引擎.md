# Day06 SOP模板与阶段推进引擎

- 版本：`V3`
- 模块 / 提案：`模块B：角色化分工与SOP链路`
- 原始日期：`2026-04-11`
- 原始来源：`V3 正式版总纲 / 模块B：角色化分工与SOP链路 / Day06`
- 当前回填状态：**已完成**
- 回填口径：已按 Day06 范围完成 SOP 模板目录、阶段清单、模板任务生成、项目阶段推进接入与前端展示收口。

---

## 今日目标

把项目推进从自由对话改为 SOP 驱动的阶段链路，让角色协作建立在模板化流程之上。

---

## 当日交付

1. `runtime/orchestrator/app/services/sop_engine_service.py`
2. `runtime/orchestrator/app/services/project_stage_service.py`
3. `runtime/orchestrator/app/services/context_builder_service.py`
4. `runtime/orchestrator/app/api/routes/projects.py`
5. `apps/web/src/features/projects/ProjectSopPanel.tsx`
6. `apps/web/src/features/projects/components/StageChecklist.tsx`

---

## 验收点

1. 项目可以选择一套 SOP 模板
2. 每个阶段有明确必需输入、产出和守卫条件
3. SOP 模板能驱动任务生成与阶段推进
4. 用户能看到当前项目处于哪个 SOP 阶段
5. SOP 链路具备最小可扩展性，后续可新增模板

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：已新增 Day06 `SopEngineService`，为项目提供内置 SOP 模板目录、模板选择、阶段清单和当前阶段模板任务生成；`ProjectStageService` 已接入 SOP 守卫，在项目已选择模板时会按“责任角色已启用 + 当前阶段 SOP 任务已完成”口径阻断或放行阶段推进，并在推进成功后自动补齐新阶段任务；项目详情接口已补充 `sop_snapshot`，前端项目详情页新增 `ProjectSopPanel` 与 `StageChecklist`，可查看当前阶段输入、产出、守卫条件、责任角色、模板任务与上下文摘要。
- 回填证据：
1. `runtime/orchestrator/app/services/sop_engine_service.py` 已落地两套内置模板（`std_delivery` / `hotfix_flow`），并提供模板选择、阶段任务同步、SOP 守卫与快照构建能力
2. `runtime/orchestrator/app/services/project_stage_service.py` 已接入 SOP 守卫评估，并在成功推进阶段后自动生成下一阶段模板任务
3. `runtime/orchestrator/app/services/context_builder_service.py` 已补充项目阶段上下文摘要构建能力，用于输出当前 SOP 阶段的结构化上下文
4. `runtime/orchestrator/app/api/routes/projects.py` 已补充 `GET /projects/sop-templates`、`PUT /projects/{project_id}/sop-template`，并在 `GET /projects/{project_id}` 返回 `sop_snapshot`
5. `apps/web/src/features/projects/ProjectSopPanel.tsx` 与 `apps/web/src/features/projects/components/StageChecklist.tsx` 已接入项目详情页，支持模板选择、阶段清单展示与当前阶段任务查看
6. `runtime/orchestrator/scripts/v3b_day06_sop_engine_smoke.py` 已完成最小烟测，覆盖模板目录查询、模板绑定、阶段任务生成、阶段守卫拦截、推进成功与自动补齐下一阶段任务

---

## 关键产物路径

1. `runtime/orchestrator/app/services/sop_engine_service.py`
2. `runtime/orchestrator/app/services/project_stage_service.py`
3. `runtime/orchestrator/app/services/context_builder_service.py`
4. `runtime/orchestrator/app/api/routes/projects.py`
5. `apps/web/src/features/projects/ProjectSopPanel.tsx`
6. `apps/web/src/features/projects/components/StageChecklist.tsx`

---

## 上下游衔接

- 前一日：Day05 角色目录与身份配置模型
- 后一日：Day07 角色任务分派与协作链路
- 对应测试文档：`docs/01-版本冻结计划/V3/02-模块B-角色化分工与SOP链路/02-测试验证/Day06-SOP模板与阶段推进引擎-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；若当日未完成，则顺延到下一日并同步更新模块状态与测试文档。

### 备注
1. Day06 只实现 SOP 模板、阶段清单、模板任务生成和阶段推进接入，不扩展到 Day07 的角色任务归属、协作交接或工作台能力。

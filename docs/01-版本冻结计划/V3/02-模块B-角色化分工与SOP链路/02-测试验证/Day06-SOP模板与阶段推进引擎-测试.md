# Day06 SOP模板与阶段推进引擎 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V3/02-模块B-角色化分工与SOP链路/01-计划文档/Day06-SOP模板与阶段推进引擎.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 项目可以选择一套 SOP 模板
2. 每个阶段有明确必需输入、产出和守卫条件
3. SOP 模板能驱动任务生成与阶段推进
4. 用户能看到当前项目处于哪个 SOP 阶段
5. SOP 链路具备最小可扩展性，后续可新增模板

---

## 实际验证动作

1. 核对关键实现文件已落地：
   - `runtime/orchestrator/app/services/sop_engine_service.py`
   - `runtime/orchestrator/app/services/project_stage_service.py`
   - `runtime/orchestrator/app/services/context_builder_service.py`
   - `runtime/orchestrator/app/api/routes/projects.py`
   - `apps/web/src/features/projects/ProjectSopPanel.tsx`
   - `apps/web/src/features/projects/components/StageChecklist.tsx`
2. 运行后端最小烟测：`runtime/orchestrator/scripts/v3b_day06_sop_engine_smoke.py`
3. 回归执行 Day04 / Day05 既有烟测，确认 SOP 接入未破坏项目阶段守卫与角色目录：
   - `runtime/orchestrator/scripts/v3a_day04_project_stage_guard_smoke.py`
   - `runtime/orchestrator/scripts/v3b_day05_role_catalog_smoke.py`
4. 执行前端构建：`apps/web -> npm run build`

---

## 当前回填结果

- 结果：**通过**
- 状态口径：Day06 范围内的 SOP 模板目录、阶段清单、模板任务生成、阶段推进接入与前端展示已完成，且最小烟测/回归/前端构建均通过。
- 证据：
1. `v3b_day06_sop_engine_smoke.py` 已验证：
   - `GET /projects/sop-templates` 返回 `std_delivery` 与 `hotfix_flow`
   - `PUT /projects/{project_id}/sop-template` 可绑定模板并生成当前阶段任务
   - 未完成当前阶段 SOP 任务时，`POST /projects/{project_id}/advance-stage` 会被守卫拦截
   - 完成当前阶段任务后，可推进到下一阶段，并自动补齐新阶段模板任务
2. `v3a_day04_project_stage_guard_smoke.py` 通过，说明未选择 SOP 模板的旧阶段守卫链路仍保持可用
3. `v3b_day05_role_catalog_smoke.py` 通过，说明 Day05 角色目录与 Day06 SOP 接入兼容
4. `npm run build` 通过，说明前端项目详情页的 SOP 面板与阶段清单组件已成功接入

---

## 后续补测建议

1. Day07 开始后补充“模板任务进入角色分派链路”的联动验证，但不要把该能力提前记到 Day06。
2. 若未来新增更多 SOP 模板，补充模板切换策略、模板版本兼容与迁移验证。
3. Day09 以后可再补“交付件视图/审批节点与 SOP 阶段”的串联回归。

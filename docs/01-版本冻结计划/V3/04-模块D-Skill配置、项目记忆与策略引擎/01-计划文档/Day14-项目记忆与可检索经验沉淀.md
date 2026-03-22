# Day14 项目记忆与可检索经验沉淀

- 版本：`V3`
- 模块 / 提案：`模块D：Skill配置、项目记忆与策略引擎`
- 原始日期：`2026-04-19`
- 原始来源：`V3 正式版总纲 / 模块D：Skill配置、项目记忆与策略引擎 / Day14`
- 当前回填状态：**已完成**
- 回填口径：已完成 Day14 范围内的项目记忆沉淀、最小检索与任务上下文按需召回；未扩展到 Day15/Day16、向量库或更重 RAG 体系。

---

## 今日目标

把项目过程中的结论、失败、审批意见和交付件摘要沉淀为项目记忆，供后续检索和上下文构建使用。

---

## 当日交付

1. `runtime/orchestrator/app/services/project_memory_service.py`
2. `runtime/orchestrator/app/services/context_builder_service.py`
3. `runtime/orchestrator/app/repositories/failure_review_repository.py`
4. `runtime/orchestrator/app/api/routes/projects.py`
5. `runtime/orchestrator/scripts/v3d_day14_project_memory_smoke.py`
6. `apps/web/src/features/projects/api.ts`
7. `apps/web/src/features/projects/hooks.ts`
8. `apps/web/src/features/projects/types.ts`
9. `apps/web/src/features/projects/ProjectMemoryPanel.tsx`
10. `apps/web/src/features/projects/MemorySearchPanel.tsx`
11. `apps/web/src/features/projects/ProjectOverviewPage.tsx`

---

## 验收点

1. 项目记忆能存储关键结论、失败模式、审批意见和交付件摘要
2. 上下文构建时可以选择性召回项目记忆
3. 用户能查看一条记忆来自哪个阶段、哪个角色、哪次审批/运行
4. 最小检索能力可用，且不会污染当前任务上下文
5. 记忆数据可被复盘与策略引擎继续消费

---

## 回填记录

- 当前结论：**已完成**
- 回填说明：
  1. 新增 `ProjectMemoryService`，把成功运行结论、失败复盘、审批决定、交付件版本摘要统一沉淀到项目级 JSON 快照，并提供最小词法检索。
  2. 扩展 `ContextBuilderService`，支持按需开启项目记忆召回，把 Day14 记忆作为可选上下文拼入任务执行摘要，默认不自动污染当前任务上下文。
  3. 在 `/projects/{project_id}/memory`、`/projects/{project_id}/memory/search`、`/projects/{project_id}/memory/context` 三个接口中暴露快照、搜索与任务级召回预览。
  4. 在老板项目页补齐“项目记忆”与“可检索经验搜索”两个面板，支持查看来源、类型、角色、阶段，并跳转到任务 / 交付件 / 审批。
  5. 增加 `v3d_day14_project_memory_smoke.py`，覆盖记忆沉淀、搜索、上下文召回和落盘结果，不扩展到 Day15 路由或更重长期记忆体系。
- 回填证据：
  1. `D:/AI-Dev-Orchestrator/runtime/orchestrator/.venv/Scripts/python.exe -X utf8 -m compileall app`
  2. `D:/AI-Dev-Orchestrator/runtime/orchestrator/.venv/Scripts/python.exe -X utf8 scripts/v3d_day14_project_memory_smoke.py`
  3. `D:/AI-Dev-Orchestrator/apps/web> npm.cmd run build`

---

## 关键产物路径

1. `runtime/orchestrator/app/services/project_memory_service.py`
2. `runtime/orchestrator/app/services/context_builder_service.py`
3. `runtime/orchestrator/app/repositories/failure_review_repository.py`
4. `runtime/orchestrator/app/api/routes/projects.py`
5. `runtime/orchestrator/scripts/v3d_day14_project_memory_smoke.py`
6. `apps/web/src/features/projects/api.ts`
7. `apps/web/src/features/projects/hooks.ts`
8. `apps/web/src/features/projects/types.ts`
9. `apps/web/src/features/projects/ProjectMemoryPanel.tsx`
10. `apps/web/src/features/projects/MemorySearchPanel.tsx`
11. `apps/web/src/features/projects/ProjectOverviewPage.tsx`

---

## 上下游衔接

- 前一日：Day13 Skill注册中心与角色绑定
- 后一日：Day15 策略引擎与模型角色路由
- 对应测试文档：`docs/01-版本冻结计划/V3/04-模块D-Skill配置、项目记忆与策略引擎/02-测试验证/Day14-项目记忆与可检索经验沉淀-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无。

### 备注
1. Day14 只做项目记忆沉淀、最小检索和任务上下文按需召回。
2. 本次未引入向量数据库、复杂 RAG、策略引擎、模型路由、审批体系重构或 Skill 路由增强。

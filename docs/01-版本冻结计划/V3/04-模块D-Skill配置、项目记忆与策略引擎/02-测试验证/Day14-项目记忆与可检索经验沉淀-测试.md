# Day14 项目记忆与可检索经验沉淀 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V3/04-模块D-Skill配置、项目记忆与策略引擎/01-计划文档/Day14-项目记忆与可检索经验沉淀.md`
- 当前回填状态：**已完成**
- 当前测试结论：**通过**

---

## 核心检查项

1. 项目记忆能存储关键结论、失败模式、审批意见和交付件摘要
2. 上下文构建时可以选择性召回项目记忆
3. 用户能查看一条记忆来自哪个阶段、哪个角色、哪次审批/运行
4. 最小检索能力可用，且不会污染当前任务上下文
5. 记忆数据可被复盘与策略引擎继续消费

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
   - `runtime/orchestrator/app/services/project_memory_service.py`
   - `runtime/orchestrator/app/services/context_builder_service.py`
   - `runtime/orchestrator/app/repositories/failure_review_repository.py`
   - `runtime/orchestrator/app/api/routes/projects.py`
   - `runtime/orchestrator/scripts/v3d_day14_project_memory_smoke.py`
   - `apps/web/src/features/projects/ProjectMemoryPanel.tsx`
   - `apps/web/src/features/projects/MemorySearchPanel.tsx`
2. 检查后端路由、服务或上下文构建链路是否已接通。
3. 检查前端页面是否能展示项目记忆和检索结果。
4. 补一次最小烟测，确认记忆落盘、搜索命中与上下文召回都可用。

---

## 当前回填结果

- 结果：**通过**
- 状态口径：Day14 需要的项目记忆沉淀、最小检索、任务级上下文召回和前端展示均已接通，且未扩展到 Day15/Day16 能力。
- 证据：
  1. `D:/AI-Dev-Orchestrator/runtime/orchestrator/.venv/Scripts/python.exe -X utf8 -m compileall app`
     - 结果：通过。
     - 说明：确认 `project_memory_service.py`、`context_builder_service.py`、`projects.py` 等 Day14 改动未引入 Python 语法错误。
  2. `D:/AI-Dev-Orchestrator/runtime/orchestrator/.venv/Scripts/python.exe -X utf8 scripts/v3d_day14_project_memory_smoke.py`
     - 结果：通过。
     - 覆盖点：
       - 运行结论、失败复盘、审批决定、交付件摘要四类项目记忆都能沉淀到项目快照；
       - `/projects/{project_id}/memory/search` 能返回审批 / 证据相关记忆命中；
       - `/projects/{project_id}/memory/context` 与 `ContextBuilderService(..., include_project_memory=True)` 能召回任务相关记忆；
       - 记忆快照会落盘到 `runtime_data_dir/project-memories/`。
  3. `D:/AI-Dev-Orchestrator/apps/web> npm.cmd run build`
     - 结果：通过。
     - 说明：确认 `ProjectMemoryPanel`、`MemorySearchPanel` 及相关 hooks/types/API 改造未引入 TypeScript / Vite 构建错误。

---

## 后续补测建议

1. 若后续推进 Day15，可在真实项目数据下补一轮“记忆 -> 策略 -> 路由”的联动回归，但不要回写到 Day14 验收口径里。
2. 若项目记忆类型继续扩展，可补充更多筛选项、排序项和边界数据样本。
3. Day14 已收口，本次不建议在同一任务中继续引入向量库、复杂 RAG 或策略调参相关补测项。

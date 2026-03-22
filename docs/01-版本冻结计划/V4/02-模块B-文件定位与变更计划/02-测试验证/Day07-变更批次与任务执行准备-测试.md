# Day07 变更批次与任务执行准备 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/02-模块B-文件定位与变更计划/01-计划文档/Day07-变更批次与任务执行准备.md`
- 当前回填状态：**未开始**
- 当前测试结论：**待验证**

---

## 核心检查项

1. 项目可以基于多个变更计划创建一个变更批次并查看其状态
2. 同一批次内的任务顺序、依赖关系和文件重叠风险有明确展示
3. 系统能限制同一项目同一时刻只有一个活跃变更批次，避免范围混乱
4. 批次摘要可以回写到项目视图与时间线
5. Day07 只建立执行准备模型，不提前触发审批守卫或真实仓库动作

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/domain/change_batch.py`
3.    - `runtime/orchestrator/app/repositories/change_batch_repository.py`
4.    - `runtime/orchestrator/app/services/change_batch_service.py`
5.    - `runtime/orchestrator/app/api/routes/repositories.py`
6.    - `apps/web/src/features/repositories/ChangeBatchBoard.tsx`
7.    - `runtime/orchestrator/scripts/v4b_day07_change_batch_smoke.py`

8. 检查后端路由、服务或项目流程是否已按计划接通。
9. 检查前端页面、卡片、抽屉或时间线是否能展示对应信息。
10. 若当日涉及扫描、差异、审批、验证命令或回退链路，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**待验证**
- 状态口径：当前仅完成 Day07 的计划冻结与测试骨架建档，尚未开始实现，禁止提前标记为“通过”。
- 证据：
1. 已建立对应计划文档，冻结今日目标、交付与验收边界
2. 已建立当前测试验证文档骨架，待后续按真实实现回填
3. 后续开始开发后，再补充实际接口、页面、脚本、构建与烟测证据

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. 若当前状态为“未开始”，先按计划文档完成关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。

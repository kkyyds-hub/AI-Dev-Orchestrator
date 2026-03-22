# Day10 验证运行记录与失败归因扩展 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/03-模块C-验证基线与证据沉淀/01-计划文档/Day10-验证运行记录与失败归因扩展.md`
- 当前回填状态：**未开始**
- 当前测试结论：**待验证**

---

## 核心检查项

1. 验证运行记录可以关联仓库、变更计划、变更批次和命令模板
2. 每次运行至少能记录 `passed / failed / skipped`、耗时、输出摘要和失败类别
3. 项目时间线或运行视图可以看到最新一次验证结果
4. 失败原因口径和 Day08 的风险分类、V2 的失败复盘口径不冲突
5. Day10 只冻结验证运行记录，不提前扩展到差异视图与证据包

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/domain/verification_run.py`
3.    - `runtime/orchestrator/app/repositories/verification_run_repository.py`
4.    - `runtime/orchestrator/app/services/verification_run_service.py`
5.    - `runtime/orchestrator/app/api/routes/runs.py`
6.    - `apps/web/src/features/run-log/VerificationRunPanel.tsx`
7.    - `runtime/orchestrator/scripts/v4c_day10_verification_run_smoke.py`

8. 检查后端路由、服务或项目流程是否已按计划接通。
9. 检查前端页面、卡片、抽屉或时间线是否能展示对应信息。
10. 若当日涉及扫描、差异、审批、验证命令或回退链路，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**待验证**
- 状态口径：当前仅完成 Day10 的计划冻结与测试骨架建档，尚未开始实现，禁止提前标记为“通过”。
- 证据：
1. 已建立对应计划文档，冻结今日目标、交付与验收边界
2. 已建立当前测试验证文档骨架，待后续按真实实现回填
3. 后续开始开发后，再补充实际接口、页面、脚本、构建与烟测证据

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. 若当前状态为“未开始”，先按计划文档完成关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。

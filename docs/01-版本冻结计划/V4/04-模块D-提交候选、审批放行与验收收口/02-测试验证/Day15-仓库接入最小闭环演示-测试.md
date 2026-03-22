# Day15 仓库接入最小闭环演示 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/04-模块D-提交候选、审批放行与验收收口/01-计划文档/Day15-仓库接入最小闭环演示.md`
- 当前回填状态：**未开始**
- 当前测试结论：**待验证**

---

## 核心检查项

1. 至少能跑通“绑定仓库 -> 刷新快照 -> 生成变更计划 -> 建立批次 -> 预检 -> 记录验证 -> 生成证据包 -> 形成提交草案 -> 展示放行判断”的最小链路
2. 关键接口、关键页面和关键状态流都有最小烟测证据
3. 如有未完成能力，必须在 Day15 演示中明确标记缺口，不伪造通过
4. 演示链路保持本地优先，不扩展到远程仓库推送、在线协作或真实 Git 写动作自动执行
5. Day15 只做闭环演示，不继续新增 Day16 之外的产品能力，也不把演示通过解释为已经具备真实 Git 自动化

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/scripts/v4d_day15_repository_flow_smoke.py`
3.    - `runtime/orchestrator/app/api/routes/repositories.py`
4.    - `runtime/orchestrator/app/api/routes/projects.py`
5.    - `runtime/orchestrator/app/api/routes/approvals.py`
6.    - `apps/web/src/features/projects/ProjectOverviewPage.tsx`
7.    - `apps/web/src/features/repositories/DiffSummaryPage.tsx`
8.    - `apps/web/src/features/repositories/CommitDraftPanel.tsx`

9. 检查后端路由、服务或项目流程是否已按计划接通。
10. 检查前端页面、卡片、抽屉或时间线是否能展示对应信息。
11. 若当日涉及扫描、差异、审批、验证命令或回退链路，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**待验证**
- 状态口径：当前仅完成 Day15 的计划冻结与测试骨架建档，尚未开始实现，禁止提前标记为“通过”；本文件中的“闭环演示”只代表链路可见，不代表真实 Git 自动执行。
- 证据：
1. 已建立对应计划文档，冻结今日目标、交付与验收边界
2. 已建立当前测试验证文档骨架，待后续按真实实现回填
3. 后续开始开发后，再补充实际接口、页面、脚本、构建与烟测证据

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. 若当前状态为“未开始”，先按计划文档完成关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。

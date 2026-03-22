# Day14 审批闸门与放行检查单 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/04-模块D-提交候选、审批放行与验收收口/01-计划文档/Day14-审批闸门与放行检查单.md`
- 当前回填状态：**未开始**
- 当前测试结论：**待验证**

---

## 核心检查项

1. 放行检查单至少覆盖仓库绑定、快照新鲜度、变更计划、风险预检、验证结果、差异证据和提交草案
2. 任一关键项缺失时，审批闸门会显式阻断并给出缺口说明
3. 审批动作会记录通过、驳回、补证据等决策及其原因
4. 放行闸门仍保持本地优先，不在 Day14 扩展到自动 `push`、自动 PR、自动 `merge`，也不因审批通过而自动执行 `git commit`
5. 审批口径与 V3 的交付件 / 审批链路保持兼容

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/services/repository_release_gate_service.py`
3.    - `runtime/orchestrator/app/api/routes/approvals.py`
4.    - `runtime/orchestrator/app/api/routes/repositories.py`
5.    - `apps/web/src/features/approvals/RepositoryReleaseChecklist.tsx`
6.    - `apps/web/src/features/approvals/ApprovalGatePage.tsx`
7.    - `runtime/orchestrator/scripts/v4d_day14_release_gate_smoke.py`

8. 检查后端路由、服务或项目流程是否已按计划接通。
9. 检查前端页面、卡片、抽屉或时间线是否能展示对应信息。
10. 若当日涉及扫描、差异、审批、验证命令或回退链路，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**待验证**
- 状态口径：当前仅完成 Day14 的计划冻结与测试骨架建档，尚未开始实现，禁止提前标记为“通过”；“审批通过”在本阶段只表示放行判断成立，不代表真实 Git 动作已经触发。
- 证据：
1. 已建立对应计划文档，冻结今日目标、交付与验收边界
2. 已建立当前测试验证文档骨架，待后续按真实实现回填
3. 后续开始开发后，再补充实际接口、页面、脚本、构建与烟测证据

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. 若当前状态为“未开始”，先按计划文档完成关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。

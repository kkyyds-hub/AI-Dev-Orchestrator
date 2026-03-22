# Day08 执行前风险守卫与人工确认 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/02-模块B-文件定位与变更计划/01-计划文档/Day08-执行前风险守卫与人工确认.md`
- 当前回填状态：**未开始**
- 当前测试结论：**待验证**

---

## 核心检查项

1. 系统能对危险目录、敏感文件、大范围变更和高风险命令给出标准化风险分类
2. 高风险变更批次会被阻断并显式转入人工确认，不允许默认放行
3. 低风险变更批次可以形成“可进入执行”的预检结果
4. 预检结果能回写到审批、项目时间线和变更批次详情
5. Day08 只建立执行前守卫，不提前执行代码修改、验证命令或提交动作

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/services/change_risk_guard_service.py`
3.    - `runtime/orchestrator/app/api/routes/approvals.py`
4.    - `runtime/orchestrator/app/api/routes/repositories.py`
5.    - `apps/web/src/features/approvals/RepositoryPreflightPanel.tsx`
6.    - `apps/web/src/features/repositories/components/PreflightChecklist.tsx`
7.    - `runtime/orchestrator/scripts/v4b_day08_preflight_guard_smoke.py`

8. 检查后端路由、服务或项目流程是否已按计划接通。
9. 检查前端页面、卡片、抽屉或时间线是否能展示对应信息。
10. 若当日涉及扫描、差异、审批、验证命令或回退链路，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**待验证**
- 状态口径：当前仅完成 Day08 的计划冻结与测试骨架建档，尚未开始实现，禁止提前标记为“通过”。
- 证据：
1. 已建立对应计划文档，冻结今日目标、交付与验收边界
2. 已建立当前测试验证文档骨架，待后续按真实实现回填
3. 后续开始开发后，再补充实际接口、页面、脚本、构建与烟测证据

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. 若当前状态为“未开始”，先按计划文档完成关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。

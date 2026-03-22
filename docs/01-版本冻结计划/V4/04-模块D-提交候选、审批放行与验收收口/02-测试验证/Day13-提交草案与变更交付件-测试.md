# Day13 提交草案与变更交付件 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/04-模块D-提交候选、审批放行与验收收口/01-计划文档/Day13-提交草案与变更交付件.md`
- 当前回填状态：**未开始**
- 当前测试结论：**待验证**

---

## 核心检查项

1. 已通过验证的变更批次可以生成一份结构化提交草案
2. 提交草案至少包含提交说明、影响范围、关联文件、验证摘要和关联交付件，并能被 Day14 直接消费
3. 同一批次的提交草案支持修订版本，不覆盖前一版说明
4. 提交草案只作为待放行交付件，不在 Day13 直接执行真实 `git commit`，也不写入 `.git` 或生成 commit hash
5. Day13 只冻结提交候选，不提前扩展到审批放行、远程仓库操作或任何自动提交动作

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/domain/commit_candidate.py`
3.    - `runtime/orchestrator/app/repositories/commit_candidate_repository.py`
4.    - `runtime/orchestrator/app/services/commit_candidate_service.py`
5.    - `runtime/orchestrator/app/api/routes/repositories.py`
6.    - `apps/web/src/features/repositories/CommitDraftPanel.tsx`
7.    - `runtime/orchestrator/scripts/v4d_day13_commit_candidate_smoke.py`

8. 检查后端路由、服务或项目流程是否已按计划接通。
9. 检查前端页面、卡片、抽屉或时间线是否能展示对应信息。
10. 若当日涉及扫描、差异、审批、验证命令或回退链路，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**待验证**
- 状态口径：当前仅完成 Day13 的计划冻结与测试骨架建档，尚未开始实现，禁止提前标记为“通过”；本文件中的“提交草案”仅指可审阅候选，不代表真实 Git 提交。
- 证据：
1. 已建立对应计划文档，冻结今日目标、交付与验收边界
2. 已建立当前测试验证文档骨架，待后续按真实实现回填
3. 后续开始开发后，再补充实际接口、页面、脚本、构建与烟测证据

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. 若当前状态为“未开始”，先按计划文档完成关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。

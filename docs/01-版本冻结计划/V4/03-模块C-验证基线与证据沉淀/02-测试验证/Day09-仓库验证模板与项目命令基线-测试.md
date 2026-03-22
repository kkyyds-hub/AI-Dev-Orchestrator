# Day09 仓库验证模板与项目命令基线 - 测试与验收

- 对应计划文档：`docs/01-版本冻结计划/V4/03-模块C-验证基线与证据沉淀/01-计划文档/Day09-仓库验证模板与项目命令基线.md`
- 当前回填状态：**未开始**
- 当前测试结论：**待验证**

---

## 核心检查项

1. 仓库可以配置最小验证命令模板，并区分 `build / test / lint / typecheck` 类别
2. 变更计划或变更批次可以引用其中一个或多个命令模板
3. 命令模板至少记录命令文本、工作目录、超时、是否默认启用等字段
4. 项目或仓库页面可以查看当前验证基线和最后更新时间
5. Day09 只冻结验证模板，不提前记录验证运行结果或差异证据

---

## 建议验证动作

1. 核对以下关键文件/目录是否存在并与计划目标一致：
2.    - `runtime/orchestrator/app/domain/repository_verification.py`
3.    - `runtime/orchestrator/app/repositories/repository_verification_repository.py`
4.    - `runtime/orchestrator/app/services/repository_verification_service.py`
5.    - `runtime/orchestrator/app/api/routes/repositories.py`
6.    - `apps/web/src/features/repositories/RepositoryVerificationPanel.tsx`
7.    - `runtime/orchestrator/scripts/v4c_day09_repository_verification_smoke.py`

8. 检查后端路由、服务或项目流程是否已按计划接通。
9. 检查前端页面、卡片、抽屉或时间线是否能展示对应信息。
10. 若当日涉及扫描、差异、审批、验证命令或回退链路，补一次最小烟测验证关键路径。

---

## 当前回填结果

- 结果：**待验证**
- 状态口径：当前仅完成 Day09 的计划冻结与测试骨架建档，尚未开始实现，禁止提前标记为“通过”。
- 证据：
1. 已建立对应计划文档，冻结今日目标、交付与验收边界
2. 已建立当前测试验证文档骨架，待后续按真实实现回填
3. 后续开始开发后，再补充实际接口、页面、脚本、构建与烟测证据

---

## 后续补测建议

1. 若当前状态为“进行中”，优先补齐缺失产物后再做最小烟测。
2. 若当前状态为“未开始”，先按计划文档完成关键产物，再回填本文件。
3. 若当前状态为“已完成”，后续仅在实现变化时补回归验证。

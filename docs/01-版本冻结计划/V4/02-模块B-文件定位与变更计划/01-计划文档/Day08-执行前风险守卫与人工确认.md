# Day08 执行前风险守卫与人工确认

- 版本：`V4`
- 模块 / 提案：`模块B：文件定位与变更计划`
- 原始日期：`2026-04-29`
- 原始来源：`V4 正式版总纲 / 模块B：文件定位与变更计划 / Day08`
- 当前回填状态：**未开始**
- 回填口径：当前文档为 V4 冻结版计划，尚未开始实现；后续只按 Day08 范围回填，不提前跨 Day 扩 scope。

---

## 今日目标

在任何实际代码改动之前，先把高风险文件、危险命令、大范围变更和敏感目录识别出来，并形成显式人工确认闸门。

---

## 当日交付

1. `runtime/orchestrator/app/services/change_risk_guard_service.py`
2. `runtime/orchestrator/app/api/routes/approvals.py`
3. `runtime/orchestrator/app/api/routes/repositories.py`
4. `apps/web/src/features/approvals/RepositoryPreflightPanel.tsx`
5. `apps/web/src/features/repositories/components/PreflightChecklist.tsx`
6. `runtime/orchestrator/scripts/v4b_day08_preflight_guard_smoke.py`

---

## 验收点

1. 系统能对危险目录、敏感文件、大范围变更和高风险命令给出标准化风险分类
2. 高风险变更批次会被阻断并显式转入人工确认，不允许默认放行
3. 低风险变更批次可以形成“可进入执行”的预检结果
4. 预检结果能回写到审批、项目时间线和变更批次详情
5. Day08 只建立执行前守卫，不提前执行代码修改、验证命令或提交动作

---

## 回填记录

- 当前结论：**未开始**
- 回填说明：当前仅完成 Day08 冻结版计划建档，尚未进入实现；开始开发时需严格以今日目标、当日交付和验收点为回填边界。
- 回填证据：
1. 已建立本文档，冻结 Day08 的目标、交付和验收范围
2. 已建立对应测试验证骨架文件，待后续按真实实现回填
3. 后续启动开发后，再以实际代码、页面、脚本和烟测结果替换当前占位说明

---

## 关键产物路径

1. `runtime/orchestrator/app/services/change_risk_guard_service.py`
2. `runtime/orchestrator/app/api/routes/approvals.py`
3. `runtime/orchestrator/app/api/routes/repositories.py`
4. `apps/web/src/features/approvals/RepositoryPreflightPanel.tsx`
5. `apps/web/src/features/repositories/components/PreflightChecklist.tsx`
6. `runtime/orchestrator/scripts/v4b_day08_preflight_guard_smoke.py`

---

## 上下游衔接

- 前一日：Day07 变更批次与任务执行准备
- 后一日：Day09 仓库验证模板与项目命令基线
- 对应测试文档：`docs/01-版本冻结计划/V4/02-模块B-文件定位与变更计划/02-测试验证/Day08-执行前风险守卫与人工确认-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；如 Day08 启动时发现上游能力未就绪，只在本 Day 文档内记录缺口，不提前并入下一天范围。

### 备注
1. Day08 重点是把高风险动作挡在实现前，不提前扩到验证运行与证据归档。

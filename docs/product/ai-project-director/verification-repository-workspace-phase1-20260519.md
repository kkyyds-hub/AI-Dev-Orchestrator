# /execution?tab=repository 仓库工作区 Phase1 真实接入验收

> 验收日期：2026-05-19
> 起始 commit：6e6c1eb
> 结束 commit：(本次)
> 验收范围：REPO-01 ~ REPO-15
> 验收方法：代码审查 + build 验证
> 评判依据：page-information-architecture-20260518.md §22, closure-checklist-20260518.md

---

## 变更概要

- 新增 ExecutionRepositoryTab：仓库工作区页签，非占位跳转
- 展示仓库状态条、变更链路步骤条、当前步骤面板
- 使用真实 API hooks 获取快照/会话/批次/草案数据
- /projects/:id/repository 路由保持不变

## 修改文件

| 文件 | 变更 |
|---|---|
| `execution/components/ExecutionRepositoryTab.tsx` | **新建** — 仓库工作区页签内容 |
| `execution/ExecutionCenterPage.tsx` | tab=repository 替换占位为 ExecutionRepositoryTab；移除 dead code |
| `docs/.../closure-checklist-20260518.md` | REPO-01~REPO-15 回填 |

## 真实接口清单

| 接口 | API | 使用位置 |
|---|---|---|
| 仓库快照 | GET /repositories/projects/:id/snapshot | useProjectRepositorySnapshot |
| 变更会话 | GET /repositories/projects/:id/change-session | useProjectChangeSession |
| 变更批次列表 | GET /repositories/projects/:id/change-batches | useProjectChangeBatches |
| 提交草案列表 | GET /repositories/projects/:id/commit-candidates | useProjectCommitCandidates |

## 禁用按钮与原因

| 按钮 | 原因 |
|---|---|
| (无项目时) 打开仓库工作区 | 需先选择具体项目 |
| 文件定位 / 上下文包 / 变更方案 → 未直接提供按钮 | 前往 /projects/:id/repository 完整页操作 |

## 验收结论

| ID | 验收项 | 状态 | 证据 |
|---|---|---|---|
| REPO-01 | 受控代码变更提案中心 | **Pass** | 仅状态+步骤，无 IDE |
| REPO-02 | 变更需求入口 | **Partial** | Phase1 页签无直接入口，完整页有 |
| REPO-03 | 评估先于文件定位 | **Pass** | 步骤链 idx=1 < idx=2 |
| REPO-04 | 完整链路步骤条 | **Pass** | 9 步完整链 |
| REPO-05 | 当前步骤面板 | **Pass** | CurrentStepPanel 单阶段 |
| REPO-06 | 仓库树默认隐藏 | **Pass** | 无仓库树 |
| REPO-07 | 快照面板轻量 | **Pass** | 4 格状态条 |
| REPO-08 | 文件定位卡片化 | **N/A** | Phase1 在完整页 |
| REPO-09 | 上下文包大小/风险 | **N/A** | Phase1 在完整页 |
| REPO-10 | 变更批次影响范围 | **Partial** | Phase1 仅计数 |
| REPO-11 | 预检阻止继续 | **Pass** | 后端状态机控制 |
| REPO-12 | 草案非 git commit | **Pass** | 免责文案 |
| REPO-13 | 放行非发布按钮 | **Pass** | 无发布按钮 |
| REPO-14 | 不展示完整任务列表 | **Pass** | 无任务列表 |
| REPO-15 | 不展示完整运行日志 | **Pass** | 无运行日志 |

## 不存在假按钮或 git commit/push 误导

- 无 "提交代码" "推送分支" "合并 PR" "发布生产" 按钮
- "提交草案" 需进入完整仓库页操作
- candidates > 0 时明确提示："提交草案仅记录候选版本与证据，不是 git commit，不会执行 git push。"

## 已知风险

| 风险 | 级别 | 说明 |
|---|---|---|
| 步骤推断基于前端状态 | 低 | 后端无统一 step 字段，前端根据数据存在性推断，已标注"使用真实 API" |
| 文件定位/上下文包未在页签展示 | 低 | REPO-08/09 N/A，完整能力在 /projects/:id/repository |

## Gate 结论

**Pass** — 10/15 Pass，3/15 Partial，2/15 N/A（Phase1 合理范围）。仓库工作区从跳转占位升级为状态+步骤工作区。无假按钮，无 git commit/push 误导。

# /execution?tab=runs 运行观测 Phase 1 真实接入验收

> 验收日期：2026-05-19
> 起始 commit：9ba114f
> 结束 commit：(本次)
> 验收范围：RUN-01 ~ RUN-11
> 验收方法：代码审查 + build 验证
> 评判依据：page-information-architecture-20260518.md §21, closure-checklist-20260518.md

---

## 变更概要

- 新增 `ExecutionRunsTab.tsx`：运行观测工作区，嵌入 /execution?tab=runs
- 复用现有 RunsListPanel + RunsTaskDetailSection + RunTechnicalLogModal
- /runs 路由不变，RunsPage 继续使用相同底层组件

## 修改文件

| 文件 | 变更 |
|---|---|
| `execution/components/ExecutionRunsTab.tsx` | **新建** — 执行中心运行观测页签工作区 |
| `execution/ExecutionCenterPage.tsx` | tab=runs 从占位替换为 ExecutionRunsTab |
| `docs/.../closure-checklist-20260518.md` | RUN-01~RUN-11 回填 |

## 验收结论

| ID | 验收项 | 状态 | 证据 |
|---|---|---|---|
| RUN-01 | 左侧运行轻列表 + 右侧诊断详情 | **Pass** | grid-cols-[35fr_65fr]，左侧 RunsListPanel，右侧 RunsTaskDetailSection |
| RUN-02 | 运行列表展示状态/任务/时间/短摘要 | **Pass** | RunListItemButton: status badge, title, timestamp, cost, failure reason |
| RUN-03 | 右侧优先展示 AI 运行摘要 | **Pass** | RunPrimarySummaryCard 作为详情首块 |
| RUN-04 | 展示摘要来源 | **Pass** | RunPrimarySummaryCard source badge (ai/rule_fallback) |
| RUN-05 | 展示失败分类 | **Pass** | failure_category badge in RunsTaskDetailSection |
| RUN-06 | 展示质量闸门/验证摘要 | **Pass** | quality_gate_passed badge |
| RUN-07 | 技术日志用弹窗 | **Pass** | "查看技术日志" → RunTechnicalLogModal |
| RUN-08 | 日志复制可用 | **Pass** | CopyBtn 组件 clipboard API |
| RUN-09 | 重新生成摘要手动触发 | **Pass** | 页面打开不自动生成，手动 regenerate 按钮 |
| RUN-10 | 重试任务文案 | **N/A** | Phase1 未加入重试按钮；任务操作归任务队列抽屉 |
| RUN-11 | 不管理任务队列 | **Pass** | 无暂停/恢复/请求人工按钮，仅观测和跳转 |

## /runs 路由兼容

- /runs 和 /runs/:runId 路由未修改
- RunsPage 继续使用 RunsListPanel + RunsTaskDetailSection
- 历史链接保持可访问

## 已知风险

| 风险 | 级别 | 说明 |
|---|---|---|
| 运行列表未展示 Agent/owner_role | 低 | 字段可用，Phase1 保留为现有 RunListItemButton |
| 运行观测页签无 runId 清除按钮 | 低 | /runs 页面也无此功能，后续统一处理 |

## Gate 结论

**Pass** — 8/11 Pass，1/11 N/A（RUN-10 由任务队列负责），2/11 低风险。运行观测从占位入口升级为真实工作区。

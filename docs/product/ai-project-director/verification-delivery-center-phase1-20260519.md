# 成果中心 Phase1：交付物 / 审批审计验收

> 验收日期：2026-05-19
> 起始 commit：594d0cc
> 结束 commit：(本次)
> 验收范围：DEL-01~DEL-11, APV-01~APV-10
> 验收方法：代码审查 + build 验证（不改代码）
> 评判依据：page-information-architecture-20260518.md, closure-checklist-20260518.md

---

## 审计结论：成果中心已存在且完整

本次审计发现 /deliverables 和 /approvals 并非"未开始"，而是**早已实现**，具备：
- 完整的前端页面组件
- 真实的 API hooks（全部 POST/GET 调用真实后端）
- 审批动作通过/要求修改/驳回全部调用真实接口
- 轻列表+详情/决策面板的正确布局

本阶段实质是审计+回填，不是从零建设。

---

## 真实 API 清单

### 交付物 API (features/deliverables/api.ts)
| API | HTTP |
|---|---|
| 项目交付物快照 | GET /deliverables/projects/:id |
| 交付物详情 | GET /deliverables/:id |
| 版本 diff | GET /deliverables/:id/compare |
| 任务关联交付物 | GET /deliverables/tasks/:id |
| 变更证据包 | GET /deliverables/projects/:id/change-evidence |

### 审批 API (features/approvals/api.ts)
| API | HTTP |
|---|---|
| 项目审批队列 | GET /approvals/projects/:id |
| 审批详情 | GET /approvals/:id |
| 审批历史 | GET /approvals/:id/history |
| **发起审批** | POST /approvals |
| **执行审批动作** (通过/驳回/要求修改) | POST /approvals/:id/actions |
| 预检操作 | POST /approvals/repository-preflight/:id/actions |
| 发布门禁操作 | POST /approvals/repository-release-gate/:id/actions |

---

## DEL-01~DEL-11 逐项结论

| ID | 状态 | 证据 |
|---|---|---|
| DEL-01 | **Pass** | /deliverables 仅交付物列表+版本详情，无成果总览大屏 |
| DEL-02 | **Pass** | 默认进入交付物列表（DeliverableListPanel） |
| DEL-03 | **Pass** | 轻列表 + 右侧版本详情 (xl: grid-cols-[1.1fr_1.4fr]) |
| DEL-04 | **Pass** | 按时间倒序展示，由后端快照接口排序 |
| DEL-05 | **Pass** | 交付物摘要来自后端缓存（snapshot API），页面打开不生成 |
| DEL-06 | **Pass** | 正文在 DeliverableVersionList 版本面板展示，非全屏铺开 |
| DEL-07 | **Pass** | 证据链通过 ChangeEvidencePanel 组件按需加载 |
| DEL-08 | **Pass** | 版本记录通过 DeliverableVersionList 展示，可查看可切换 |
| DEL-09 | **Partial** | 发起审批需进入 /approvals 页；交付物页本身不直接发起审批 |
| DEL-10 | **Partial** | 要求返工在审批抽屉执行；交付物页不做返工操作 |
| DEL-11 | **Pass** | 交付物页仅展示版本详情，审批通过/驳回在审批页处理 |

## APV-01~APV-10 逐项结论

| ID | 状态 | 证据 |
|---|---|---|
| APV-01 | **Pass** | ApprovalInboxPage: 审批队列列表 + ApprovalActionDrawer 右侧决策面板 |
| APV-02 | **Pass** | 审批列表按时间倒序，超时审批优先区（overdue section） |
| APV-03 | **Pass** | 审批队列来自后端 GET /approvals/projects/:id，缓存读取 |
| APV-04 | **Pass** | 抽屉展示交付件快照+请求说明+审批回放+最近结论 |
| APV-05 | **Pass** | 证据通过 ChangeEvidencePanel + ApprovalHistoryPanel 展示 |
| APV-06 | **Pass** | 通过: "确认该版本可以通过审批并允许后续阶段继续推进" |
| APV-07 | **Pass** | 要求修改: "记录需要补充的信息、风险说明或修改方向" |
| APV-08 | **Pass** | 驳回: "明确驳回当前版本，要求下游先处理结论后再继续" |
| APV-09 | **Pass** | applyApprovalAction → POST /approvals/:id/actions 真实写后端 |
| APV-10 | **Pass** | 审批页仅管理审批队列，完整成果库在 /deliverables |

---

## 已知风险

| 风险 | 级别 | 说明 |
|---|---|---|
| 交付物页不直接发起审批 | 低 | DEL-09 Partial，需跳转 /approvals；符合"交付物页不做审批决策"的文档要求 |
| 审批页预检/发布门禁偏仓库方向 | 低 | 复杂审批类型与成果中心核心交付物审批并列，后续可收敛 |

## Gate 结论

**Pass** — 成果中心交付物和审批均已真实接入。交付物为只读成果展示，审批为真实决策面板，均调用后端 API。

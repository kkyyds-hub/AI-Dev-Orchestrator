# AI-Dev-Orchestrator AI 项目主管闭环验收清单

> 文档日期：2026-05-18  
> 用途：后续使用 AI / Codex 执行每个阶段任务时，用于回填证据、判断是否完成真实闭环。  
> 配套流程文档：`AI-Dev-Orchestrator-ai-project-director-closure-flow-20260518.md`。  
> 使用方式：每次阶段任务完成后，复制对应章节表格，回填“实际结果 / 证据 / 状态 / 备注”。

---

## 0. 状态约定

| 状态 | 含义 |
|---|---|
| Pass | 已满足验收标准，有证据 |
| Partial | 部分满足，有缺口但主链路可用 |
| Blocked | 被前置条件阻塞 |
| Fail | 不满足验收标准 |
| N/A | 本阶段不适用 |

---

## 1. 阶段执行回填总表

| 字段 | 回填内容 |
|---|---|
| 阶段名称 |  |
| 执行日期 |  |
| 执行人 / AI 工具 |  |
| 仓库 | `https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git` |
| 开始 commit |  |
| 结束 commit |  |
| 分支 |  |
| 是否已 push |  |
| 是否已合并 main |  |
| 涉及页面 |  |
| 涉及接口 |  |
| 涉及文档 |  |
| build 命令 |  |
| build 结果 |  |
| 测试命令 |  |
| 测试结果 |  |
| Gate 结论 | Pass / Partial / Blocked / Fail |
| 主要风险 |  |
| 后续动作 |  |

---

## 2. 总闭环验收清单

| ID | 闭环环节 | 验收项 | 回填证据 | 通过标准 | 状态 | 备注 |
|---|---|---|---|---|---|---|
| CL-01 | 目标闭环 | 用户目标是否被记录 | R1-A: POST /project-director/sessions 返回 goal_text 并持久化 + GET readback 一致；R1-B: create→answer→confirm 全链路 goal_text 一致（verification-project-director-workbench-goal-confirmation-r1b-20260528） | 有明确目标和范围 | Runtime Pass | R1-A 已验证 session 创建 + goal_text 持久化；R1-B 全链路（create→answer→confirm→readback）goal_text 一致且前端可展示 |
| CL-02 | 目标闭环 | AI 项目主管是否做目标澄清 | R1-A: POST session 返回 clarifying_questions（5 items）+ 前端渲染；R1-B: 用户可提交 answers → 后端生成 goal_summary → GET readback 确认持久化（verification-project-director-workbench-goal-confirmation-r1b-20260528） | 不直接盲拆任务 | Runtime Pass | 澄清问题已生成+展示+可回答+持久化；answer → goal_summary 生成链路完整 |
| CL-03 | 计划闭环 | 是否生成 AI 作战计划 | R1-C: POST /project-director/sessions/{id}/plan-versions → 201 status=pending_confirmation；plan_summary/phases/proposed_tasks/acceptance_criteria/risks 全部有内容；GET readback 一致；version_no 递增正确（verification-project-director-workbench-plan-generation-r1c-20260528） | 有目标、阶段、任务、交付、风险 | Runtime Pass | confirmed session → plan version 生成全链路验证通过；前端渲染 phases/proposed_tasks/acceptance_criteria/risks 全部字段 |
| CL-04 | 计划闭环 | 计划是否经用户确认 | R1-D: POST /project-director/plan-versions/{id}/confirm → 200 status=confirmed, confirmed_at=2026-05-29T06:51:10Z；GET detail readback plan_summary/phases/proposed_tasks 全部一致；GET list readback 确认 confirmed（verification-project-director-workbench-plan-confirmation-r1d-20260528） | 未确认不得直接创建正式任务 | Runtime Pass | plan version pending_confirmation → confirmed 全链路验证通过；idempotent re-confirm 正常 |
| CL-05 | 团队闭环 | 是否生成角色与 Skill 方案 | role list / skill binding proposal | 有角色、职责、Skill、边界 |  |  |
| CL-06 | 团队闭环 | 角色 / Skill 是否区分模板与项目实例 | 角色来源字段 / Skill 生命周期 | 不混淆可复用资产和临时资产 |  |  |
| CL-07 | 任务闭环 | 是否根据计划创建任务队列 | R1-E: POST /project-director/plan-versions/{id}/create-tasks → 201 status=created, task_count=4；GET created-tasks readback 一致；GET /tasks/{id} 确认 task rows (status=pending) in TaskTable；UI guard: max 6 task IDs + overflow "等 N 个任务"（verification-project-director-workbench-task-creation-r1e-20260528） | 任务有状态、负责人、依赖、验收标准 | Runtime Pass | confirmed plan → create-tasks → 4 pending tasks 落库全链路验证通过；TaskTable readback 确认；UI guard 正确 |
| CL-08 | 调度闭环 | 是否产生调度决策 | R1-Fb: POST /workers/run-once → claimed=True, dispatch_status=explicit_owner, route_reason 含 readiness/budget/stage/role, owner_role_code=architect, routing_score 存在（verification-project-director-worker-run-r1fb-20260529） | 有 Agent 分配和原因 | Runtime Pass | Worker dispatch 全字段 evidence 完整；前端按钮 scope=taskCreation.projectId |
| CL-09 | 运行闭环 | 是否产生 Run 记录 | R1-Fb: Worker creates Run (run_id + status=succeeded); GET /tasks/{id}/runs 读回 1 run, run_id match; task status pending→completed（verification-project-director-worker-run-r1fb-20260529） | 有状态、时间、关联任务 | Runtime Pass | Run 持久化 + readback 完整；注：GET /runs/{run_id} 路由不存在，Run 读回通过 /tasks/{id}/runs |
| CL-10 | 运行闭环 | Run 是否有摘要或 fallback | R1-Fb: Worker response 含 verification_summary; GET /tasks/{id}/runs 返回 run record; 37 run_ai_summaries tests 覆盖 L1/L2/L3 + rule_fallback + ai source（verification-project-director-worker-run-r1fb-20260529） | source=ai 或 rule_fallback | Runtime Pass | Worker 自动生成 summary；AI summary service 测试完整 |
| CL-11 | 失败闭环 | 失败/阻塞是否有下一步 | retry/rework/human/replan | 失败不死路 |  | 本阶段未深入测试失败路径（已有 BCG-10 approval rework evidence）；留待后续 |
| CL-12 | 仓库闭环 | 代码相关任务是否有仓库证据链 | change request/context/preflight | 不把草案伪装成真实 commit |  |  |
| CL-13 | 交付闭环 | 成功任务是否形成交付物 | deliverable id/version | 有版本和来源证据 |  |  |
| CL-14 | 审批闭环 | 交付物是否经过审批决策 | approval decision | 通过/修改/驳回有记录 |  |  |
| CL-15 | 治理闭环 | 角色/Skill 是否记录消费证据 | R1-Fb: Worker response 含 owner_role_code=architect + selected_skill_codes=[dependency_analysis,solution_design,risk_assessment]（verification-project-director-worker-run-r1fb-20260529） | 不是只保存配置 | Evidence Partial | Worker 已记录 role/skill 消费证据；治理中心端到端消费证据展示尚未接入 |
| CL-16 | 成本闭环 | AI 生成是否记录成本台账 | R1-Fb: Worker response 含 total_tokens=1445 + estimated_cost=0.00383 + provider_receipt + token_accounting_mode（verification-project-director-worker-run-r1fb-20260529） | 有模型、来源、缓存、成本 | Evidence Partial | Worker 已记录 token/cost/receipt；真模型执行（provider_openai/deepseek-v4-pro）非 simulate；治理中心成本台账前端展示仍为静态数据 |
| CL-17 | 页面闭环 | 页面按钮是否真实闭环 | R1-A~F: 工作台"发送"/"提交澄清回答"/"确认目标"/"生成作战计划"/"确认计划"/"创建任务队列"/"启动一次执行"全部真实 POST API + 状态展示（verification-project-director-worker-run-r1fb-20260529） | 无假按钮 | Runtime Pass (工作台) | 工作台 7 个按钮全部真实闭环；scope fix: taskCreation.projectId；全站 CL-17 仍需其他页面验收 |
| CL-18 | 文档闭环 | 产品文档是否同步更新 | docs/product path | 变更有文档依据 |  |  |

---

## 3. 工作台验收清单

| ID | 验收项 | 回填证据 | 通过标准 | 状态 | 备注 |
|---|---|---|---|---|---|
| WB-01 | 工作台是否以 AI 项目主管对话为主 | 截图 / 组件路径 | 对话区是主视觉，不是统计大屏 |  |  |
| WB-02 | 是否只保留最小态势摘要 | 截图 | 不堆大量卡片 |  |  |
| WB-03 | 是否提供作战计划入口 | 截图 / 路由 / 弹窗 | 查看摘要，不铺完整任务表 |  |  |
| WB-04 | 是否提供 Agent 动向入口 | 截图 / 弹窗 | 只展示摘要，不重复治理页 |  |  |
| WB-05 | 是否提供项目流程入口 | 截图 / Mermaid/流程组件 | 可点击或可跳转 |  |  |
| WB-06 | 待确认事项是否可处理 | API / 状态变化 | 同意/驳回/修改后有记录 |  |  |
| WB-07 | 阻塞处理是否跳转到正确页面 | 路由参数 | 带 projectId/taskId 上下文 |  |  |
| WB-08 | 页面打开是否不触发 AI 生成 | 网络请求/日志 | 只读缓存，不自动生成 |  |  |
| WB-09 | 聊天框是否能访问项目上下文 | R1-A: selectedProjectId 传入 DirectorChatEntry；展示项目上下文 badge（项目名称+project_id）；selectedProjectId === "all" 映射为 null（verification-project-director-workbench-session-entry-r1a-20260528） | 能读取项目、任务、运行、交付、治理摘要 | Runtime Pass | R1-A 已验证项目 ID 传递和上下文展示；更深层上下文（任务/运行/摘要）需后续阶段补充 |
| WB-10 | 宽屏布局是否有效利用空间 | 截图 | 不出现大片无意义空白 |  |  |

---

## 4. 项目页验收清单

| ID | 验收项 | 回填证据 | 通过标准 | 状态 | 备注 |
|---|---|---|---|---|---|
| PRJ-01 | 项目页是否展示项目目标 | 截图 / 数据字段 | 目标清晰可见 |  |  |
| PRJ-02 | 是否展示当前阶段 | 截图 | 阶段状态明确 |  |  |
| PRJ-03 | 是否展示 AI 作战计划摘要 | 截图 / summary source | 摘要来自缓存或 fallback |  |  |
| PRJ-04 | 是否展示当前风险摘要 | 截图 | 风险关联任务/运行/审批证据 |  |  |
| PRJ-05 | 是否只展示最近项目事件 | 截图 | 不铺完整时间线 |  |  |
| PRJ-06 | 是否避免侧边栏入口重复矩阵 | 截图 | 不常驻任务/运行/仓库/审批入口组 |  |  |
| PRJ-07 | 请求重新评估是否只生成建议 | API/状态 | 不直接改计划 |  |  |
| PRJ-08 | 计划变更是否进入用户确认 | 审批/待确认记录 | 用户确认后才应用 |  |  |
| PRJ-09 | 项目页是否不承担任务编辑 | 截图/按钮 | 任务编辑跳任务队列 |  |  |
| PRJ-10 | 项目页是否不承担运行诊断 | 截图 | 运行详情跳运行观测 |  |  |

---

## 5. 执行中心总体验收清单

| ID | 验收项 | 回填证据 | 通过标准 | 状态 | 备注 |
|---|---|---|---|---|---|
| EXE-01 | 执行中心是否默认进入任务队列 | 路由/截图 | 默认不是总览大屏 |  |  |
| EXE-02 | 是否有任务队列/运行观测/仓库工作区页签 | 截图 | 三者同级 |  |  |
| EXE-03 | 顶部摘要是否轻量 | 截图 | 一句话，不堆卡片 |  |  |
| EXE-04 | 是否避免三栏大屏 | 截图 | 不把任务/运行/仓库强行塞一屏 |  |  |
| EXE-05 | 页签切换是否保留 projectId 上下文 | 路由参数 | 切换后上下文不丢 |  |  |
| EXE-06 | 执行中心是否不展示交付物审批 | 截图 | 交付物/审批去成果中心 |  |  |

---

## 6. 任务队列验收清单

| ID | 验收项 | 回填证据 | 通过标准 | 状态 | 备注 |
|---|---|---|---|---|---|
| TASK-01 | 任务是否按调度优先级分组 | TaskQueueList.tsx:19-51 groupTasks() 五组 | 待人工/阻塞/失败、执行中、可调度/待执行、等待依赖/暂停、已完成 | Pass | 2026-05-19 验收，详 verification-task-queue-phase1 |
| TASK-02 | 任务列表是否弱化表格感 | border card rows, no HTML table | 轻列表，不是数据库表 | Pass | 2026-05-19 |
| TASK-03 | 每个任务是否只展示核心 6 项 | TaskQueueList.tsx:210-291 TaskQueueItem | 标题、状态、Agent、优先级、阻塞/依赖、最近运行 | Pass | 2026-05-19 验收 |
| TASK-04 | 右侧是否为执行态势面板 | TaskExecutionSituationPanel.tsx | Agent 负载、阻塞原因、最近运行、AI 建议 | Pass | 2026-05-19 |
| TASK-05 | 任务详情是否用抽屉 | ExecutionTasksTab.tsx:274 TaskDetailDrawer | 不做常驻大右栏 | Pass | 2026-05-19 验收 |
| TASK-06 | 暂停是否真实调用后端 | TaskDetailDrawer 暂停按钮(pending/failed/blocked) → POST /tasks/:id/pause；条件对齐后端 build_pause_transition:115 | 状态改变 | Pass | 2026-05-19 Phase2 验收+对齐状态机 |
| TASK-07 | 恢复是否真实调用后端 | TaskDetailDrawer 恢复按钮(paused) → POST /tasks/:id/resume；条件对齐后端 build_resume_transition:134 | 状态改变 | Pass | 2026-05-19 Phase2 验收 |
| TASK-08 | 请求人工是否真实调用后端 | TaskDetailDrawer 请求人工按钮(pending/failed/blocked/paused) → POST /tasks/:id/request-human；条件对齐后端 build_request_human_review_transition:159-163 | waiting_human 状态 | Pass | 2026-05-19 Phase2 验收+对齐状态机 |
| TASK-09 | 人工已处理是否真实调用后端 | TaskDetailDrawer 人工已处理按钮 → POST /tasks/:id/resolve-human | 状态回到可调度 | Pass | 2026-05-19 Phase2 验收 |
| TASK-10 | 重新入队文案是否准确 | TaskDetailDrawer 重新入队按钮 + “重置为待执行，下一次 Worker 调度时执行” | 说明”下一次调度执行” | Pass | 2026-05-19 Phase2 验收 |
| TASK-11 | 查看运行是否跳运行观测 | buildRunRoute({runId, taskId, projectId}) | 带 runId/taskId | Pass | 2026-05-19 验收 |
| TASK-12 | 查看仓库上下文是否跳仓库工作区 | /projects/:pid/repository?taskId=xxx | 带 taskId/projectId | Pass | 2026-05-19 验收 |
| TASK-13 | 任务页是否不展示完整日志 | 无完整日志渲染 | 日志去运行观测 | Pass | 2026-05-19 确认 |
| TASK-14 | 任务页是否不展示仓库树 | 无仓库树渲染 | 仓库树去仓库弹窗 | Pass | 2026-05-19 确认 |

---

## 7. 运行观测验收清单

| ID | 验收项 | 回填证据 | 通过标准 | 状态 | 备注 |
|---|---|---|---|---|---|
| RUN-01 | 是否采用左侧运行轻列表 + 右侧诊断详情 | ExecutionRunsTab.tsx grid-cols-[35fr_65fr] + RunsListPanel/RunsTaskDetailSection | 布局清晰 | Pass | 2026-05-19 Phase1: /execution?tab=runs 与 /runs 均采用此布局 |
| RUN-02 | 运行列表是否展示状态/Agent/任务/时间/短摘要 | RunListItemButton.tsx: status badge + title + time + cost + failure reason | 不做大表格 | Pass | 2026-05-19; owner_role_code 字段可用但 Phase1 保留在 panel 中 |
| RUN-03 | 右侧是否优先展示 AI 运行摘要 | RunsTaskDetailSection RunPrimarySummaryCard 优先展示 | 普通用户先看到结论 | Pass | 2026-05-19 |
| RUN-04 | 是否展示摘要来源 | RunPrimarySummaryCard source badge | source=ai/rule_fallback/reused | Pass | 2026-05-19 |
| RUN-05 | 是否展示失败分类 | RunsTaskDetailSection failure_category badge | failed/blocked 有原因 | Pass | 2026-05-19 |
| RUN-06 | 是否展示质量闸门/验证摘要 | RunsTaskDetailSection quality_gate_passed badge | 有则展示，无则说明未记录 | Pass | 2026-05-19 |
| RUN-07 | 技术日志是否用弹窗 | RunTechnicalLogModal + "查看技术日志"按钮 | 不默认铺日志 | Pass | 2026-05-19 |
| RUN-08 | 日志复制是否可用 | RunsTaskDetailSection CopyBtn 组件 clipboard API | 复制成功反馈 | Pass | 2026-05-19 |
| RUN-09 | 重新生成摘要是否手动触发 | RunPrimarySummaryCard 手动按钮 | 页面打开不自动生成 | Pass | 2026-05-19 |
| RUN-10 | 重试任务文案是否准确 | Phase1 未在运行观测加入重试按钮 | 不误导为立即重新运行 | N/A | 2026-05-19: 任务操作在任务队列抽屉中完成，运行观测保留为纯观测 |
| RUN-11 | 运行页是否不管理任务队列 | 无暂停/恢复/请求人工等任务操作按钮 | 任务操作只做关联跳转/重新入队 | Pass | 2026-05-19 |

---

## 8. 仓库工作区验收清单

| ID | 验收项 | 回填证据 | 通过标准 | 状态 | 备注 |
|---|---|---|---|---|---|
| REPO-01 | 是否定位为受控代码变更提案中心 | 无编辑区/IDE，仅状态条+步骤链+当前面板 | 不像在线 IDE | Pass | 2026-05-19 Phase1: 仅状态观测+步骤追踪 |
| REPO-02 | 是否提供变更需求入口 | Phase1 执行中心页签未提供直接入口，完整页有 | 用户可向 AI 主管提出需求 | Partial | 2026-05-19: 变更需求入口在 /projects/:id/repository 完整页 |
| REPO-03 | AI 主管评估是否先于文件定位 | 步骤链 "AI 主管评估"(idx=1) 先于 "文件定位"(idx=2) | 不直接编辑文件 | Pass | 2026-05-19 |
| REPO-04 | 步骤条是否包含完整链路 | CHANGE_CHAIN_STEPS 9步完整链路 | 变更需求→...→放行 | Pass | 2026-05-19 |
| REPO-05 | 每次只展示当前步骤工作面板 | CurrentStepPanel 单阶段摘要 | 不堆一屏模块 | Pass | 2026-05-19 |
| REPO-06 | 仓库树是否默认隐藏 | ExecutionRepositoryTab 无仓库树 | 弹窗/抽屉查看 | Pass | 2026-05-19: 仓库树在完整页 |
| REPO-07 | 快照面板是否轻量 | 4格状态: 快照/会话/批次/草案，各一个值 | 只展示状态、数量 | Pass | 2026-05-19 |
| REPO-08 | 文件定位结果是否卡片化 | Phase1 未在页签内展示文件定位详情 | 展示路径、命中原因 | N/A | 2026-05-19: 文件定位在 /projects/:id/repository |
| REPO-09 | 上下文包是否展示大小/截断风险 | Phase1 未在页签内展示上下文包 | 能判断成本 | N/A | 2026-05-19: 上下文包在完整页 |
| REPO-10 | 变更批次是否展示影响范围 | Phase1 仅展示批次数量 | 关联计划、任务、文件 | Partial | 2026-05-19: 批次详情在完整页 |
| REPO-11 | 预检不通过时是否阻止继续 | Phase1 步骤链展示预检状态 | 不允许直接生成草案 | Pass | 2026-05-19: 流程由后端状态机控制 |
| REPO-12 | 提交草案是否明确不是 git commit | candidates>0 时显示免责文案 | 有显著提示 | Pass | 2026-05-19 |
| REPO-13 | 放行判断是否不是发布按钮 | 无发布按钮，仅步骤指示 | 只做 judgement | Pass | 2026-05-19 |
| REPO-14 | 仓库页是否不展示完整任务列表 | 无任务列表渲染 | 只显示关联任务摘要 | Pass | 2026-05-19 |
| REPO-15 | 仓库页是否不展示完整运行日志 | 无运行日志渲染 | 日志去运行观测 | Pass | 2026-05-19 |

---

## 9. 成果中心验收清单

| ID | 验收项 | 回填证据 | 通过标准 | 状态 | 备注 |
|---|---|---|---|---|---|
| DEL-01 | 成果中心是否只有交付物/审批两个页签 | /delivery 成果中心父页面，两个页签：交付物、审批 | 不做成果总览大屏 | Pass | 2026-05-19返工: 建立成果中心父页面收敛两个页签 |
| DEL-02 | 默认是否打开交付物 | /deliverables 默认进入 DeliverableListPanel | 先看成果再审批 | Pass | 2026-05-19 |
| DEL-03 | 交付物是否轻列表 + 右侧摘要 | grid-cols-[1.1fr_1.4fr] 左侧列表 + 右侧版本详情 | 不做完整大表格 | Pass | 2026-05-19 |
| DEL-04 | 交付物是否按处理优先级排序 | 快照接口按时间倒序，项目筛选 | 按优先级可筛 | Pass | 2026-05-19; 后端 snapshot 负责排序 |
| DEL-05 | 交付物摘要是否自动生成并缓存 | GET /deliverables/projects/:id 读取缓存快照 | 页面打开不生成 | Pass | 2026-05-19 |
| DEL-06 | 正文是否用弹窗 | DeliverableVersionList 面板展示版本正文，非全屏铺开 | 不常驻铺开 | Pass | 2026-05-19 |
| DEL-07 | 证据链是否用弹窗 | ChangeEvidencePanel 按需加载 | 不挤占主页面 | Pass | 2026-05-19 |
| DEL-08 | 版本记录是否用弹窗 | DeliverableVersionList 版本切换面板 | 可追溯 | Pass | 2026-05-19 |
| DEL-09 | 发起审批是否创建真实审批请求 | POST /approvals → 审批页出现待审项；交付物页本身不直接发起审批 | 审批页出现待审项 | Partial | 2026-05-19: 真实 API 已存在，但入口在 /approvals 页，/deliverables 页不直接发起审批（符合"交付物页不做审批决策"） |
| DEL-10 | 要求返工是否进入任务/返工链路 | ApprovalActionDrawer "要求修改" 调用 applyApprovalAction | 不只是文案 | Partial | 2026-05-19: 审批动作真实写后端；返工→任务队列闭环需后端验证 |
| DEL-11 | 交付物页是否不做审批决策 | 交付物页无审批按钮，审批在 /approvals | 通过/驳回在审批页 | Pass | 2026-05-19 |

---

## 10. 审批页验收清单

| ID | 验收项 | 回填证据 | 通过标准 | 状态 | 备注 |
|---|---|---|---|---|---|
| APV-01 | 是否采用左侧审批列表 + 右侧决策面板 | ApprovalInboxPage 审批队列 + ApprovalActionDrawer 右侧决策抽屉 | 结构清晰 | Pass | 2026-05-19 审计回填 |
| APV-02 | 审批列表是否按处理优先级排序 | 超时审批优先区 + 时间倒序队列 | 待我审批优先 | Pass | 2026-05-19 |
| APV-03 | 审批建议是否自动生成并缓存 | GET /approvals/projects/:id 读取后端缓存 | 页面打开不生成 | Pass | 2026-05-19 |
| APV-04 | 是否展示 AI 建议和理由 | 最近结论/请求说明/审批回放记录 | 建议通过/修改/驳回 | Pass | 2026-05-19: 审批建议以结构化记录呈现 |
| APV-05 | 是否展示证据充分性 | ChangeEvidencePanel + ApprovalHistoryPanel | 缺证据要标注 | Pass | 2026-05-19 |
| APV-06 | 通过按钮是否说明后果 | "确认该版本可以通过审批并允许后续阶段继续推进" | 用户知道通过后发生什么 | Pass | 2026-05-19 |
| APV-07 | 要求修改是否说明后果 | "记录需要补充的信息、风险说明或修改方向" | 生成返工请求 | Pass | 2026-05-19 |
| APV-08 | 驳回是否说明后果 | "明确驳回当前版本，要求下游先处理结论后再继续" | 关闭当前版本并保留证据 | Pass | 2026-05-19 |
| APV-09 | 审批动作是否真实写入后端 | applyApprovalAction → POST /approvals/:id/actions | 决策状态变化 | Pass | 2026-05-19: approve/reject/request_changes 均真实 POST |
| APV-10 | 审批页是否不展示完整成果库 | 审批页仅管理审批队列，成果库在 /deliverables | 成果库去交付物页 | Pass | 2026-05-19 |

---

## 11. 治理中心验收清单

| ID | 验收项 | 回填证据 | 通过标准 | 状态 | 备注 |
|---|---|---|---|---|---|
| GOV-01 | 治理中心是否定位为 AI 团队资产治理中心 | H1 "AI 团队资产治理中心"，5页签结构 | 不是普通设置页 | Pass | 2026-05-19 Phase1 |
| GOV-02 | 是否包含五个区块 | GovernancePage 5 tabs: team/roles/skills/policy/cost-memory | 本项目AI团队、角色治理、Skill治理、策略与权限、成本与记忆 | Pass | 2026-05-19 Phase1 |
| GOV-03 | 默认是否打开本项目 AI 团队 | default tab="team" | 首屏看团队，不是配置表 | Pass | 2026-05-19 Phase1 |
| GOV-04 | 是否区分角色模板和项目角色实例 | lifecycle badge: project_local/template_candidate 等 | 来源清晰 | Partial | 2026-05-19: 前端已展示，后端保存/确认闭环待接入 |
| GOV-05 | 是否区分正式 Skill、项目临时 Skill、Skill 迭代候选 | status badge: stable/candidate/temporary | 生命周期清晰 | Partial | 2026-05-19: 前端已展示，沉淀流程待用户确认闭环 |
| GOV-06 | 角色是否有生命周期 | lifecycle badge 展示 5 种状态 | project_local/template_candidate/template_stable/deprecated/archived | Partial | 2026-05-19: 前端已展示，完整流转需后端 |
| GOV-07 | Skill 是否有生命周期 | lifecycle badge 展示 6 种状态 | draft/temporary/candidate/stable/deprecated/archived | Partial | 2026-05-19: 前端已展示，完整流转需后端 |
| GOV-08 | Skill 是否展示最近消费证据 | 标注"暂无消费证据" | 不是只显示已绑定 | Partial | 2026-05-19: 消费证据数据待后端接入 |
| GOV-09 | AI 是否只能建议沉淀角色/Skill | 文案说明+按钮禁用 | 用户确认后才正式保存 | Partial | 2026-05-19: 确认闭环无后端接口，保存按钮禁用 |
| GOV-10 | 临时 Skill 是否有清理策略 | 文案说明多因素判断 | 不只按时间，还看使用次数/绑定/证据/版本替代 | Partial | 2026-05-19: 前端已完成文案说明 |
| GOV-11 | 策略与权限是否分三类 | 三列卡片：可自动执行/需确认/禁止自动执行 | 可自动执行/需确认/禁止自动执行 | Pass | 2026-05-19 Phase1 |
| GOV-12 | 危险动作是否默认禁止或需审批 | 禁止列表含 git commit/push/发布/删除等 8 项 | git写入、删除、发布等不自动 | Pass | 2026-05-19 Phase1: 静态基线 |
| GOV-13 | 成本与记忆是否展示成本来源可信度 | 标注 heuristic/missing/provider_reported | provider_reported/heuristic/missing | Partial | 2026-05-19: 前端已说明，数据源为静态 |
| GOV-14 | 记忆 compact/rehydrate/reset 是否真实闭环 | 按钮已禁用+说明原因 | 不是假按钮 | Partial | 2026-05-19: 无后端闭环，按钮正确禁用 |
| GOV-15 | 治理中心是否不展示完整任务/运行/审批列表 | 无任务/运行/审批列表渲染 | 只展示证据摘要和跳转 | Pass | 2026-05-19 Phase1 |

---

## 12. 成本治理验收清单

| ID | 验收项 | 回填证据 | 通过标准 | 状态 | 备注 |
|---|---|---|---|---|---|
| COST-01 | 页面打开是否不触发 AI 生成 | 网络请求/日志 | 只读缓存 |  |  |
| COST-02 | 是否有 L0 规则摘要 | 数据/代码 | 不必要调用模型 |  |  |
| COST-03 | 是否有 L1 短摘要 | 数据/代码 | 50-150字，便宜/快模型 |  |  |
| COST-04 | 是否有 L2 结构化判断 | 数据/代码 | 用于重试/送审/沉淀判断 |  |  |
| COST-05 | 是否有 L3 高价值决策 | 数据/代码 | 用于重规划/复杂根因/高风险放行 |  |  |
| COST-06 | L3 是否记录调用理由 | 台账 | 无理由不得强模型 |  |  |
| COST-07 | AI 生成是否写入资产台账 | 数据表/文件 | 对象、事件、模型、来源、成本、缓存、采纳 |  |  |
| COST-08 | 是否支持 source=rule_fallback | 数据/截图 | Provider 失败不空白 |  |  |
| COST-09 | 是否支持 source=reused/inherited | 数据/截图 | 能体现复用 |  |  |
| COST-10 | 摘要是否有过期判断 | 数据/截图 | 关联对象变化后标记过期 |  |  |
| COST-11 | 是否支持省钱/标准/深度模式 | 配置/截图 | 放治理中心，不放设置页 |  |  |
| COST-12 | 角色/Skill 复用收益是否记录 | 数据/截图 | 展示复用数量和节省价值 |  |  |
| COST-13 | 自动摘要长度是否受控 | 数据/配置 | 默认短摘要 |  |  |
| COST-14 | 是否避免重复生成同一对象摘要 | 台账 | 同一版本不重复调用 |  |  |

---

## 13. 设置页验收清单

| ID | 验收项 | 回填证据 | 通过标准 | 状态 | 备注 |
|---|---|---|---|---|---|
| SET-01 | 设置页是否只保留四区块 | SettingsPage 四区块：Provider、环境、安全、诊断 | Provider与模型、运行环境、安全与权限、系统诊断 | Pass | 2026-05-19 Phase1 |
| SET-02 | Provider 配置是否状态展示 + 弹窗编辑 | 状态摘要常驻，编辑区折叠展开 | 不常驻大表单 | Pass | 2026-05-19 Phase1 |
| SET-03 | API Key 是否隐藏 | masked 展示 + input type=password | 不明文展示 | Pass | 2026-05-19 Phase1 |
| SET-04 | 保存 Provider 是否真实写入后端 | PUT /provider-settings/openai | 刷新后仍存在 | Pass | 2026-05-19 Phase1 |
| SET-05 | 测试连接是否真实闭环 | POST /provider-settings/openai/test | 无后端不能做假按钮 | Pass | 2026-05-19 Phase1 |
| SET-06 | 运行环境是否展示健康状态 | GET /health 真实接入 | 后端、数据库、Worker、Event Stream 等 | Pass | 2026-05-19; 数据库/Worker/Event Stream 暂无专用接口，已标注 |
| SET-07 | 系统诊断是否可复制 | 复制按钮含 Provider+Health+安全+缺失接口 | 复制真实状态 | Partial | 2026-05-19: 复制功能完成；数据库/Worker/ES 无专用诊断接口 |
| SET-08 | 安全与权限是否只放系统级能力 | 仓库安全边界+项目绑定，无 AI 策略 | 不混入 AI 权限策略 | Pass | 2026-05-19 Phase1 |
| SET-09 | 成本模式是否不在设置页 | 设置页无成本相关内容 | 去治理中心 | Pass | 2026-05-19 Phase1 |
| SET-10 | 设置页是否不展示运行日志大页 | 无日志渲染 | 日志去运行观测 | Pass | 2026-05-19 Phase1 |

---

## 14. 前端风格与布局验收清单

| ID | 验收项 | 回填证据 | 通过标准 | 状态 | 备注 |
|---|---|---|---|---|---|
| UI-01 | 是否保持深色后台风格 | 截图 | 风格统一，不突兀 |  |  |
| UI-02 | 是否减少重复信息 | 截图对比 | 同一数据不在多个页面完整重复 |  |  |
| UI-03 | 是否多用弹窗/抽屉承载细节 | 截图 | 页面常驻信息轻量 |  |  |
| UI-04 | 是否有效利用宽屏空间 | 截图 | 不出现内容过窄、大量右侧空白 |  |  |
| UI-05 | 是否避免大面积表格 | 截图 | 表格弱化为轻列表/卡片 |  |  |
| UI-06 | 是否避免三栏大屏堆叠 | 截图 | 页面只有一个主视角 |  |  |
| UI-07 | 是否长 ID 不撑版 | 截图 | 截断、复制、title 悬停 |  |  |
| UI-08 | 是否按钮数量受控 | 截图 | 常驻按钮少，更多操作收纳 |  |  |
| UI-09 | 是否空状态有下一步引导 | 截图 | 不只是“暂无数据” |  |  |
| UI-10 | 是否移动/窄屏可用 | 截图 | 布局不崩 |  |  |

---

## 15. 后端接口与真实闭环验收清单

| ID | 验收项 | 回填证据 | 通过标准 | 状态 | 备注 |
|---|---|---|---|---|---|
| API-01 | 每个执行按钮是否有真实 API 或明确跳转 | 代码/API | 无假按钮 |  |  |
| API-02 | 404 是否能区分路由缺失和数据缺失 | 测试记录 | 不误判 |  |  |
| API-03 | 409 是否能提示状态冲突原因 | 测试记录 | 用户知道前置条件 |  |  |
| API-04 | 422 是否能提示参数问题 | 测试记录 | 可修复 |  |  |
| API-05 | 500 是否有诊断入口 | 日志/设置页诊断 | 可排查 |  |  |
| API-06 | 状态变更后是否刷新当前页面数据 | 操作截图 | 页面不显示旧状态 |  |  |
| API-07 | 所有写操作是否有成功/失败反馈 | 截图 | 用户知道结果 |  |  |
| API-08 | 高风险动作是否二次确认 | 截图 | 删除/清除/危险能力开启 |  |  |

---

## 16. 文档回填验收清单

| ID | 验收项 | 回填证据 | 通过标准 | 状态 | 备注 |
|---|---|---|---|---|---|
| DOC-01 | 页面信息架构文档是否更新 | docs/product 文件 | 页面职责变更已记录 |  |  |
| DOC-02 | 闭环流程文档是否更新 | docs/product 文件 | 流程变更已记录 |  |  |
| DOC-03 | 验收清单是否回填 | 本文件 | 有状态和证据 |  |  |
| DOC-04 | Codex 指令是否引用对应文档 | 指令文本 | 不自由发挥 |  |  |
| DOC-05 | Gate 结论是否区分 Pass/Partial/Blocked/Fail | Gate 文档 | 不虚假总 Pass |  |  |

---

## 17. Codex 阶段任务回填模板

每次交给 Codex 完成后，建议回填以下模板：

```text
阶段名称：
目标页面：
本阶段目标：
严格边界：
验收标准：

Codex 完成结果：
- 提交哈希：
- 分支：
- 是否 push：
- 修改文件：
- 新增文件：
- 删除文件：
- build 命令：
- build 结果：
- 测试命令：
- 测试结果：

闭环证据：
- 前端入口：
- API 调用：
- 后端 route：
- 状态变化：
- 页面截图：
- 文档回填：

验收结论：Pass / Partial / Blocked / Fail
遗留问题：
下一阶段建议：
```

---

## 18. 最终 Gate 判定模板

| Gate 项 | 结论 | 证据 | 风险 | 后续动作 |
|---|---|---|---|---|
| 页面职责是否符合文档 |  |  |  |  |
| 按钮是否真实闭环 |  |  |  |  |
| API 是否真实接入 |  |  |  |  |
| 数据是否可追溯 |  |  |  |  |
| 摘要是否缓存/复用 |  |  |  |  |
| 成本是否受控 |  |  |  |  |
| 角色/Skill 是否有消费证据 |  |  |  |  |
| 文档是否回填 |  |  |  |  |
| build 是否通过 |  |  |  |  |
| 是否允许进入下一阶段 |  |  |  |  |

最终结论：

```text
Pass / Partial / Blocked / Fail
```

说明：

```text

```

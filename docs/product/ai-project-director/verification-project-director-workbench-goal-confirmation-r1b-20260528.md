# AI Project Director 工作台 Goal Confirmation R1-B Evidence

> 文档类型：Runtime Evidence（窄范围验证）
> 验证日期：2026-05-28
> 验证人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`1729033a2f507ac89737cb397b3b8df2082060bc`
> 前置阶段 commit：`5d959f0` (R1-A session entry), `0036cdc` (R1-A evidence)
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应主链路：步骤 2（AI 主管澄清目标 → 用户回答）→ 步骤 3（用户确认目标）

---

## 1. 验证范围

本 evidence 文档覆盖 R1-B 阶段：Codex 已提交前端最小接入代码（commit `1729033`），DeepSeek 负责验证真实链路。

R1-B 在前端新增以下能力：
- 在 clarifying 状态下，每个澄清问题下方展示 textarea 供用户填写回答
- "提交澄清回答"按钮 → POST /project-director/sessions/{id}/answers
- 回答提交后展示 goal_summary + "确认目标"按钮
- "确认目标"按钮 → POST /project-director/sessions/{id}/confirm

### 1.1 映射验收项

| 验收项 ID | 描述 | 本阶段验证范围 |
|---|---|---|
| CL-01 | 用户目标是否被记录 | POST session 持久化 goal_text；answer/confirm 流程后 GET readback 一致 |
| CL-02 | AI 项目主管是否做目标澄清 | clarifying_questions 渲染 + 用户可提交 answers → 后端生成 goal_summary |
| CL-03 | 目标确认后允许后续生成计划（前置条件） | confirm 成功 → status=confirmed → 为后续 plan version 创建提供前置条件 |
| WB-09 | 聊天框是否能访问项目上下文 | selectedProjectId 传递保持；上下文 badge 保持 |

---

## 2. 前置检查

### 2.1 Commit 验证

```text
origin/main HEAD: 1729033a2f507ac89737cb397b3b8df2082060bc
```

变更文件（仅前端，4 files）：
- `apps/web/src/features/project-director/api.ts` (+25 lines: submitProjectDirectorAnswers, confirmProjectDirectorGoal)
- `apps/web/src/features/project-director/hooks.ts` (+18/-5 lines: useSubmitProjectDirectorAnswers, useConfirmProjectDirectorGoal)
- `apps/web/src/features/project-director/types.ts` (+9 lines: SubmitProjectDirectorAnswersInput, ConfirmProjectDirectorGoalInput)
- `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx` (+176/-5 lines: answer textareas, submit answers button, confirm goal button, goal summary display)

**结论：diff 仅包含 R1-B 前端接入范围（回答澄清问题 + 确认目标），无后端修改，无 plan-versions / create-tasks / planning/apply / worker 调用。**

### 2.2 已检查文件

- `.kkr/skills/ai-project-director-command-governance/SKILL.md`
- `docs/product/ai-project-director/page-information-architecture-20260518.md`
- `docs/product/ai-project-director/closure-flow-20260518.md`
- `docs/product/ai-project-director/closure-checklist-20260518.md`
- `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md`
- `docs/product/ai-project-director/verification-project-director-workbench-session-entry-r1a-20260528.md`
- `apps/web/src/features/project-director/api.ts`
- `apps/web/src/features/project-director/hooks.ts`
- `apps/web/src/features/project-director/types.ts`
- `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx`
- `runtime/orchestrator/app/api/routes/project_director.py`
- `runtime/orchestrator/tests/test_project_director_sessions.py`

---

## 3. Build 与测试

### 3.1 前端 Build

```text
命令: cd apps/web && npm.cmd run build
结果: ✓ built in 3.44s
      499 modules transformed.
      TypeScript tsc -b: 通过
```

### 3.2 后端测试

```text
命令: cd runtime/orchestrator && python -m pytest tests/test_project_director_sessions.py -v
结果: 38 passed in 9.93s
      覆盖: CreateSession(10) / GetSession(2) / SubmitAnswers(10) / ConfirmGoal(7) / Service(6) / ContractFields(3)
```

---

## 4. Live HTTP Evidence

### 4.1 测试方法

临时启动 uvicorn（端口 9879，临时 SQLite 数据库），通过 `http.client` 直接调用 API。

### 4.2 Session ID

`45fcae9c-9caf-48bb-b894-d33847b6ed1b`

### 4.3 Step 1: POST /project-director/sessions

```text
请求: POST /project-director/sessions
Body: {"goal_text": "构建一个完整的用户认证系统，支持OAuth2.0和JWT，包含登录注册和密码重置功能，目标明确"}

响应: 201 Created
  status: clarifying
  clarifying_questions count: 5
  gate_conclusion: Partial
```

### 4.4 Step 2: POST /project-director/sessions/{id}/answers

```text
请求: POST /project-director/sessions/{id}/answers
Body: {"answers": [{"question_id": "q_...", "answer": "针对..."}, ... 5 answers]}

响应: 200 OK
  status: ready_to_confirm
  goal_summary: present (non-empty, contains goal and answer sections)
  clarifying_answers count: 5
  needs_user_confirmation: true
```

### 4.5 Step 3: GET readback after answers

```text
请求: GET /project-director/sessions/{id}

响应: 200 OK
  status: ready_to_confirm
  answers persisted: True (5/5 match)
  goal_summary present: True
```

### 4.6 Step 4: POST /project-director/sessions/{id}/confirm

```text
请求: POST /project-director/sessions/{id}/confirm

响应: 200 OK
  status: confirmed
  confirmed_at: 2026-05-29T06:11:31.904103+00:00
  gate_conclusion: Partial（目标闭环 Pass，总闭环未完成）
```

### 4.7 Step 5: Final GET readback

```text
请求: GET /project-director/sessions/{id}

响应: 200 OK
  status: confirmed
  goal_summary match: True (matches Step 2 response)
  confirmed_at match: True (matches Step 4 response)
  gate_conclusion: Partial（目标闭环 Pass，总闭环未完成）
```

### 4.8 Error Paths

```text
6. Confirm without answers: 409 Conflict (expected 409)  ✓
7. Submit empty answers: 422 Unprocessable Entity (expected 422)  ✓
8. Re-confirm already confirmed: 200 OK (idempotent)  ✓
```

---

## 5. 前端代码审查

### 5.1 R1-B 新增 API 调用

| API | Method | 用途 | 调用位置 |
|---|---|---|---|
| `/project-director/sessions/{id}/answers` | POST | 提交澄清回答 | `handleSubmitAnswers` → `submitAnswersMutation.mutateAsync` |
| `/project-director/sessions/{id}/confirm` | POST | 确认目标摘要 | `handleConfirmGoal` → `confirmGoalMutation.mutateAsync` |

### 5.2 越界检查

DirectorChatEntry.tsx 及其依赖的 api.ts 中 **不存在** 以下动作的调用：

| 动作 | 是否实现 | 证据 |
|---|---|---|
| 调用 /plan-versions | 否 | 无 POST/GET plan-versions API 调用 |
| 调用 /create-tasks | 否 | 无 task creation API 调用 |
| 调用 planning/apply | 否 | 无 planning route 调用 |
| 调度 Worker | 否 | 无 worker dispatch API 调用 |
| apply-local / git-commit | 否 | 无仓库写入链路 |

**结论：R1-B 前端仅接入 answers submit 和 goal confirm，未越界 ✓**

### 5.3 前端按钮禁用逻辑（相当于前端门禁）

| 条件 | 按钮状态 |
|---|---|
| `canSubmitAnswers`: session.status === "clarifying" AND all required questions answered AND not pending | 启用"提交澄清回答" |
| `canConfirmGoal`: session.status === "ready_to_confirm" AND not pending | 启用"确认目标" |
| required questions 未回答完整 | "提交澄清回答" disabled |
| 非 ready_to_confirm 状态 | "确认目标" disabled |

**结论：前端按钮禁用逻辑正确，required 问题未回答完整时前端阻止提交 ✓**

---

## 6. 映射验收项结论

| 验收项 | 状态 | 说明 |
|---|---|---|
| CL-01 | Runtime Pass | R1-A 已验证 session 创建 + goal_text 持久化；R1-B 全链路（create → answer → confirm → readback）goal_text 一致 |
| CL-02 | Runtime Pass | R1-A 已验证 clarifying_questions 生成与展示；R1-B 用户可提交 answers → 后端生成 goal_summary → GET readback 确认持久化 |
| CL-03 | Evidence Partial | 目标确认流程完成（status=confirmed）；confirmed 是后续 plan version 创建的前置条件（只有 confirmed session 可生成 plan）；但 plan version 生成尚未接入前端。**不得写 Pass** |
| WB-09 | Runtime Pass | selectedProjectId 传递链路保持；项目上下文 badge 保持；无退化 |

---

## 7. Gate 结论

### 7.1 R1-B 阶段 Gate

| Gate 项 | 结论 | 证据 |
|---|---|---|
| 前端 Build 通过 | Pass | `npm.cmd run build` → built in 3.44s |
| 后端测试通过 | Pass | 38 passed in 9.93s |
| Live HTTP Create Session | Pass | 201 Created |
| Live HTTP Submit Answers | Pass | 200, status=ready_to_confirm, goal_summary present |
| Live HTTP GET Readback (after answers) | Pass | 200, answers persisted, goal_summary persisted |
| Live HTTP Confirm Goal | Pass | 200, status=confirmed, confirmed_at non-null |
| Live HTTP Final GET Readback | Pass | 200, goal_summary match, confirmed_at match, status=confirmed |
| Error: Confirm without answers | Pass | 409 Conflict |
| Error: Empty answers | Pass | 422 Unprocessable |
| Idempotent confirm | Pass | 200 OK |
| 未调用 plan-versions | Pass | 前端无相关 API 调用 |
| 未调用 create-tasks | Pass | 前端无相关 API 调用 |
| 未调用 planning/apply | Pass | 前端无相关 API 调用 |
| 未调用 Worker | Pass | 前端无相关 API 调用 |

**R1-B Gate：Runtime Pass**

### 7.2 AI Project Director Total Closure

**仍为 Partial**

原因：
- CL-03 仅满足前置条件（目标确认完成），plan version 生成/确认前端尚未接入
- CL-04~CL-18 尚未完成
- 计划生成、任务创建、Worker 调度、运行证据、交付物、审批、仓库闭环、治理沉淀、成本台账均未接入

---

## 8. 文档修改清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `docs/product/ai-project-director/verification-project-director-workbench-goal-confirmation-r1b-20260528.md` | 新增 | 本 evidence 文档 |
| `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md` | 追加 | 工作台 R1-B 记录（4.1.2） |
| `docs/product/ai-project-director/closure-checklist-20260518.md` | 更新 | CL-01/CL-02/WB-09 状态细化；CL-03 标注前置条件 |

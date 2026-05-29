# AI Project Director 工作台 Session 接入 R1-A Evidence

> 文档类型：Runtime Evidence（窄范围验证）
> 验证日期：2026-05-28
> 验证人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`5d959f0d245fc69034dc19afad3303f02d881d2a`
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应主链路：步骤 1（用户提出目标）→ 步骤 2（AI 主管澄清目标）

---

## 1. 验证范围

本 evidence 文档覆盖 R1-A 阶段：Codex 已提交前端最小接入代码（commit `5d959f0`），DeepSeek 负责验证真实链路，不改业务代码。

### 1.1 映射验收项

| 验收项 ID | 描述 | 本阶段验证范围 |
|---|---|---|
| CL-01 | 用户目标是否被记录 | POST /project-director/sessions 创建 session 并持久化 goal_text；GET 读回验证 |
| CL-02 | AI 项目主管是否做目标澄清 | 创建 session 后返回 clarifying_questions；前端渲染澄清问题列表 |
| WB-09 | 聊天框是否能访问项目上下文 | selectedProjectId 传入 DirectorChatEntry；前端展示项目上下文 badge |

---

## 2. 前置检查

### 2.1 Commit 验证

```text
origin/main HEAD: 5d959f0d245fc69034dc19afad3303f02d881d2a
```

变更文件（仅前端，6 files）：
- `apps/web/src/features/project-director/api.ts` (new)
- `apps/web/src/features/project-director/hooks.ts` (new)
- `apps/web/src/features/project-director/types.ts` (new)
- `apps/web/src/pages/workbench/WorkbenchPage.tsx` (mod)
- `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx` (mod)
- `apps/web/vite.config.ts` (mod)

**结论：diff 仅包含 R1-A 前端接入范围，无后端修改，无计划/task/worker 相关代码。**

### 2.2 已检查文件

- `.kkr/skills/ai-project-director-command-governance/SKILL.md`
- `docs/product/ai-project-director/page-information-architecture-20260518.md`
- `docs/product/ai-project-director/closure-flow-20260518.md`
- `docs/product/ai-project-director/closure-checklist-20260518.md`
- `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md`
- `apps/web/src/features/project-director/api.ts`
- `apps/web/src/features/project-director/hooks.ts`
- `apps/web/src/features/project-director/types.ts`
- `apps/web/src/pages/workbench/WorkbenchPage.tsx`
- `apps/web/src/pages/workbench/components/DirectorChatEntry.tsx`
- `apps/web/vite.config.ts`
- `runtime/orchestrator/app/api/routes/project_director.py`
- `runtime/orchestrator/tests/test_project_director_sessions.py`

---

## 3. Build 与测试

### 3.1 前端 Build

```text
命令: cd apps/web && npm.cmd run build
结果: ✓ built in 3.49s
      499 modules transformed.
      TypeScript tsc -b: 通过
```

### 3.2 后端测试

```text
命令: cd runtime/orchestrator && python -m pytest tests/test_project_director_sessions.py -v
结果: 38 passed in 9.80s
      覆盖: CreateSession(10) / GetSession(2) / SubmitAnswers(10) / ConfirmGoal(7) / Service(6) / ContractFields(3)
```

---

## 4. Live HTTP Evidence

### 4.1 测试方法

临时启动 uvicorn（端口 9878，临时 SQLite 数据库），通过 `http.client` 直接调用 API。

### 4.2 POST /project-director/sessions

```text
请求: POST /project-director/sessions
Body: {"goal_text": "构建一个完整的用户认证系统，支持OAuth2.0和JWT，包含登录注册和密码重置功能"}

响应: 201 Created
{
  "id": "50ba2cae-bb16-4a29-acc4-f20c39133508",
  "project_id": null,
  "goal_text": "构建一个完整的用户认证系统，支持OAuth2.0和JWT，包含登录注册和密码重置功能",
  "status": "clarifying",
  "clarifying_questions": [5 items],
  "next_action": "请继续回答 5 个必答问题后提交答案",
  "gate_conclusion": "Partial",
  "needs_user_confirmation": true,
  "forbidden_actions": ["不生成计划", "不创建任务", "不调度 Worker", "不写仓库"],
  ...
}
```

### 4.3 GET /project-director/sessions/{session_id} Readback

```text
请求: GET /project-director/sessions/50ba2cae-bb16-4a29-acc4-f20c39133508

响应: 200 OK
goal_text match: ✓ True
clarifying_questions count match: ✓ True (5 items, same as POST response)
readback status: clarifying
readback gate_conclusion: Partial
所有必要字段存在 (id, status, goal_text, clarifying_questions, next_action, gate_conclusion): ✓ True
```

### 4.4 Error Cases

```text
POST with empty goal_text: 422 ✓ (符合预期)
GET nonexistent session: 404 ✓ (符合预期)
```

---

## 5. 前端代码审查

### 5.1 selectedProjectId 传递

`WorkbenchPage.tsx:82-85`:
```typescript
<DirectorChatEntry
  selectedProjectId={selectedProjectId}
  selectedProjectName={selectedProjectName}
/>
```

`DirectorChatEntry.tsx:27`:
```typescript
const scopedProjectId = selectedProjectId === "all" ? null : selectedProjectId;
```

**结论：selectedProjectId === "all" 时 project_id 为 null  ✓**

### 5.2 超范围动作检查

DirectorChatEntry.tsx 中 **不存在** 以下动作的实现：

| 动作 | 是否实现 | 证据 |
|---|---|---|
| 回答澄清问题 | 否 | 无 answer submission UI 或 API 调用 |
| 确认目标 | 否 | 无 confirm 按钮或 POST .../confirm 调用 |
| 生成 plan version | 否 | 无 POST .../plan-versions 调用 |
| 确认 plan version | 否 | 无 POST .../plan-versions/{id}/confirm 调用 |
| 创建任务 | 否 | 无 POST .../create-tasks 调用 |
| 调用 Worker | 否 | 无 worker dispatch API 调用 |

**结论：DirectorChatEntry 仅实现 POST session + 展示返回结果，未超范围 ✓**

前端描述文字明确声明范围："当前 R1 仅接入目标提交与澄清问题读取"（line 73）、"Ctrl/⌘ + Enter 发送；当前只会创建会话并读取澄清问题"（line 198）。

### 5.3 项目上下文展示

DirectorChatEntry 在顶部展示项目上下文 badge（line 75-77）：
```html
<span>项目上下文：{selectedProjectName}</span>
```

底部展示 `project_id` 或 "全局项目上下文"（line 198）。

**结论：聊天框可访问项目上下文 ✓ (WB-09)**

---

## 6. 映射验收项结论

| 验收项 | 状态 | 说明 |
|---|---|---|
| CL-01 | Evidence Partial | POST 创建 session 并持久化 goal_text；GET readback 一致；但前端仅展示，无独立"目标记录"持久化存储确认（此处 backend session 即目标记录） |
| CL-02 | Runtime Pass | 后端返回 clarifying_questions（5 items）；前端渲染 Q1~Q5 列表含必答标记/hint；contract fields（next_action, forbidden_actions, gate_conclusion）均正确展示 |
| WB-09 | Runtime Pass | selectedProjectId 传入 DirectorChatEntry；顶部展示 project context badge；selectedProjectId === "all" 时映射为 null |

---

## 7. Gate 结论

### 7.1 R1-A 阶段 Gate

| Gate 项 | 结论 | 证据 |
|---|---|---|
| 前端 Build 通过 | Pass | `npm.cmd run build` → built in 3.49s |
| 后端测试通过 | Pass | 38 passed |
| Live HTTP POST session | Pass | 201 Created, 返回完整字段 |
| Live HTTP GET readback | Pass | 200 OK, goal_text 和 clarifying_questions 一致 |
| selectedProjectId 传递 | Pass | "all" → null，其他 → 原值 |
| 未实现超范围动作 | Pass | 无 answer/confirm/plan/task/worker 调用 |
| 前端未回答澄清问题 | N/A (R1 边界内) | R1 边界明确禁止 |
| 前端未确认目标 | N/A (R1 边界内) | R1 边界明确禁止 |

**R1-A Gate：Runtime Pass**

### 7.2 AI Project Director Total Closure

**仍为 Partial**

原因：
- CL-03~CL-18 尚未完成
- 计划生成、任务创建、Worker 调度、运行证据、交付物、审批、仓库闭环、治理沉淀、成本台账均未接入
- 当前仅为 R1-A 最小前端接入验证

---

## 8. 未解决问题

- 前端前端展示的 Chinese 字符在 Windows 控制台输出时存在编码问题（终端显示乱码），但 API JSON 响应中的 UTF-8 数据完整且 GET readback 一致性已验证。不影响实际功能。

---

## 9. 文档修改清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `docs/product/ai-project-director/verification-project-director-workbench-session-entry-r1a-20260528.md` | 新增 | 本 evidence 文档 |
| `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md` | 追加 | 工作台 R1-A 记录；CL-01/CL-02/WB-09 状态更新 |

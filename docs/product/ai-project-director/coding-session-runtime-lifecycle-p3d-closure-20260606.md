# Coding Session Runtime Lifecycle P3-D Event / Audit 阶段收口

> **文档类型**: P3-D 阶段收口审计
> **生成日期**: 2026-06-06
> **基准 commit**: `48c178f`
> **参考项目**: ComposioHQ Agent Orchestrator (`c3eeecb`)
> **前置文档**:
> - `.kkr/skills/ai-project-director-command-governance/SKILL.md`
> - `docs/product/ai-project-director/coding-session-runtime-lifecycle-p3-closure-20260606.md`
> - `docs/product/ai-project-director/coding-session-runtime-lifecycle-p3d-event-audit-design-20260606.md`
> - `docs/product/ai-project-director/coding-session-runtime-lifecycle-p3a-design-20260605.md`
> **边界**: 收口审计，不改代码，不新增功能
> **状态**: P3-D Runtime Lifecycle Event / Audit: Pass；AI Project Director 总闭环 Partial

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator 后端

| 文件 | 用途 |
|------|------|
| `runtime/orchestrator/app/domain/runtime_event.py` | P3-D2 RuntimeEventSchema + RuntimeEventBuilder — gate-only 事件域模型 |
| `runtime/orchestrator/app/services/runtime_event_audit_service.py` | P3-D3 RuntimeEventAuditService — 门禁事件写入 AgentMessage |
| `runtime/orchestrator/app/workers/task_worker.py` | Worker 主链中调用 RuntimeEventAuditService 和 gate 审计 |
| `runtime/orchestrator/tests/test_runtime_event_builder.py` | P3-D2 7 builder tests |
| `runtime/orchestrator/tests/test_runtime_event_audit_service.py` | P3-D3 3 audit service tests (SQLite) |
| `runtime/orchestrator/tests/test_worker_workspace_readonly_validation.py` | P2/P3 regression baseline (18 tests) |

### AI-Dev-Orchestrator 前端

| 文件 | 用途 |
|------|------|
| `apps/web/src/features/agents/components/AgentRuntimeGateEventPanel.tsx` | P3-D4 运行时门禁事件面板 — 只读筛选 + 中文化 + 兜底提示 |
| `apps/web/src/features/agents/components/AgentThreadControlGrid.tsx` | 左侧栏组合 — 新增 AgentRuntimeGateEventPanel |

### Agent Orchestrator 参考

| 文件 | 参考要点 |
|------|---------|
| `packages/core/src/types.ts` | session/runtime 分轴、RuntimeHandle 身份标识、ActivitySignal |
| `packages/core/src/session-manager.ts` | recordActivityEvent() 审计模式、CleanupStack |
| `packages/core/src/lifecycle-manager.ts` | 状态探测与事件分离、reaction engine |
| `packages/core/src/lifecycle-state.ts` | CanonicalSessionLifecycle 三元组推导 |
| `packages/core/src/cleanup-stack.ts` | LIFO undo、失败时保留审计线索 |

---

## A. P3-D 阶段目标

P3-D 的目标是 **Runtime Lifecycle Event / Audit 的只读审计闭环**。在 P3-B（gate chain 计算）和 P3-C（AgentSession snapshot）的基础上，P3-D 将 gate 评估结果固化为不可修改的 AgentMessage 时间线事件，并提供前端只读展示。

P3-D 的完整范围：

1. **定义事件域模型**（P3-D2）— `RuntimeEventSchema`、`RuntimeEventBuilder`、14 种事件枚举
2. **实现审计服务**（P3-D3）— `RuntimeEventAuditService` 将门禁事件写入 AgentMessage timeline
3. **前端只读展示**（P3-D4）— `AgentRuntimeGateEventPanel` 从 timeline 筛选并展示门禁事件

**P3-D 只处理两类事件**：
- `runtime_launch_gate_evaluated` — 门禁全部通过
- `runtime_launch_gate_blocked` — 门禁被阻断

其他 12 种真实 runtime / probe / kill / cleanup 事件仍在事件枚举中定义，但被 builder 明确拒绝构造。

---

## B. 当前结论

| 能力 | 结论 | 说明 |
|------|------|------|
| P3-D Runtime Lifecycle Event / Audit | **Pass** | D2 域模型 + D3 审计服务 + D4 前端展示全部完成 |
| RuntimeEventSchema + Builder | **Pass** | 14 种事件枚举定义完成，gate-only builder gate 通过 7 tests |
| RuntimeEventBuilder gate-only 限制 | **Pass** | 非 gate 事件构造时抛出 ValueError + "Not started" |
| AgentMessage timeline 写入 gate event | **Pass** | `RuntimeEventAuditService` 写入 `SYSTEM/TIMELINE` 消息，3 SQLite tests |
| 审计失败不得继续 executor | **Pass** | `RuntimeEventAuditService` 写入异常会阻断 executor 调用链 |
| 前端 timeline 只读展示 gate event | **Pass** | `AgentRuntimeGateEventPanel` 只读筛选 + `AgentThreadControlGrid` 左侧栏集成 |
| 用户可见中文化和兜底展示 | **Pass** | 门禁中文化、运行时类型/适配器中文化、详情缺失/非法 JSON 提示 |
| **真实 runtime 启动** | **Not started** | 无 subprocess/tmux/docker 真实进程 |
| **Runtime probe** | **Not started** | 无进程探活 |
| **AI 自动编码** | **Not started** | Agent 未进入 worktree |
| **Git add / commit / push / PR** | **Not started** | Delivery Axis 全部未实现 |
| **AI Project Director 总闭环** | **Partial** | P1/P2/P3 全部 Pass，但 Runtime/Delivery 真实闭环 + Conversation Hub 未建设 |

---

## C. P3-D2 完成内容

### 新增 runtime_event.py

文件：`runtime/orchestrator/app/domain/runtime_event.py`（569 行）

核心结构：

| 组件 | 说明 |
|------|------|
| `RuntimeEventType` | 14 个枚举值，覆盖从门禁到清理的完整生命周期 |
| `RuntimeEventState` | 6 个状态（unknown/spawning/alive/exited/missing/probe_failed） |
| `RuntimeEventSafetyFlags` | 9 个安全开关，默认全部 `False` |
| `RuntimeEventSchema` | Pydantic 域模型，17 个字段 + `to_content_detail_json()` 序列化 |
| `RuntimeEventBuilder` | 工厂类，提供 `from_gate_result()` 和 `build()` 两个构造入口 |

### 当前只允许构造两类事件

`P3D2_BUILDABLE_RUNTIME_EVENT_TYPES` 只包含：

```
runtime_launch_gate_evaluated
runtime_launch_gate_blocked
```

其他 12 个事件类型（`runtime_launch_requested`、`runtime_spawning`、`runtime_handle_bound`、`runtime_alive_observed`、`runtime_exited`、`runtime_missing`、`runtime_probe_failed`、`runtime_kill_requested`、`runtime_killed`、`runtime_cleanup_started`、`runtime_cleanup_failed`、`runtime_cleanup_succeeded`）在 `RuntimeEventBuilder.build()` 中被明确拒绝，报错信息包含 `"Not started"`。

### safety_flags 默认全部 false

9 个安全开关在 `RuntimeEventSafetyFlags` 中全部默认为 `False`：

```
execution_enabled=False
launches_ai_runtime=False
runs_real_command=False
runs_git=False
runs_write_git=False
changes_process_cwd=False
fake_launch_started=False
real_runtime_started=False
runtime_probe_started=False
```

### content_detail JSON 合同已建立

统一 JSON 结构包含 `schema_version`、`event_id`、`event_type`、`session_id`、`project_id`、`task_id`、`run_id`、`runtime_handle_id`、`previous_runtime_state`、`next_runtime_state`、`reason_code`、`summary_cn`、`technical_detail`、`safety_flags`、`evidence`、`created_by` 字段。序列化方法包含 3 级截断策略，确保不超过 `AgentMessage.content_detail` 的 4000 字符限制。

### summary_cn 必须中文

所有 `summary_cn` 字段强制使用中文文案。例如：

- 门禁通过：`"运行时启动门禁已全部通过。共检查 5 道条件……门禁通过只表示前置条件满足，运行时尚未启动。"`
- 门禁阻断：`"运行时启动门禁已阻断。第 4 道条件（工作区安全命令证明）未通过……门禁阻断是受控安全行为，不是系统崩溃。"`

---

## D. P3-D3 完成内容

### 新增 RuntimeEventAuditService

文件：`runtime/orchestrator/app/services/runtime_event_audit_service.py`（91 行）

唯一公开方法 `record_launch_gate_event()`：
- 接收 `AgentSession` + `gate_result` + 上下文参数
- 调用 `RuntimeEventBuilder.from_gate_result()` 构造事件
- 调用 `_append_runtime_event_message()` 写入 AgentMessage

### AgentMessage 字段映射

| AgentMessage 字段 | 填充值 |
|-------------------|--------|
| `role` | `SYSTEM` |
| `message_type` | `TIMELINE` |
| `event_type` | `runtime_launch_gate_evaluated` 或 `runtime_launch_gate_blocked` |
| `phase` | `AgentSession.current_phase` 的值 |
| `state_from` | `"unknown"` |
| `state_to` | `"unknown"` |
| `intervention_type` | `None` |
| `note_event_type` | `None` |
| `content_summary` | `event.summary_cn`（中文） |
| `content_detail` | `event.to_content_detail_json()`（P3-D JSON 合同） |

### TaskWorker 真实构造路径已注入

在 `TaskWorker.run_once()` 中（约 L1650），gate 结果计算完成后，调用 `RuntimeEventAuditService.record_launch_gate_event()` 写入 AgentMessage。该调用在 workspace validation 和 safe command proof 之后、executor 调用之前执行。

### 审计写入失败会在 executor 前中断

`record_launch_gate_event()` 的任何异常（包括 `AgentMessageRepository.create()` 失败）都会向上传播，在 Worker 中被 `except Exception` 捕获，触发 session rollback，阻止 executor 继续执行。这保证了 "无审计则无执行" 的安全契约。

### 不写非 gate event

`RuntimeEventAuditService` 当前只有一个方法（`record_launch_gate_event`），不存在写入其他 12 种 runtime 事件的代码路径。

---

## E. P3-D4 完成内容

### 新增前端 AgentRuntimeGateEventPanel

文件：`apps/web/src/features/agents/components/AgentRuntimeGateEventPanel.tsx`（377 行）

已集成到 `AgentThreadControlGrid` 左侧栏，位于 `AgentWorkspaceLifecycleAuditPanel` 和 `BossInterventionForm` 之间。

### 只读筛选机制

`isRuntimeGateEvent()` 函数只筛选 `event_type` 在 `RUNTIME_GATE_EVENT_LABELS` 中的消息，即只筛选两种事件：

```
runtime_launch_gate_evaluated → "运行时启动门禁已通过"
runtime_launch_gate_blocked  → "运行时启动门禁已阻断"
```

### 前端中文展示

| 英文原始值 | 中文展示 |
|-----------|---------|
| `runtime_launch_gate_evaluated` | 运行时启动门禁已通过 |
| `runtime_launch_gate_blocked` | 运行时启动门禁已阻断 |
| `workspace_validation` | G1 工作区状态校验 |
| `workspace_context` | G2 工作区上下文校验 |
| `runtime_dry_run` | G3 运行时参数预览 |
| `safe_command_proof` | G4 工作区路径安全证明 |
| `adapter_capability` | G5 适配器能力检查 |
| `subprocess` | 子进程运行方式 |
| `openai_provider` | OpenAI 提供方 |
| `fake`（运行时类型） | 模拟运行方式 |
| `fake`（适配器） | 模拟适配器 |
| `true` / `false` | 是 / 否 |
| 未知运行时类型 | 未知运行方式（title 保留原始值） |
| 未知适配器 | 未知适配器（title 保留原始值） |

### 兜底提示

- `content_detail` 为空 → "事件详情未记录。"
- `content_detail` 非法 JSON → "事件详情无法解析。"
- 提示使用琥珀色背景，不崩页面，仍展示 `content_summary`

### 禁止误导文案

面板和所有 badge 中不出现：
- Runtime 已启动
- AI 正在编码
- 进程运行中
- Claude/Codex 已连接
- PR 已准备

始终展示 "证据只读，未启动运行时" 作为安全提醒。

---

## F. 当前形成的事件链路

从 Worker 执行到前端展示的完整 P3-D 事件链路：

```
1. Worker workspace validation (P2-B)
   ↓
2. Worker workspace context resolution (P2-B-R1)
   ↓
3. Runtime launch dry-run preview (P2-C)
   ↓
4. Worktree safe command proof — pwd (P2-D)
   ↓
5. check_runtime_launch_gates() — G1~G5 评估 (P3-B)
   ↓
6. RuntimeEventBuilder.from_gate_result() — 构造事件 (P3-D2)
   ↓
7. RuntimeEventAuditService.record_launch_gate_event() — 写入 AgentMessage (P3-D3)
   ↓
8. gate failed → executor 硬阻断 (P3-B2-R1)
   gate passed → 本阶段仍然不启动 runtime (P3 安全边界)
   ↓
9. 前端 AgentRuntimeGateEventPanel 从 timeline 只读展示 (P3-D4)
```

步骤 6–9 是 P3-D 新增的闭环。

---

## G. 安全边界

P3-D 阶段全部安全开关的当前状态：

| 安全开关 | 当前值 | 位置 |
|---------|--------|------|
| `execution_enabled` | **false** | `RuntimeEventSafetyFlags` + `RuntimeLaunchGateResult` |
| `launches_ai_runtime` | **false** | `RuntimeEventSafetyFlags` + `RuntimeLaunchGateResult` |
| `runs_real_command` | **false** | `RuntimeEventSafetyFlags` + `RuntimeLaunchGateResult` |
| `runs_git` | **false** | `RuntimeEventSafetyFlags` + `RuntimeLaunchGateResult` |
| `runs_write_git` | **false** | `RuntimeEventSafetyFlags` + `RuntimeLaunchGateResult` |
| `changes_process_cwd` | **false** | `RuntimeEventSafetyFlags` + `RuntimeLaunchGateResult` |
| `fake_launch_started` | **false** | `RuntimeEventSafetyFlags` + `AgentSessionRuntimeLifecycleSnapshot` |
| `real_runtime_started` | **false** | `RuntimeEventSafetyFlags` + `AgentSessionRuntimeLifecycleSnapshot` |
| `runtime_probe_started` | **false** | `RuntimeEventSafetyFlags` + `AgentSessionRuntimeLifecycleSnapshot` |

额外禁区：
- 不启动 Claude / Codex / DeepSeek / OpenCode
- 不让 AI runtime 进入 worktree
- 不创建 PR
- 不提交业务代码变更
- 不创建 / 删除 worktree
- 不创建 / 删除 branch

---

## H. Event / Evidence / Snapshot 的关系

P3-D 收口时必须澄清三者关系：

| 概念 | 是什么 | 存储位置 | 生命周期 | 示例 |
|------|--------|---------|---------|------|
| **Runtime Launch Gate Evidence**（P3-B2） | 单次 Worker 响应中的门禁评估结果 | `WorkerRunResult` 字段（内存，不持久化） | 一次 Worker 周期 | `runtime_launch_gate_ready = false` |
| **Runtime Lifecycle Event**（P3-D） | 可回放的历史审计事件 | `AgentMessage` 表（SQLite 持久化） | 永久（追加写入，不可修改） | `event_type = "runtime_launch_gate_blocked"` |
| **AgentSession Runtime Lifecycle Snapshot**（P3-C1） | 从 AgentSession 字段派生的当前状态快照 | 不存储（每次读取时重新计算） | 每次读取 | `runtime_lifecycle_state = "unknown"` |

**三者不能混用**：
- Evidence 是瞬态的——Worker 结束后就消失
- Event 是历史的——一旦写入不可修改
- Snapshot 是派生的——从 AgentSession 字段 + 最新 event 计算

**P3-D 只做了**：把 gate evidence 固化为 timeline event。这个 event 可以被未来快照派生逻辑读取（例如 "因为看到了 `runtime_launch_gate_blocked` event，所以 snapshot 的 runtime state 不是 unknown 而是 blocked-pre-launch"），但那样的派生逻辑属于 P3-E 或后续阶段。

---

## I. 用户可见文案规范

### 核心原则

1. 用户界面必须使用简单中文
2. 不直接展示英文枚举（`unknown`、`probe_failed`、`runtime_type_missing`）
3. 不直接展示 `true` / `false`（使用 "是" / "否" / "未记录"）
4. 不直接展示 gate key（`workspace_validation`、`safe_command_proof`）
5. 所有能力提示必须如实反映当前状态

### 关键文案的正确与错误示例

| 场景 | 错误文案 | 正确文案 |
|------|---------|---------|
| 门禁通过 | "运行时就绪" | "运行时启动门禁已全部通过。门禁通过只表示前置条件满足，运行时尚未启动。" |
| 门禁阻断 | "启动失败" | "运行时启动门禁已阻断。门禁阻断是受控安全行为，不是系统崩溃。" |
| 安全证明未通过 | "pwd failed" | "当前目录证明与工作区路径不一致" |
| 适配器不可用 | "adapter unavailable" | "运行时适配器不可用" |
| 运行时类型缺失 | "runtime_type_missing" | "运行时类型缺失" |
| 安全标记 | "true" / "false" | "是" / "否" |

### 禁止使用的误导文案

以下文案在对应能力未实现前严禁出现在任何前端页面：

- "AI 正在编码"
- "Runtime 已启动"
- "Claude/Codex 已连接"
- "进程运行中"
- "PR 已准备"
- "自动提交已完成"

---

## J. 参考 Agent Orchestrator 的机制

### 参考了的机制

| AO 机制 | 学习要点 | P3-D 对应实现 |
|---------|---------|-------------|
| **session/runtime 分轴** | `CanonicalSessionLifecycle` 将 runtime state 独立于 session state 记录 | `RuntimeEventType` 14 种事件独立于 session/execution event |
| **lifecycle manager 状态与事件分离** | `determineStatus()` 收集数据 → 推导状态 → emit event | `check_runtime_launch_gates()` 收集 5 道门禁 → gate result → `RuntimeEventAuditService.record_launch_gate_event()` |
| **activity / audit event** | `recordActivityEvent()` 将结构化事件追加到审计流 | `_append_runtime_event_message()` 复用 `AgentMessageRepository.create()` 写入 timeline |
| **runtime handle 身份标识** | `RuntimeHandle` 是 `{id, runtimeName, data}`，不等于 alive | `runtime_handle_id` 在事件中固定为 `null`（P3 阶段没有真实 runtime 可以绑定） |
| **cleanup/rollback 失败保留审计线索** | CleanupStack.runAll() swallow error 但提供 `onError` 回调记录 | 审计写入失败会向上传播 → Worker 捕获 → session rollback → failure review |

### 没有照搬的内容

| AO 内容 | 为什么不照搬 |
|---------|------------|
| 插件架构 | AI-Dev 不需要完整插件系统 |
| Node.js / TypeScript 技术栈 | AI-Dev 使用 Python + FastAPI + SQLite |
| tmux 默认 runtime | P3 阶段不做真实 runtime |
| LifecycleManager 轮询循环 | P3 阶段无真实进程可轮询 |
| ActivitySignal (native/terminal/hook) | P3 阶段不做 runtime probe |
| SCM integration (PR/CI/review) | Delivery Axis 属于 P4+ |
| CLI / Next.js dashboard | AI-Dev 是 web-first API 应用 |

---

## K. 仍然没有开始的能力

| # | 能力 | 说明 |
|---|------|------|
| 1 | `runtime_launch_requested` 真实事件写入 | 未实现（P3-D2 枚举有定义，builder 拒绝构造） |
| 2 | `runtime_spawning` 事件 | 未实现 |
| 3 | `runtime_handle_bound` 事件 | 未实现 |
| 4 | `runtime_alive_observed` 事件 | 未实现 |
| 5 | `runtime_exited` 真实回写 | 未实现 |
| 6 | `runtime_missing` 事件 | 未实现 |
| 7 | `runtime_probe_failed` 事件 | 未实现 |
| 8 | `runtime_kill_requested` / `runtime_killed` 事件 | 未实现 |
| 9 | `runtime_cleanup_*` 真实事件 | 未实现 |
| 10 | 真实 subprocess adapter | `FakeRuntimeAdapter` 仍是唯一适配器 |
| 11 | 真实 tmux / docker adapter | 未实现 |
| 12 | AI 自动编码 | Agent 未进入 worktree 自主编码 |
| 13 | git add / commit / push | Delivery Axis 未实现 |
| 14 | PR 创建与审核 | 无 SCM 集成 |
| 15 | CI / review / merge loop | 未实现 |
| 16 | Project Director Conversation Hub | 未建设 |

---

## L. 下一阶段建议

| 阶段 | 目标 | 说明 |
|------|------|------|
| **P3-E** | Fake runtime lifecycle simulation 前后端闭环展示 | 将 P3-B 的 gate evidence、P3-C 的 snapshot、P3-D 的 timeline event 合并为统一的 Runtime Lifecycle 总览面板 |
| **P3-F** | 真实 runtime 启动前 guardrail + feature flag | 定义 `execution_enabled` 翻转的显式条件、审计要求和安全契约 |
| **P3-G** | Runtime probe 设计，不直接启用 | 设计 `RuntimeAdapter.is_alive()` 的调用时机、重试策略、状态回写路径 |
| **P4** | Git add / commit / push / PR 产品闭环设计 | Delivery Axis 状态机、SCM 集成 |
| **Conversation Hub** | AI Project Director 对话中枢 | 从 gap analysis 的 P7 路线切入 |

---

## Gate 结论

| Gate | 结论 |
|------|------|
| P3-D Runtime Lifecycle Event / Audit | **Pass** |
| P3-D2 RuntimeEventSchema + Builder | **Pass** |
| P3-D3 AgentMessage 写入 gate event | **Pass** |
| P3-D4 前端只读展示 gate event | **Pass** |
| P3-E Fake runtime lifecycle simulation | **Not started** |
| P3-F 真实 runtime guardrail | **Not started** |
| 真实 runtime 启动 | **Not started** |
| Runtime probe | **Not started** |
| AI 自动编码 | **Not started** |
| Git add / commit / push / PR | **Not started** |
| **AI Project Director 总闭环** | **Partial** |

## 附录: P3-D 提交历史

| Commit | 说明 |
|--------|------|
| `5d19fff` | feat: record P3-D3 runtime gate events |
| `6f37d09` | fix: align P3-D3 runtime gate event timeline mapping |
| `cc8a5d6` | test: guard runtime gate audit failure before executor |
| `0023aa4` | feat: display P3-D4 runtime gate events |
| `15c18ca` | fix: localize P3-D4 runtime gate timeline copy |
| `48c178f` | fix: harden P3-D4 runtime gate event display fallback |

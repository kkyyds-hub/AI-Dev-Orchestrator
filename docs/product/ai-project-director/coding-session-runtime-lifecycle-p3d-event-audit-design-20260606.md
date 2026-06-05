# Coding Session Runtime Lifecycle P3-D Event / Audit 只读事件落点设计

> **文档类型**: P3-D 设计文档（只做事件审计合同设计，不改业务代码）
> **生成日期**: 2026-06-06
> **基准 commit**: `ff58d55`
> **参考项目**: ComposioHQ Agent Orchestrator (`c3eeecb`)
> **前置文档**:
> - `.kkr/skills/ai-project-director-command-governance/SKILL.md`
> - `docs/product/ai-project-director/coding-session-runtime-lifecycle-p3-closure-20260606.md`
> - `docs/product/ai-project-director/coding-session-runtime-lifecycle-p3a-design-20260605.md`
> **边界**: 纯设计文档，不改 Python 代码、不改前端、不启动服务、不启动 runtime、不做 runtime probe
> **状态**: P3-D Event / Audit Design: Design only；真实 runtime 启动: Not started

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator

| 文件 | 用途 |
|------|------|
| `.kkr/skills/ai-project-director-command-governance/SKILL.md` | 指令治理规范 |
| `docs/product/ai-project-director/coding-session-runtime-lifecycle-p3-closure-20260606.md` | P3 收口文档——当前能力基线 |
| `docs/product/ai-project-director/coding-session-runtime-lifecycle-p3a-design-20260605.md` | P3-A 设计——生命周期状态机、门禁链、event/audit 初步方向 |
| `runtime/orchestrator/app/domain/agent_message.py` | AgentMessage 域模型——`event_type`、`content_summary`、`content_detail` 现有字段 |
| `runtime/orchestrator/app/repositories/agent_message_repository.py` | AgentMessageRepository——`create()` + `list_by_session_id()` |
| `runtime/orchestrator/app/services/agent_conversation_service.py` | AgentConversationService——`_append_message()` 模式、现有 event 类型 |
| `runtime/orchestrator/app/domain/runtime_lifecycle.py` | AgentSessionRuntimeLifecycleSnapshot——P3-C1 双轴派生 |
| `runtime/orchestrator/app/workers/runtime_adapter.py` | RuntimeAdapter contract + RuntimeLifecycleState/Reason 枚举 |
| `runtime/orchestrator/app/workers/task_worker.py` | WorkerRunResult P3 evidence 字段 |
| `runtime/orchestrator/app/api/routes/agent_threads.py` | AgentSessionResponse + AgentMessageResponse API DTO |
| `apps/web/src/features/agents/types.ts` | 前端 AgentSessionSnapshot + AgentTimelineMessage 类型 |
| `apps/web/src/features/agents/components/AgentWorkspaceLifecycleAuditPanel.tsx` | P2-A-R1 工作区生命周期审计面板（event 过滤模式参考） |
| `apps/web/src/features/agents/components/AgentCodingSessionSnapshot.tsx` | P3-C1 会话运行状态双轴卡片 |

### Agent Orchestrator 参考

| 文件 | 参考要点 |
|------|---------|
| `packages/core/src/types.ts` | `RuntimeStateRecord` + `CanonicalRuntimeState/Reason`、`ActivitySignal` |
| `packages/core/src/session-manager.ts` | `recordActivityEvent()` 审计写入模式、CleanupStack |
| `packages/core/src/lifecycle-manager.ts` | `determineStatus()` 状态探测→生命周状态推导→reaction 触发 |
| `packages/core/src/lifecycle-state.ts` | `CanonicalSessionLifecycle` 三元组解析、`deriveLegacyStatus()` |
| `packages/core/src/cleanup-stack.ts` | LIFO undo、失败时保留审计线索 |

---

## A. P3-D 目标

P3-D 是 **Runtime Lifecycle Event / Audit 的只读事件模型和落点方案设计**。它不实现任何代码，只为后续真实 runtime launch、probe、exited、missing、probe_failed 等事件提前定义审计合同。

P3-D 的具体目标：

1. **定义 Runtime Lifecycle Event 类型** — 14 种 event_type，覆盖从门禁评估到清理完成的完整生命周期
2. **定义 Event 与 Snapshot 的关系** — event 是历史事实，snapshot 是当前派生状态，两者不能混用
3. **定义事件落点方案** — AgentMessage（用户可读摘要）+ RunLog / detail JSON（技术证据）双通道
4. **定义 AgentMessage 字段映射** — 每种 event 如何填写 role、message_type、event_type、content_summary、content_detail
5. **定义 content_detail JSON 合同** — 统一的 JSON schema，确保所有 runtime event 的结构一致
6. **定义中文文案规范** — 用户界面不得展示英文枚举，不得使用误导性文案

P3-D 明确不做的事：

- 不修改任何 Python 代码
- 不修改任何前端代码
- 不启动 runtime
- 不做 runtime probe
- 不改变现有 Worker / AgentSession 行为
- 不在 AgentMessage 表中新增列
- 不新增数据库 migration

---

## B. 为什么需要 Runtime Lifecycle Event / Audit

### B.1 现有能力的局限

P3 当前已建立的三种证据形式各有局限：

| 证据形式 | 定位 | 局限 |
|---------|------|------|
| **WorkerRunResult evidence** (P3-B2) | 单次 Worker 响应中的证据字段 | 只反映一个 worker 周期内的状态；不持久化；无法回放历史 |
| **AgentSession Runtime Lifecycle Snapshot** (P3-C1) | 从 AgentSession 持久化字段派生的当前状态快照 | 只反映 "现在是什么"，不反映 "发生了什么变化"；runtime 轴永远是 `unknown` |
| **Runtime Launch Gate Result** (P3-B) | 门禁链的一次性评估结果 | 不在 AgentMessage timeline 中；前端只能通过 Worker 响应看到 |

### B.2 为什么需要事件

后续真实 runtime 启动后，系统需要回答以下问题：

- 什么时候做了门禁评估？门禁通过了吗？哪道门禁失败了？
- 什么时候请求了 runtime 启动？谁请求的？
- 运行时句柄是何时绑定的？
- 运行时的存活状态是什么时候确认的？后来又变了吗？
- 运行时为什么退出？是正常结束还是崩溃？
- 什么时候发现运行时丢失的？丢了以后系统做了什么？
- 有没有尝试过 kill？成功了吗？

这些问题只能通过 **事件时间线** 回答。单次 Worker 响应会被覆盖，snapshot 会把状态变化抹平，但事件是历史事实——它不可修改、可排序、可回放。

### B.3 事件 ≠ 证明能力已实现

P3-D 定义事件合同，**不代表这些事件的能力已经实现**。`runtime_launch_requested` 之后的所有真实事件（`runtime_spawning`、`runtime_alive_observed`、`runtime_exited`、`runtime_missing`、`runtime_probe_failed`、`runtime_kill_*`、`runtime_cleanup_*`）目前全部是 **Not started**。

---

## C. Event 与 Snapshot 的关系

这是 P3-D 最核心的设计原则，必须严格区分：

| | Event（事件） | Snapshot（快照） |
|---|-------------|----------------|
| **是什么** | 历史事实——"某时某刻发生了什么" | 当前派生状态——"现在是什么" |
| **是否可修改** | 不可修改（追加写入） | 可重新派生（每次读取时计算） |
| **存储位置** | AgentMessage 表、RunLog 文件 | 不存储（从 AgentSession + latest event 派生） |
| **示例** | "2026-06-06 14:30: G4 safe_command_proof 阻断门禁" | "当前 runtime_lifecycle_state = unknown, reason = handle_recorded_no_probe" |
| **用户价值** | 回答 "什么时候、发生了什么、为什么" | 回答 "现在是什么状态" |
| **时效性** | 历史事实，永远有效 | 只在读取时刻有效 |

### C.1 推导关系

Snapshot 可以由最新 event + AgentSession 字段派生，但 P3-D 只设计 event 合同，不设计派生逻辑。派生逻辑属于 P3-E 或后续阶段。

```
AgentSession 持久化字段
        +
最新 runtime event (from AgentMessage)
        │
        ▼
    Snapshot 派生 (P3-E 或后续)
```

### C.2 当前 P3-C1 snapshot 为什么 runtime 轴永远是 unknown

因为没有任何 runtime event 被写入 AgentMessage。P3-C1 只能看 `runtime_handle_id` 是否有值——有值就意味着 "曾经记录过一个句柄，但没有事件证明它活过"。

---

## D. 建议的 Runtime Lifecycle Event 类型

以下 14 种 event_type 覆盖了从门禁评估到清理完成的完整生命周期。所有 event_type 使用 `runtime_` 前缀，与现有的 `session_`、`execution_`、`workspace.` 前缀形成清晰的命名空间。

### D.1 Event 一览

| # | event_type | 含义 | 当前状态 |
|---|-----------|------|---------|
| 1 | `runtime_launch_gate_evaluated` | 运行时启动门禁已评估（五道门禁全部评估完毕） | **可立即实现**（P3-B 已有 gate result） |
| 2 | `runtime_launch_gate_blocked` | 运行时启动门禁已阻断（至少一道门禁失败） | **可立即实现**（P3-B 已有 gate result） |
| 3 | `runtime_launch_requested` | 运行时启动已被请求（门禁通过后，调用 adapter.launch() 之前） | Not started |
| 4 | `runtime_spawning` | 运行时正在启动（adapter.launch() 已调用，等待首次探活） | Not started |
| 5 | `runtime_handle_bound` | 运行时句柄已绑定到 AgentSession | Not started |
| 6 | `runtime_alive_observed` | 运行时已确认存活（probe 返回 alive） | Not started |
| 7 | `runtime_exited` | 运行时已退出（进程正常或异常结束） | Not started |
| 8 | `runtime_missing` | 运行时句柄丢失（进程意外消失，exit code 未知） | Not started |
| 9 | `runtime_probe_failed` | 运行时探测失败（无法确认进程状态） | Not started |
| 10 | `runtime_kill_requested` | 运行时终止已被请求 | Not started |
| 11 | `runtime_killed` | 运行时已被终止（adapter.kill() 已完成） | Not started |
| 12 | `runtime_cleanup_started` | 运行时清理已开始 | Not started |
| 13 | `runtime_cleanup_failed` | 运行时清理失败 | Not started |
| 14 | `runtime_cleanup_succeeded` | 运行时清理成功 | Not started |

### D.2 Event 1–2: 门禁事件

这两个事件是当前唯一可以在 P3-D 后续子阶段（P3-D3）立即实现的，因为 P3-B 已经产生了完整的 gate result 数据。

- `runtime_launch_gate_evaluated`: 门禁全通过时写入
- `runtime_launch_gate_blocked`: 门禁不通过时写入

其他 12 个事件全部依赖真实 runtime launch / probe / exit / kill / cleanup——这些能力在 P3 阶段全部是 Not started。

### D.3 Event 的相互顺序

事件在时间线上是有序的。正常流程下的期望顺序：

```
runtime_launch_gate_evaluated (门禁通过)
  → runtime_launch_requested
    → runtime_spawning
      → runtime_handle_bound
        → runtime_alive_observed
          → ... (正常工作期) ...
            → runtime_exited (正常退出)
              → runtime_cleanup_started
                → runtime_cleanup_succeeded
```

异常路径示例：

```
runtime_launch_gate_blocked (门禁阻断) — 流程终止，不继续

runtime_launch_gate_evaluated → runtime_launch_requested
  → runtime_spawning → runtime_probe_failed → runtime_probe_failed
    → runtime_probe_failed (第 3 次) → runtime_missing (升级)

runtime_alive_observed → runtime_missing (意外丢失)

runtime_alive_observed → runtime_kill_requested
  → runtime_killed → runtime_exited

runtime_cleanup_started → runtime_cleanup_failed (清理失败，保留审计线索)
```

---

## E. Event 落点建议

### E.1 方案对比

| 维度 | AgentMessage | RunLog (JSONL 文件) |
|------|------------|---------------------|
| **存储位置** | `agent_messages` 表（SQLite） | `runs/{task_id}/{run_id}.jsonl` 文件 |
| **关联能力** | 天然关联 session/project/task/run（FK 字段） | 通过路径关联 run_id |
| **适合内容** | 用户可读摘要（中文） | 详细技术证据（JSON） |
| **前端展示** | `AgentTimelineList` 直接读取并展示 | 需要额外 API 或 log viewer |
| **内容大小限制** | `content_summary` ≤ 2000 字符，`content_detail` ≤ 4000 字符 | 无硬限制，但应保持合理 |
| **查询能力** | 可按 session_id、event_type、message_type 过滤 | 需要逐行解析 JSONL |
| **持久性** | 数据库事务保证 | 文件系统，不保证事务一致性 |

### E.2 推荐方案：双通道

P3-D 推荐采用 **AgentMessage + RunLog 双通道**：

- **AgentMessage**: 记录用户可读摘要。`content_summary` 用中文写 "发生了什么"（例如 "运行时启动门禁已阻断：安全命令证明未通过，pwd 输出与工作区路径不一致"）。`content_detail` 存储精简版 JSON（核心字段，不超过 4000 字符限制）。
- **RunLog**: 记录完整技术证据。`content_detail` 中的 JSON 可在此处完整展开，包括所有 gate/safety flag/probe 的原始数据。

两者通过以下字段关联：
- `session_id`
- `run_id`
- `runtime_handle_id`（在 content_detail JSON 中）
- `event_type`

### E.3 为什么不用新表

当前不新增专门的 `runtime_lifecycle_event` 表，原因：
1. `AgentMessage` 已经支持 session/project/task/run FK 链和按 `event_type` 过滤
2. `AgentMessage` 已经有 `role = SYSTEM` + `message_type = TIMELINE` 的写入模式（参考 `session_started`、`execution_started`、`session_finalized`）
3. 新建专用表会增加 migration 和维护成本，而当前 runtime 事件数量还未膨胀到需要单独建模的程度
4. 后续如果 runtime event 数据量和查询模式变化，可以在此设计基础上新增专用模型——不影响 AgentMessage 已有的 event 数据

---

## F. AgentMessage 字段映射建议

### F.1 现有 field 复用

所有 runtime lifecycle event 写入 `AgentMessage` 时使用统一的字段映射规则：

| AgentMessage 字段 | 对于 runtime event 的填写规则 |
|-------------------|---------------------------|
| `role` | 固定 `SYSTEM`（系统自动产生的事件） |
| `message_type` | 固定 `TIMELINE`（时间线事件，非 review/rework/intervention） |
| `event_type` | `runtime_*` 格式（如 `runtime_launch_gate_blocked`） |
| `phase` | 当前 `AgentSession.current_phase` 的值（如 `executing`） |
| `state_from` | runtime 变化前的 `RuntimeLifecycleState`（如 `unknown`） |
| `state_to` | runtime 变化后的 `RuntimeLifecycleState`（如 `spawning`） |
| `intervention_type` | 固定 `None`（runtime event 不是 intervention） |
| `note_event_type` | 固定 `None`（保留给 boss note-event 使用，不混用） |
| `context_checkpoint_id` | 当前 `AgentSession.context_checkpoint_id` |
| `context_rehydrated` | 当前 `AgentSession.context_rehydrated` |
| `content_summary` | 中文一句话摘要（见 H 节文案规范） |
| `content_detail` | JSON 字符串（见 G 节 JSON 合同） |

### F.2 示例：门禁全通过事件

```
role = SYSTEM
message_type = TIMELINE
event_type = "runtime_launch_gate_evaluated"
phase = "executing"
state_from = "unknown"
state_to = "unknown"              # 门禁通过不等于 runtime 已启动
content_summary = "运行时启动门禁已全部通过：G1 工作区校验、G2 工作区上下文、G3 运行时预览、G4 安全命令证明、G5 适配器能力检查均通过。但这只表示前置条件就绪，运行时尚未启动。"
content_detail = {JSON 合同}
```

### F.3 示例：门禁阻断事件

```
role = SYSTEM
message_type = TIMELINE
event_type = "runtime_launch_gate_blocked"
phase = "executing"
state_from = "unknown"
state_to = "unknown"              # 门禁阻断，未到 spawning
content_summary = "运行时启动门禁已阻断：第 4 道门禁（工作区安全命令证明）未通过。pwd 输出路径与 AgentSession 工作区路径不一致。"
content_detail = {JSON 合同}
```

### F.4 示例：将来的运行时退出事件（当前 Not started）

```
role = SYSTEM
message_type = TIMELINE
event_type = "runtime_exited"
phase = "executing"
state_from = "alive"
state_to = "exited"
content_summary = "运行时进程已退出。退出码为 0，判定为正常退出。"
content_detail = {JSON 合同}
```

---

## G. content_detail JSON 合同

### G.1 统一 JSON Schema

所有 runtime lifecycle event 的 `content_detail` 使用统一的 JSON 结构。定义如下：

```json
{
  "schema_version": "1.0",
  "event_id": "<uuid>",
  "event_type": "runtime_launch_gate_blocked",
  "session_id": "<uuid>",
  "project_id": "<uuid>",
  "task_id": "<uuid>",
  "run_id": "<uuid>",
  "runtime_handle_id": null,
  "runtime_type": "subprocess",
  "agent_type": "openai_provider",
  "adapter_kind": "fake",
  "previous_runtime_state": "unknown",
  "next_runtime_state": "unknown",
  "reason_code": "pwd_mismatch_workspace_path",
  "summary_cn": "运行时启动门禁已阻断：第 4 道门禁（工作区安全命令证明）未通过。",
  "technical_detail": "observed_pwd='/unexpected/path' != expected_workspace_path='/tmp/aido-worktree'",
  "safety_flags": {
    "execution_enabled": false,
    "launches_ai_runtime": false,
    "runs_real_command": false,
    "runs_git": false,
    "runs_write_git": false,
    "changes_process_cwd": false,
    "fake_launch_started": false,
    "real_runtime_started": false,
    "runtime_probe_started": false
  },
  "evidence": {
    "gates_passed": ["workspace_validation", "workspace_context", "runtime_dry_run"],
    "gates_failed": ["safe_command_proof"],
    "blocking_reason_code": "pwd_mismatch_workspace_path",
    "blocking_summary": "Worker worktree safe command proof (pwd) failed.",
    "workspace_path": "/tmp/aido-worktree",
    "observed_pwd": "/unexpected/path",
    "pwd_matches_workspace_path": false
  },
  "created_by": "TaskWorker.run_once"
}
```

### G.2 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `schema_version` | string | 是 | JSON 结构版本，当前为 `"1.0"` |
| `event_id` | string | 是 | 事件唯一 ID（UUID），用于跨通道（AgentMessage ↔ RunLog）关联 |
| `event_type` | string | 是 | 与 `AgentMessage.event_type` 相同 |
| `session_id` | string | 是 | AgentSession ID |
| `project_id` | string | 是 | Project ID |
| `task_id` | string | 是 | Task ID |
| `run_id` | string | 是 | Run ID |
| `runtime_handle_id` | string \| null | 是 | 运行时句柄（如 `fake:pid:90001`），尚未绑定时为 null |
| `runtime_type` | string \| null | 否 | 运行时类型（`subprocess` / `tmux` / `docker`） |
| `agent_type` | string \| null | 否 | 智能体类型（`openai_provider` / `claude_code` 等） |
| `adapter_kind` | string \| null | 否 | 适配器标识（`fake` / `subprocess` / `tmux` / `docker`） |
| `previous_runtime_state` | string | 是 | 事件前的 `RuntimeLifecycleState` |
| `next_runtime_state` | string | 是 | 事件后的 `RuntimeLifecycleState` |
| `reason_code` | string \| null | 是 | 事件原因码（来自 `RuntimeLifecycleReason` 或 gate block reason） |
| `summary_cn` | string | 是 | 中文摘要（与 `content_summary` 可以不同，这里更偏技术） |
| `technical_detail` | string \| null | 否 | 补充技术细节 |
| `safety_flags` | object | 是 | 9 个安全开关状态（见 G.3） |
| `evidence` | object | 否 | 与事件相关的证据数据（见 G.4） |
| `created_by` | string | 是 | 事件产生者（如 `"TaskWorker.run_once"`、`"WorkerWorktreeSafeCommandProofRunner"`） |

### G.3 safety_flags 必需字段

```json
{
  "execution_enabled": false,
  "launches_ai_runtime": false,
  "runs_real_command": false,
  "runs_git": false,
  "runs_write_git": false,
  "changes_process_cwd": false,
  "fake_launch_started": false,
  "real_runtime_started": false,
  "runtime_probe_started": false
}
```

这 9 个字段在 P3 阶段全部为 `false`。当后续阶段逐步开启真实能力时，对应字段会翻转为 `true`——但每次翻转都必须有对应的 event 记录。

### G.4 evidence 子对象

`evidence` 是一个可扩展的 JSON 对象，根据 `event_type` 包含不同的证据数据：

- 对于 `runtime_launch_gate_*` 事件: 包含 gates_passed、gates_failed、blocking_reason_code、blocking_summary、workspace_path、observed_pwd、pwd_matches_workspace_path
- 对于 `runtime_launch_requested` 事件: 包含 launch_cwd_preview、agent_type、runtime_type、adapter_kind
- 对于 `runtime_alive_observed` 事件: 包含 probe_attempt、probe_method、handle_id
- 对于 `runtime_exited` 事件: 包含 exit_code
- 对于 `runtime_missing` 事件: 包含 probe_attempts、last_probe_error
- 对于 `runtime_probe_failed` 事件: 包含 probe_attempt、probe_error、probe_timeout

---

## H. 用户可见中文文案规范

### H.1 核心原则

1. 所有用户界面展示必须使用简单中文
2. 不得直接展示英文枚举（如 `unknown`、`probe_failed`、`handle_recorded_no_probe`）
3. 不得使用误导性文案暗示能力已实现
4. 真实 runtime 尚未启动时，不得展示 "AI 正在编码"、"Runtime 已启动"、"Claude/Codex 已连接"、"PR 已准备" 等文案

### H.2 英文枚举 → 中文映射表

#### Runtime Lifecycle State

| 英文枚举 | 中文展示 | 英文枚举 | 中文展示 |
|---------|---------|---------|---------|
| `unknown` | 未检测 | `spawning` | 启动中 |
| `alive` | 已确认存活 | `exited` | 已确认退出 |
| `missing` | 运行通道丢失 | `probe_failed` | 检测失败 |

#### Runtime Lifecycle Reason

| 英文枚举 | 中文展示 |
|---------|---------|
| `handle_not_assigned` | 尚未分配运行通道 |
| `handle_recorded_no_probe` | 已记录通道编号，但未检测是否在运行 |
| `snapshot_only_no_runtime_probe` | 仅基于会话记录生成快照，未做运行时探测 |
| `launch_gate_blocked` | 启动门禁已阻断 |

#### Runtime Event Type

| 英文枚举 | 中文展示（用于前端展示的事件标签） |
|---------|------------------------------|
| `runtime_launch_gate_evaluated` | 启动门禁已完成评估 |
| `runtime_launch_gate_blocked` | 启动门禁已阻断 |
| `runtime_launch_requested` | 已请求启动运行时 |
| `runtime_spawning` | 运行时正在启动 |
| `runtime_handle_bound` | 运行通道已绑定 |
| `runtime_alive_observed` | 运行时已确认存活 |
| `runtime_exited` | 运行时已退出 |
| `runtime_missing` | 运行通道丢失 |
| `runtime_probe_failed` | 运行时检测失败 |
| `runtime_kill_requested` | 已请求终止运行时 |
| `runtime_killed` | 运行时已被终止 |
| `runtime_cleanup_started` | 运行时清理已开始 |
| `runtime_cleanup_failed` | 运行时清理失败 |
| `runtime_cleanup_succeeded` | 运行时清理已完成 |

### H.3 禁止使用的误导文案

以下文案在对应能力未实现前**严禁**出现在前端页面：

| 禁止文案 | 原因 |
|---------|------|
| "AI 正在编码" | AI 自动编码尚未实现 |
| "Runtime 已启动" | 真实 runtime 尚未启动 |
| "Claude/Codex 已连接" | AI 运行时未接入 |
| "PR 已准备" | PR 产品闭环未实现 |
| "自动提交已开启" | git commit 未实现 |
| "代码已推送" | git push 未实现 |
| "CI 检查进行中" | CI 集成未实现 |
| "正在自动修复" | 自动修复未实现 |
| "提交成功" | 无 git commit 能力 |

### H.4 正确的中文事件文案示例

```
runtime_launch_gate_evaluated:
  "运行时启动门禁已全部通过。共检查 5 道条件：工作区状态就绪、工作区上下文可用、运行时参数预览就绪、工作区路径验证通过、适配器能力可用。门禁通过只表示前置条件满足，运行时尚未启动。"

runtime_launch_gate_blocked:
  "运行时启动门禁已阻断。第 3 道条件（运行时参数预览）未通过：缺少运行时类型配置。门禁阻断是受控安全行为，不是系统崩溃。"

runtime_launch_requested (将来):
  "运行时启动已被请求。适配器类型：后台执行通道；工作区路径：/tmp/aido-worktree。运行时正在启动中，尚未确认存活。"

runtime_alive_observed (将来):
  "运行时进程已确认存活。通道编号：进程号 48291。运行时当前正在以子进程方式运行。"

runtime_exited (将来):
  "运行时进程已退出。退出码：0（正常）。该进程已不在运行中。"
```

---

## I. 与现有 P3 evidence 的关系

P3-D 定义的事件模型与 P3 已有的三种证据形式**互补但不重叠**：

| 证据形式 | 来源 | 作用 | P3-D 事件如何关联 |
|---------|------|------|-----------------|
| **Runtime Launch Gate Evidence** (P3-B2) | `WorkerRunResult` → `WorkerRunOnceResponse` | 单次 Worker 响应中的门禁评估结果 | `runtime_launch_gate_evaluated` / `runtime_launch_gate_blocked` 事件的内容来源于此 |
| **AgentSession Runtime Lifecycle Snapshot** (P3-C1) | `AgentSession` 持久化字段 | 当前状态快照 | 快照的派生可以读取最新 runtime event 来改进 `runtime_lifecycle_state`（P3-C1 当前永远是 `unknown`，因为无事件可读） |
| **Runtime Lifecycle Event** (P3-D) | `AgentMessage` → `AgentTimelineMessage` | 时间线事件，不可修改的历史记录 | 这是 P3-D 设计的核心产物 |

三者不能混用：
- Gate evidence 是 "一次性评估"，Event 是 "历史记录"——Gate evidence 的数据写入 Event，但 Gate evidence 本身不持久化
- Snapshot 是 "当前派生状态"，Event 是 "事实链"——Snapshot 可以由 Event 派生，但不能替代 Event
- P3-D 不改变 P3-B / P3-C 的现有字段和结构

---

## J. 与参考 Agent Orchestrator 的关系

### 参考了的机制

| AO 机制 | 学习要点 | P3-D 对应设计 |
|---------|---------|-------------|
| **session/runtime 分轴** | `CanonicalSessionLifecycle` 将 runtime state 作为独立维度记录，不与 session state 混用 | P3-D event 独立记录 runtime 状态变化，不改变 session/execution event |
| **lifecycle manager 状态探测→记录** | `LifecycleManager.determineStatus()` → `commit lifecycle state change` → event emission | `runtime_*` event 在状态转换时写入 AgentMessage（由 Worker 或未来 LifecycleManager 触发） |
| **activity event / audit event** | `recordActivityEvent()` 将结构化事件追加到 activity log | `_append_message()` 模式复用于 runtime event；content_detail JSON 承载结构化证据 |
| **cleanup 失败保留审计线索** | AO 的 CleanupStack.runAll() 默认 swallow error，但提供 `onError` 回调来记录 | `runtime_cleanup_failed` event 专门用于记录清理失败，不丢失审计线索 |
| **runtime handle 作为事件关联 identity** | AO 的 `RuntimeHandle` 包含 id 和 runtimeName，用于关联 kill/restore 操作 | `runtime_handle_id` 在 content_detail JSON 和 state_from/state_to 中关联事件链 |

### 没有照搬的内容

| AO 内容 | 为什么不照搬 |
|---------|------------|
| 插件架构 (`PluginModule`/`PluginManifest`) | AI-Dev 不需要完整插件系统 |
| Node.js / TypeScript 技术栈 | AI-Dev 使用 Python + FastAPI + SQLite |
| `RecordActivityEvent` 文件系统 JSONL | AI-Dev 用 AgentMessage（SQLite）+ RunLog（JSONL）双通道 |
| tmux 作为默认 runtime | P3 阶段不做真实 runtime launch |
| `LifecycleManager` 轮询循环 | P3 阶段无真实进程可轮询 |
| `ActivitySignal` (native/terminal/hook 三层探活) | P3 阶段不做 runtime probe |
| SCM integration (PR/CI/review) | Delivery Axis 属于 P4+ |
| CLI / Next.js dashboard | AI-Dev 是 web-first API 应用 |

---

## K. 后续实现拆分建议

P3-D 只是设计文档。后续实现建议拆分为以下子阶段：

### P3-D1：Event Schema 文档 + 复审（当前已完成）

- 产出：本设计文档
- 不写任何代码

### P3-D2：新增 Runtime Event Domain Model + Builder

- 新增 `runtime/orchestrator/app/domain/runtime_event.py`
- 包含 `RuntimeEventSchema`（JSON 合同的数据结构）、`RuntimeEventBuilder`（工厂方法，从 gate result / probe result 构建标准化的 content_detail JSON）
- 不依赖数据库，不写 AgentMessage
- targeted tests

### P3-D3：AgentMessage 写入 `runtime_launch_gate_evaluated` / `runtime_launch_gate_blocked`

- 在 `TaskWorker.run_once()` 中，门禁评估完成后，调用 `AgentConversationService` 新方法 `record_runtime_event()` 写入 AgentMessage
- 这两个事件是唯一 "当前可立即实现" 的 runtime event（因为 gate result 数据已经存在）
- targeted tests

### P3-D4：前端 Timeline 只读展示 Runtime Event

- `AgentWorkspaceLifecycleAuditPanel` 已有 "按 event_type 过滤 + 解析 content_detail JSON" 的模式
- 复用同一模式，新增 runtime event 的显示：event_type = `runtime_*` 过滤、中文标签展示、content_detail 中的 summary_cn、safety_flags 子面板
- 所有 runtime event 标注 "证据只读，不表示 runtime 已启动"

### P3-F 之后：真实 Launch / Probe 事件接入

- `runtime_launch_requested` → `runtime_spawning` → `runtime_alive_observed`
- `runtime_exited` / `runtime_missing` / `runtime_probe_failed`
- `runtime_kill_requested` → `runtime_killed`
- `runtime_cleanup_started` / `runtime_cleanup_failed` / `runtime_cleanup_succeeded`

---

## L. 当前 Not started 清单

| # | 能力 | 说明 |
|---|------|------|
| 1 | `runtime_launch_requested` 真实事件写入 | 未实现 |
| 2 | `runtime_spawning` 事件 | 未实现 |
| 3 | `runtime_handle_bound` 事件 | 未实现 |
| 4 | `runtime_alive_observed` 事件 | 未实现 |
| 5 | `runtime_exited` 真实回写 | 未实现 |
| 6 | `runtime_missing` 事件 | 未实现 |
| 7 | `runtime_probe_failed` 事件 | 未实现 |
| 8 | `runtime_kill_requested` / `runtime_killed` 事件 | 未实现 |
| 9 | `runtime_cleanup_*` 真实事件 | 未实现 |
| 10 | 真实 subprocess adapter | `FakeRuntimeAdapter` 是唯一的适配器实现 |
| 11 | 真实 tmux / docker adapter | 未实现 |
| 12 | Runtime probe (探活) | 未实现 |
| 13 | AI 自动编码 | 未实现 |
| 14 | git add / commit / push | 未实现 |
| 15 | PR 创建与审核 | 未实现 |
| 16 | CI / review / merge loop | 未实现 |
| 17 | Project Director Conversation Hub | 未实现 |

---

## Gate 结论

| Gate | 结论 |
|------|------|
| P3-D Event / Audit Design | **Design only** |
| P3-D1 代码实现 | **Not started** |
| `runtime_launch_gate_evaluated` / `runtime_launch_gate_blocked` 事件写入 | **Not started** |
| 真实 runtime 启动 | **Not started** |
| Runtime probe | **Not started** |
| AI 自动编码 | **Not started** |
| Git add / commit / push / PR | **Not started** |
| **AI Project Director 总闭环** | **Partial** |

P3-D 完成了 Runtime Lifecycle Event / Audit 的完整设计合同——14 种事件类型、双通道落点方案、AgentMessage 字段映射、content_detail JSON 合同、中文文案规范。这些设计为后续 P3-D2/P3-D3/P3-D4 的逐步实现提供了明确的方向和约束。但 P3-D 本身不实现任何代码，所有真实 runtime / probe / AI 编码 / git PR 能力仍然是 Not started。

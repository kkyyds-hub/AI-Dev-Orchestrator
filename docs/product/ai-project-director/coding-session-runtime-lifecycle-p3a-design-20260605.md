# Coding Session Runtime Lifecycle P3-A 设计

> **文档类型**: P3-A 设计文档（只做设计收口，不改业务代码）
> **生成日期**: 2026-06-05
> **基准 commit**: `c9e179b2ebca5284d10ea1bcee1b31a5b81029df`
> **参考项目**: ComposioHQ Agent Orchestrator (`c3eeecb`)
> **前置文档**:
> - `.kkr/skills/ai-project-director-command-governance/SKILL.md`
> - `docs/product/ai-project-director/coding-session-worktree-p1-lifecycle-closure-20260605.md`
> - `docs/product/ai-project-director/coding-session-worktree-p2-worker-context-closure-20260605.md`
> - `docs/product/ai-project-director/gap-analysis/ai-project-director-ideal-gap-after-p1-20260605.md`
> - `docs/product/ai-project-director/coding-session-lifecycle-design-20260604.md`
> - `docs/product/ai-project-director/page-information-architecture-20260518.md`
> **边界**: 纯设计文档，不改 Python 代码、不改前端、不运行服务、不启动 AI runtime
> **状态**: P3-A 设计收口完成；Runtime lifecycle 未启动

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator 后端

| 文件 | 用途 |
|------|------|
| `runtime/orchestrator/app/domain/agent_session.py` | AgentSession 领域模型 — `agent_type`, `runtime_type`, `runtime_handle_id`, `coding_status`, `activity_state` 枚举和字段 |
| `runtime/orchestrator/app/domain/agent_message.py` | AgentMessage 领域模型 — `event_type`, `phase`, `state_from`, `state_to`, `content_summary`, `content_detail` |
| `runtime/orchestrator/app/workers/task_worker.py` | `WorkerRunResult` (证据字段), `validate_worker_agent_workspace()`, `resolve_worker_workspace_context()`, `build_worker_runtime_launch_dry_run()`, proof pipeline |
| `runtime/orchestrator/app/workers/worktree_safe_command.py` | `WorkerWorktreeSafeCommandProofRunner.run_probe()` — 唯一的 allowlisted `pwd` proof |
| `runtime/orchestrator/app/api/routes/workers.py` | `WorkerRunOnceResponse` — API 层透传全部 evidence 字段 |
| `runtime/orchestrator/app/api/routes/agent_threads.py` | `AgentSessionResponse` — AgentSession API DTO |
| `runtime/orchestrator/app/services/agent_conversation_service.py` | `AgentConversationService` — `start_session()`, `record_execution_started()`, `record_execution_outcome()`, `finalize_session()`, `_append_message()` |
| `runtime/orchestrator/tests/test_worker_workspace_readonly_validation.py` | P2 12 targeted tests |

### Agent Orchestrator 参考

| 文件 | 参考要点 |
|------|---------|
| `packages/core/src/types.ts` | `CanonicalSessionLifecycle` 三元组 (session/pr/runtime)；`Runtime.create()` + `isAlive()` + `sendMessage()`；`ActivitySignal`；`RuntimeHandle` |
| `packages/core/src/session-manager.ts` | CleanupStack LIFO undo；spawn → workspace.create → runtime.create → agent |
| `packages/core/src/lifecycle-manager.ts` | 轮询循环 + status detection + reaction engine；`determineStatus()` |
| `packages/core/src/lifecycle-state.ts` | `deriveLegacyStatus()` — 三元组联合推导；`CanonicalSessionLifecycle` schema |
| `packages/core/src/cleanup-stack.ts` | LIFO undo stack, `dismiss()` on success, `runAll()` on failure |
| `packages/plugins/workspace-worktree/src/index.ts` | `workspacePath` 作为 runtime/command seam；`destroy()`: git worktree remove --force，不删 branch；restore recovery 路径 |

---

## 1. P3-A 目标与非目标

### 1.1 目标

P3-A 是 **Runtime Axis 的完整生命周期设计**。P1 完成了 Workspace Axis（worktree 创建/清理），P2 完成了 Worker Context / Runtime Dry-run / Safe Command Proof（"证明可以，但不执行"）。P3-A 设计的是：当 `execution_enabled` 从 `False` 翻转为 `True` 时，Runtime Axis 需要什么状态机、什么前置条件、什么回写路径、什么审计机制。

具体设计目标：

1. **定义 Runtime lifecycle 完整状态机** — 从 `unknown` → `spawning` → `alive` → `exited`/`missing`/`probe_failed`
2. **定义 Runtime launch 前置条件** — P2 证据链如何作为 launch gate
3. **定义 Runtime handle 如何绑定 AgentSession** — `runtime_handle_id` 字段的填充时机和内容
4. **定义 blocked / failed / exited / missing / probe_failed 如何回写 AgentSession** — `coding_status` 和 `activity_state` 的状态流转
5. **定义 runtime event / audit 如何落 AgentMessage** — timeline event 的类型、内容和时机
6. **定义 Runtime launch dry-run API 是否独立化的建议** — 对比内联在 TaskWorker 和独立 API endpoint 的权衡
7. **定义与现有 evidence 字段的关系** — P2 字段是 P3-A 的 gate，P3-A 新增字段是 gate 通过后的 runtime 状态

### 1.2 非目标

P3-A **不是**：

- 不是 P3-B（worker runtime adapter contract — 如何对接 subprocess/tmux/docker 的具体实现）
- 不是 P3-C（safe command proof 前端展示）
- 不是 P3-D（Project Director Conversation Hub）
- 不是 AI runtime 的启动实现代码
- 不是对 `TaskWorker.run_once()` 控制流的修改
- 不是对 `ExecutorService.execute_task()` 的修改

### 1.3 本设计不宣称已实现

P3-A 的所有设计内容均为 **设计建议**。当前代码库中的 `execution_enabled`、`launches_runtime`、`runs_command` 全部保持 `False`。本设计文档定义了当未来阶段翻转为 `True` 时需要遵循的机制，但**不表示这些机制已经实现**。

---

## 2. Runtime Lifecycle 状态机

### 2.1 设计基线回顾

设计基线文档 `coding-session-lifecycle-design-20260604.md` 定义了 RuntimeAxis 的状态枚举：

```
unknown → spawning → alive → exited
                            → missing
                            → probe_failed
```

P3-A 在此基础上补充每个状态的定义、触发条件、可恢复性和回写要求。

### 2.2 完整状态定义

| 状态 | 含义 | 触发条件 | 可恢复到 alive? | AgentSession 回写 |
|------|------|---------|----------------|-------------------|
| `unknown` | 未探测或无法探测 | AgentSession 创建后，runtime 启动前 | — (初始态) | `coding_status=spawning`, `activity_state=ready` |
| `spawning` | Runtime 进程正在启动 | `RuntimeAdapter.launch()` 调用后，进程尚未确认存活 | N/A (瞬态) | `coding_status=spawning`, `activity_state=active`, `runtime_handle_id=<handle>` |
| `alive` | 进程存活，正常运行 | `RuntimeAdapter.is_alive()` 返回 True（如 `ps` 确认 PID、tmux session 存在、container running） | — (正常态) | `coding_status=working`, `activity_state=active` |
| `exited` | 进程正常或异常退出 | `RuntimeAdapter.is_alive()` 返回 False + exit code 已知 | 否 (终态) | `coding_status=completed/failed`, `activity_state=exited` |
| `missing` | 进程意外消失（如 tmux session 被外部 kill、容器被删除、PID 被回收） | `RuntimeAdapter.is_alive()` 返回 False + exit code 未知 + handle 消失 | 否 (终态) | `coding_status=terminated`, `activity_state=exited` |
| `probe_failed` | 无法确认进程状态（网络/权限/OS 问题） | `RuntimeAdapter.is_alive()` 抛出异常或超时，但不确定进程是否已死 | 是 (临时态) | `coding_status=stuck`, `activity_state=blocked` |

### 2.3 状态转换图

```
                    ┌─────────┐
                    │ unknown │  ← AgentSession 创建，runtime 尚未启动
                    └────┬────┘
                         │ RuntimeAdapter.launch()
                         ▼
                    ┌──────────┐
                    │ spawning │  ← 瞬态：进程正在启动（通常 < 5s）
                    └────┬─────┘
                         │ probe: is_alive() == True
                         ▼
                    ┌───────┐
              ┌─────│ alive │─────┐
              │     └───┬───┘     │
              │         │         │
              │  probe: │         │ probe:
              │  alive  │         │ is_alive() == False
              │  (正常)  │         │ + exit code known
              │         │         │
              │         │         ▼
              │         │    ┌────────┐
              │         │    │ exited │ ← 终态：进程已退出
              │         │    └────────┘
              │         │
              │         │ probe:
              │         │ is_alive() throws
              │         │ + handle 不可恢复
              │         │
              │         ▼
              │    ┌─────────┐
              │    │ missing │ ← 终态：进程意外消失
              │    └─────────┘
              │
              │ probe:
              │ is_alive() throws/timeout
              │ + 不确定进程生死
              │
              ▼
         ┌──────────────┐
         │ probe_failed │ ← 临时态：可重试探测
         └──────────────┘
              │ probe: is_alive() == True
              ▼
         ┌───────┐
         │ alive │ (恢复到正常态)
         └───────┘
```

### 2.4 与 AO `CanonicalRuntimeState` 的对比

| AO Runtime State | AI-Dev Runtime State | 差异 |
|------------------|---------------------|------|
| `unknown` | `unknown` | 一致 |
| — | `spawning` | AO 没有显式的 spawning 状态（由 `session.state = spawning` 覆盖） |
| `alive` | `alive` | 一致 |
| `exited` | `exited` | 一致 |
| `missing` | `missing` | 一致 |
| `probe_failed` | `probe_failed` | 一致 |

关键差异：AO 将 "正在启动" 表达为 `session.state = spawning`，不单独在 runtime 维度建模。AI-Dev 的四轴模型中 Runtime Axis 独立于 Session Axis，因此 `spawning` 显式定义在 Runtime Axis 上。

---

## 3. Runtime Launch 前置条件

### 3.1 设计原则

Runtime launch 不能无条件执行。在 `execution_enabled` 从 `False` 翻转为 `True` 之前，P2 的全部证据链必须作为 gate 逐一验证。

### 3.2 Gate Chain

P3-A 定义的 Runtime launch gate chain（按顺序）：

| Gate # | Gate 名称 | 检查对象 | 失败行为 |
|--------|----------|---------|---------|
| G1 | Workspace validation | `validate_worker_agent_workspace()` → `ready` | 阻断 launch，`coding_status=stuck`, `activity_state=blocked` |
| G2 | Workspace context resolution | `workspace_context.ready` + `uses_agent_workspace` | 阻断 launch |
| G3 | Runtime dry-run configuration | `runtime_launch_dry_run.ready` + `agent_type` + `runtime_type` | 阻断 launch |
| G4 | Safe command proof | `worktree_safe_command_proof.ready` (P2-D) | 阻断 launch，`last_workspace_error` 写入 proof block summary |
| G5 | Runtime adapter capability check | `RuntimeAdapter.can_launch(agent_type, runtime_type)` | 阻断 launch，`reason_code = runtime_adapter_unavailable` |

全部 5 个 gate 通过后，`execution_enabled` 翻转为 `True`，runtime launch 可以执行。

### 3.3 Gate 数据结构建议

```python
@dataclass(slots=True, frozen=True)
class RuntimeLaunchGateResult:
    """Aggregate result of all pre-launch gate checks."""

    ready: bool
    gates_passed: list[str]          # 通过的 gate 名称列表
    gates_failed: list[str]          # 失败的 gate 名称列表
    blocking_reason_code: str | None # 第一个失败的 reason_code
    blocking_summary: str | None     # 人类可读的失败摘要
    workspace_context: WorkerWorkspaceContextResolution
    runtime_dry_run: WorkerRuntimeLaunchDryRun
    safe_command_proof: WorkerWorktreeSafeCommandProof  # P2-D
```

该数据结构作为 `WorkerRunResult` 的新增字段，在 API 中透传。

---

## 4. Runtime Dry-run API 是否独立化的建议

### 4.1 当前状况

P2-C 的 `build_worker_runtime_launch_dry_run()` 是 `TaskWorker.run_once()` 的内部函数。它由 Worker 在执行主链中内联调用，结果作为 `WorkerRunResult` evidence 字段返回。

### 4.2 独立化 vs 内联的权衡

| 维度 | 内联在 TaskWorker (当前) | 独立 API endpoint |
|------|------------------------|-------------------|
| **调用时机** | 每次 `run_once()` 自动执行 | 前端/用户可以按需请求 |
| **对 Worker 的影响** | 增加 run_once 的延迟（当前为纯计算，无 I/O 开销） | 不影响 Worker 热路径 |
| **前端可见性** | 通过 `WorkerRunOnceResponse` 透传 | 独立 API 可提供更清晰的 dry-run 结果 |
| **复用性** | 只对 Worker 调用方可见 | 其他服务（如 Conversation Hub）可独立调用 |
| **复杂度** | 不增加 API surface | 增加一个 route + DTO |

### 4.3 建议

**分两阶段**：

- **P3-A 阶段**: 保持内联在 `TaskWorker` 中，作为 launch gate chain 的一个环节。`WorkerRuntimeLaunchDryRun` 的 ready/blocked 状态决定是否继续到 G4（safe command proof）。
- **P3-B 阶段**: 当 runtime adapter contract 定义完成后，考虑新增独立 API `POST /agent-sessions/{id}/runtime-launch-dry-run`，允许前端/用户在 Worker 循环之外预览 runtime 配置。

独立 API 的签名建议：

```
POST /agent-sessions/{id}/runtime-launch-dry-run
Response: RuntimeLaunchDryRunResponse {
    ready: bool
    source: str
    reason_code: str | null
    session_id: str
    agent_type: str | null
    runtime_type: str | null
    workspace_path: str | null
    launch_cwd_preview: str | null
    launch_command_preview: str | null
    gate_checks: [GateCheckResult]  # 逐个 gate 的状态
    execution_enabled: bool         # P3-A 仍为 False
}
```

---

## 5. Runtime Handle 如何绑定 AgentSession

### 5.1 设计

`AgentSession.runtime_handle_id` (String, nullable, max_length=200) 已经存在于模型中。P3-A 定义它的填充时机和内容格式。

| Runtime Type | handle 内容 | 填充时机 | 示例 |
|-------------|-----------|---------|------|
| `subprocess` | `pid:<PID>` | `subprocess.Popen` 返回后立即填充 | `pid:48291` |
| `tmux` | `tmux:<session_name>` | `tmux new-session -d` 返回后填充 | `tmux:aido-session-proj-abc123` |
| `docker` | `docker:<container_id>` | `docker run -d` 返回后填充 | `docker:a1b2c3d4e5f6` |
| `process` | `pid:<PID>` 或 `handle:<arbitrary_key>` | 平台特定 | `pid:48291` |

### 5.2 填充流程

```python
# 伪代码，仅供设计参考
class RuntimeAdapter:
    def launch(self, *, agent_session: AgentSession, ...) -> RuntimeHandle:
        """Start the runtime process and return an opaque handle."""
        ...

# TaskWorker.run_once() 中 (P3-A 之后)：
if gate_result.ready:
    handle = runtime_adapter.launch(agent_session=agent_session, ...)
    agent_session = agent_conversation_service.bind_runtime_handle(
        session_id=agent_session.id,
        runtime_handle_id=handle.to_string(),   # "pid:48291"
    )
```

### 5.3 AgentConversationService 新增方法建议

```python
def bind_runtime_handle(
    self,
    *,
    session_id: UUID,
    runtime_handle_id: str,
) -> AgentSession:
    """Bind a runtime handle after successful launch."""
    session = self._require_session(session_id)
    session = self.agent_session_repository.update_status(
        session.id,
        runtime_handle_id=runtime_handle_id,
        coding_status=CodingSessionStatus.WORKING,
        activity_state=CodingSessionActivityState.ACTIVE,
        summary="Runtime process launched and bound to agent session.",
    )
    self._append_message(
        session=session,
        role=AgentMessageRole.SYSTEM,
        message_type=AgentMessageType.TIMELINE,
        event_type="runtime_handle_bound",
        phase=AgentSessionPhase.EXECUTING.value,
        state_from=session.current_phase.value,
        state_to=AgentSessionPhase.EXECUTING.value,
        content_summary=f"Runtime handle bound: {runtime_handle_id}",
        content_detail=None,
    )
    return session
```

---

## 6. Blocked / Failed / Exited / Missing / Probe Failed 如何回写 AgentSession

### 6.1 回写矩阵

| Runtime 状态 | `coding_status` | `activity_state` | `AgentSession.status` | `last_workspace_error` | 触发动作 |
|-------------|----------------|-----------------|----------------------|----------------------|---------|
| `spawning` | `spawning` | `active` | `running` | 不变 | timeline event: `runtime_spawning` |
| `alive` | `working` | `active` | `running` | 不变 | timeline event: `runtime_alive` |
| `exited` (exit 0) | `completed` | `exited` | `completed` | 不变 | timeline event: `runtime_exited` → 触发 `finalize_session()` |
| `exited` (exit ≠ 0) | `failed` | `exited` | `failed` | `"Runtime exited with code N"` | timeline event: `runtime_exited` → 触发 `finalize_session()` |
| `missing` | `terminated` | `exited` | `blocked` | `"Runtime handle lost: {handle}"` | timeline event: `runtime_missing` → 触发 failure review |
| `probe_failed` | `stuck` | `blocked` | `running` (不变) | `"Runtime probe failed: {error}"` | timeline event: `runtime_probe_failed` → 进入 retry loop (最多 3 次) |

### 6.2 probe_failed 的恢复路径

`probe_failed` 是唯一可恢复的非正常状态。恢复路径：

```
probe_failed → retry probe (最多 3 次, 间隔递增)
  ├─ probe success → alive (恢复)
  └─ 3 次全部 probe_failed → missing (升级为终态)
```

### 6.3 回写方法建议

当前 `AgentConversationService` 已有 `finalize_session()` 方法，支持 `run_status` 驱动的 `coding_status` 设置（COMPLETED/FAILED/TERMINATED）和 `activity_state=EXITED`。P3-A 建议新增：

```python
def record_runtime_state_change(
    self,
    *,
    session_id: UUID,
    runtime_state: str,          # "spawning" / "alive" / "exited" / "missing" / "probe_failed"
    coding_status: CodingSessionStatus,
    activity_state: CodingSessionActivityState,
    runtime_handle_id: str | None = None,
    exit_code: int | None = None,
    error_summary: str | None = None,
) -> AgentSession:
    """Record a runtime state transition with timeline audit."""
    ...
```

该方法负责：
1. 更新 AgentSession 的 `coding_status`、`activity_state`、`runtime_handle_id`、`last_workspace_error`
2. 写入 AgentMessage 的 timeline event（`event_type = f"runtime_{runtime_state}"`）
3. 在 `runtime_state = "exited"` 时触发 `finalize_session()`

---

## 7. Runtime Event / Audit 如何落 AgentMessage 或 Run Log

### 7.1 双通道审计

P3-A 建议 runtime 事件同时写入两个审计通道：

| 通道 | 存储 | 用途 | 内容 |
|------|------|------|------|
| **AgentMessage (timeline)** | `agent_messages` 表 | 前端 Agent 线程页面只读展示 | `event_type = runtime_{state}`, `content_summary = human-readable summary`, `content_detail = {runtime_state, handle_id, exit_code, error}` |
| **Run Log** | `runs/{task_id}/{run_id}.jsonl` | Worker 级别的结构化证据 | `event = runtime_state_change`, `data = {previous_state, new_state, handle_id, exit_code, probe_attempt, probe_error}` |

### 7.2 AgentMessage event 类型定义

| event_type | message_type | role | 触发条件 |
|-----------|-------------|------|---------|
| `runtime_spawning` | `TIMELINE` | `SYSTEM` | RuntimeAdapter.launch() 调用后 |
| `runtime_alive` | `TIMELINE` | `SYSTEM` | 首次 probe 确认进程存活 |
| `runtime_exited` | `TIMELINE` | `SYSTEM` | 进程退出（正常或异常） |
| `runtime_missing` | `TIMELINE` | `SYSTEM` | 进程意外消失 |
| `runtime_probe_failed` | `TIMELINE` | `SYSTEM` | 探活失败（临时） |
| `runtime_probe_recovered` | `TIMELINE` | `SYSTEM` | probe_failed 后重试成功 |
| `runtime_handle_bound` | `TIMELINE` | `SYSTEM` | runtime_handle_id 写入 AgentSession |

### 7.3 AgentMessage content_detail 结构建议

每个 runtime event 的 `content_detail` 字段建议使用结构化 JSON：

```json
{
  "runtime_state": "alive",
  "previous_runtime_state": "spawning",
  "runtime_handle_id": "pid:48291",
  "runtime_type": "subprocess",
  "agent_type": "openai_provider",
  "exit_code": null,
  "probe_attempt": null,
  "probe_error": null
}
```

### 7.4 当前已有审计模式的复用

当前 `AgentConversationService` 已经建立了 timeline event 写入模式：

- `start_session()` → `event_type = "session_started"`
- `record_execution_started()` → `event_type = "execution_started"`
- `record_execution_outcome()` → `event_type = "execution_finished"` / `"review_passed"` / `"review_required"` / `"rework_requested"` / `"boss_note_event"`
- `finalize_session()` → `event_type = "session_finalized"`

P3-A 的 runtime event 应遵循相同的 `_append_message()` 模式，`event_type` 前缀统一为 `runtime_*`。

---

## 8. 与现有 WorkerRunResult / WorkerRunOnceResponse Evidence 字段的关系

### 8.1 字段分层

P2 和 P3-A 的字段按语义分为四层：

| 层 | 阶段 | 字段组 | 语义 | execution_enabled |
|----|------|--------|------|-------------------|
| **L0: AgentSession 元数据** | P0/P1 | `agent_type`, `runtime_type`, `workspace_type`, `workspace_path`, `workspace_clean`, `branch_name` | "AgentSession 知道自己是谁、在哪" | N/A |
| **L1: Workspace Context** | P2-B | `workspace_context_*` (10 字段) | "Worker 确认 worktree 可用" | `False` |
| **L2: Runtime Dry-run** | P2-C | `runtime_launch_dry_run_*` (18 字段) | "Runtime 配置预览正确" | `False` |
| **L3: Safe Command Proof** | P2-D | `worktree_safe_command_proof_*` (21 字段) | "pwd 证明 cwd 指向 worktree" | `False` |
| **L4: Runtime Lifecycle State** | P3-A | `runtime_lifecycle_state`, `runtime_lifecycle_reason`, `runtime_handle_id`, `runtime_exit_code`, `runtime_probe_attempt`, `runtime_probe_error` | "Runtime 进程正在运行/已退出/丢失" | **`True`** (当 gate 全部通过时) |

### 8.2 新增字段建议

在 `WorkerRunResult` 中新增 P3-A runtime lifecycle 字段：

```python
# P3-A Runtime lifecycle state fields
runtime_lifecycle_state: str | None = None        # "unknown"|"spawning"|"alive"|"exited"|"missing"|"probe_failed"
runtime_lifecycle_reason: str | None = None       # 转换原因
runtime_handle_id: str | None = None              # "pid:NNN"|"tmux:name"|"docker:cid" (已存在字段，P3-A 填充)
runtime_exit_code: int | None = None              # subprocess exit code
runtime_probe_attempt: int | None = None          # 探活重试次数
runtime_probe_error: str | None = None            # 探活错误信息
runtime_lifecycle_execution_enabled: bool | None = None  # P3-A gate chain 全部通过后 True
runtime_lifecycle_launches_runtime: bool | None = None    # RuntimeAdapter.launch() 是否已调用
```

### 8.3 与 P2 字段的关系

P2 字段 **不是** P3-A 的替代品，而是 P3-A 的 **前置 gate**：

- L1-L3 全部 ready → `runtime_lifecycle_execution_enabled = True`
- L1-L3 任一 blocked → `runtime_lifecycle_execution_enabled = False`，不执行 launch
- L4 字段仅在 launch 后才有有效值

P2 的硬性声明（`execution_enabled=False`，`launches_runtime=False`）在 P3-A 实现后，L4 层的对应字段会变为 `True`，但 L1-L3 的字段保持 `False`（workspace context 和 dry-run 本身仍然是 evidence-only）。

---

## 9. 与 Workspace Safe Command Proof 的关系

### 9.1 P2-D proof 在 P3-A 中的角色

P2-D 的 `WorkerWorktreeSafeCommandProof` 是 P3-A runtime launch gate chain 的 **第四道 gate (G4)**。

关系：

1. **proof.ready == True**: gate 通过，继续到 G5（adapter capability check）
2. **proof.ready == False**: gate 失败，runtime launch 被阻断。`proof.reason_code` 和 `proof.observed_pwd` 写入 `last_workspace_error`

### 9.2 proof 的扩展方向

P3-A 不改变 P2-D 的 `pwd` 只有一个 allowlisted 命令。但设计上预留扩展点：

```
当前: pwd → 证明 cwd 正确
P3-A 后可能扩展（但不实现）:
  - git rev-parse --show-toplevel → 证明在正确的 git 仓库内
  - env | grep PATH → 证明环境变量正确
  - which python3 → 证明工具链可用
```

所有扩展命令必须在 deny-by-default allowlist 中显式注册，保持与 `WorkerPwdCommandRunner._ensure_allowlisted()` 相同的安全模式。

### 9.3 proof 与 runtime launch 的执行顺序

```
L1: workspace validation ──┐
L2: workspace context ─────┤
L3: runtime dry-run ───────┤ gate chain
L4: safe command proof ────┤ (pwd)
L5: adapter capability ────┘
         │
         ▼ (all gates passed)
    execution_enabled = True
         │
         ▼
    RuntimeAdapter.launch(cwd=workspace_path)
         │
         ▼
    probe: is_alive()
         │
         ▼
    runtime_lifecycle_state = "alive"
```

---

## 10. 前端只读展示字段清单

### 10.1 当前前端已展示的字段 (P2-A / P2-A-R1)

| 组件 | 已展示字段 |
|------|-----------|
| `AgentCodingSessionSnapshot` | `agent_type`, `runtime_type`, `runtime_handle_id`, `branch_name`, `workspace_type`, `workspace_path`, `workspace_clean`, `last_workspace_error`, `coding_status`, `activity_state` |
| `AgentSessionList` | `session_status`, `review_status`, `current_phase`, `coding_status`, `activity_state`, `workspace_type`, `workspace_path`, `branch_name`, `last_workspace_error` |
| `AgentWorkspaceLifecycleAuditPanel` | workspace create/cleanup audit events: `workspace_path`, `branch_name`, `status`, `blocked_reason`, `runs_git`, `runs_write_git` |

### 10.2 P3-A 建议新增的前端只读展示

| 新增字段/组件 | 来源 | 展示位置 |
|-------------|------|---------|
| `runtime_lifecycle_state` | `WorkerRunResult` / `AgentSessionResponse` | `AgentCodingSessionSnapshot` 新增一行：运行载体状态 |
| `runtime_exit_code` | `WorkerRunResult` / `AgentSessionResponse` | `AgentCodingSessionSnapshot` — 仅 `exited` 状态时展示 |
| `runtime_probe_attempt` | `WorkerRunResult` / `AgentSessionResponse` | `AgentCodingSessionSnapshot` — 仅 `probe_failed` 状态时展示 |
| Runtime timeline events (`runtime_spawning`, `runtime_alive`, `runtime_exited`, etc.) | `AgentMessage` timeline | `AgentTimelineList` — 与现有 session/execution event 混合展示 |
| `runtime_lifecycle_execution_enabled` | `WorkerRunResult` / `AgentSessionResponse` | `AgentCodingSessionSnapshot` 免责声明中引用 |

### 10.3 `AgentCodingSessionSnapshot` 扩展建议

在现有 "智能体 / 运行载体 / 后台通道 / 分支 / 工作区类型 / 工作区路径" 六栏下方，新增第七栏：

```typescript
// 运行载体状态
runtime_lifecycle_state: "alive" | "exited" | "spawning" | "missing" | "probe_failed" | null
runtime_exit_code: number | null
```

展示逻辑：
- `alive` → 绿色 badge "进程存活"
- `exited` (exit 0) → 灰色 badge "已退出 (正常)" + exit_code
- `exited` (exit ≠ 0) → 红色 badge "已退出 (异常)" + exit_code
- `spawning` → 蓝色 badge "启动中"
- `missing` → 黄色 badge "进程丢失"
- `probe_failed` → 橙色 badge "探活失败"
- `null` → "未启动 AI runtime"（当前 P2 状态的展示）

---

## 11. 仍然 Not Started 的能力清单

P3-A 设计完成，但以下能力在代码层面仍然 **Not Started**：

| # | 能力 | 状态 | 预计阶段 |
|---|------|------|---------|
| 1 | 真实 AI runtime 进程启动（subprocess/tmux/docker） | Not started | P3-B |
| 2 | RuntimeAdapter 接口定义和实现 | Not started | P3-B |
| 3 | `RuntimeAdapter.is_alive()` — 进程探活 | Not started | P3-B |
| 4 | `RuntimeAdapter.launch()` — 进程创建 | Not started | P3-B |
| 5 | Runtime lifecycle 状态机代码实现 | Not started | P3-B |
| 6 | Gate chain (G1-G5) 代码实现 | Not started | P3-B |
| 7 | `record_runtime_state_change()` — AgentSession 回写 | Not started | P3-B |
| 8 | Runtime timeline event (`runtime_*`) — AgentMessage 写入 | Not started | P3-B |
| 9 | Runtime probe retry loop (probe_failed → missing 升级) | Not started | P3-B |
| 10 | Runtime lifecycle 前端只读展示 | Not started | P3-C (建议) |
| 11 | CleanupStack / rollback on launch failure | Not started | P3-B |
| 12 | AI runtime 在 worktree 中执行自动编码 | Not started | P4+ |
| 13 | Git add / commit / push / PR 产品闭环 | Not started | P5+ |
| 14 | CI / review / merge loop | Not started | P5+ |
| 15 | Project Director Conversation Hub | Not started | P7 |
| 16 | AI Project Director 总闭环 | **仍为 Partial** | — |

---

## 12. P3-B / P3-C / P3-D 的后续拆分建议

### 12.1 P3-B：Worker Runtime Adapter Contract

**目标**: 定义 `RuntimeAdapter` 接口并实现 subprocess 的最小可用版本。

**范围**:
- 定义 `RuntimeAdapter` abstract interface：`can_launch(agent_type, runtime_type) → bool`、`launch(session, workspace_path) → RuntimeHandle`、`is_alive(handle) → bool`、`kill(handle) → None`
- 实现 `SubprocessRuntimeAdapter`：使用 `subprocess.Popen` 启动，PID 作为 handle
- 在 `TaskWorker.run_once()` 中插入 gate chain (G1-G5) + launch + probe + state writeback
- AgentSession 新增 `runtime_lifecycle_state` 字段（或在现有 `coding_status`/`activity_state` 上扩展推导逻辑）
- 实现 CleanupStack 在 launch 失败时的回滚
- targeted tests

**不包含**:
- tmux / docker runtime adapter（后续扩展）
- AI 编码任务的实际执行

### 12.2 P3-C：Runtime Lifecycle + Safe Command Proof 前端展示

**目标**: 将 P3-A 定义的 runtime lifecycle 字段和 P2-D 的 safe command proof 字段接入前端。

**范围**:
- `AgentCodingSessionSnapshot` 新增 `runtime_lifecycle_state` 展示
- `AgentTimelineList` 展示 `runtime_*` timeline events
- 新增 `WorktreeSafeCommandProofPanel` 组件：展示 `pwd` proof 结果
- 所有组件保持只读免责声明

### 12.3 P3-D：Runtime Dry-run 独立 API

**目标**: 新增独立的 runtime dry-run API endpoint。

**范围**:
- `POST /agent-sessions/{id}/runtime-launch-dry-run` 或等价的 `/workers/runtime-launch-dry-run`
- 独立于 Worker 循环的调用能力
- 前端 "预览 Runtime 配置" 按钮接入

### 12.4 分阶段路线总结

```
P1: Workspace Axis — worktree create/cleanup (Done ✅)
P2: Worker Context / Dry-run / Safe Command Proof (Done ✅)
P3-A: Runtime Lifecycle 设计收口 (本文档 ✅)
P3-B: Runtime Adapter Contract + subprocess launch + gate chain
P3-C: 前端只读展示 Runtime lifecycle + Safe Command Proof
P3-D: Runtime Dry-run 独立 API
P4: AI runtime in worktree 自动编码
P5: Worktree diff → commit candidate → PR
P6: 审批 / commit / delivery
P7: Project Director Conversation Hub
P8: 端到端 UAT / 总 Gate
```

---

## 13. Gate 结论

### 13.1 P3-A 设计收口

| Gate | 结论 |
|------|------|
| P3-A Runtime Lifecycle Design | **Design Complete** |
| P3-A 代码实现 | **Not started** |

### 13.2 AI Project Director 总闭环

**仍为 Partial。**

P3-A 完成了 Runtime Axis 的完整生命周期设计——状态机、gate chain、handle 绑定、状态回写、审计通道、前端展示建议。但：

- Runtime Axis 的代码实现未启动（`execution_enabled` 仍为 `False`）
- Delivery Axis 全部未实现
- Project Director Conversation Hub 未建设

本设计文档不是 runtime 启动的宣告，而是当 future phase 将 `execution_enabled` 翻转为 `True` 时必须遵循的蓝图。

---

## 附录 A: 设计决策记录

| # | 决策 | 理由 |
|---|------|------|
| 1 | `spawning` 作为 Runtime Axis 独立状态 | 四轴模型中 Runtime 独立于 Session；AO 将 spawning 放在 session 层是三元组共享的妥协 |
| 2 | Runtime dry-run API 先不独立化 | 减少 P3-A 的 API surface；dry-run 作为 gate chain 内联在 Worker 中更简洁 |
| 3 | AgentMessage + Run Log 双通道审计 | AgentMessage 给前端 timeline 展示；Run Log 给 Worker 级结构化证据 |
| 4 | probe_failed 最多重试 3 次后升级为 missing | 避免无限 retry；3 次足以覆盖短暂的网络/OS 抖动 |
| 5 | gate chain 使用顺序组合（非并行） | 每个 gate 依赖前一个的输出；并行无意义且增加复杂度 |
| 6 | `runtime_handle_id` 使用 `<type>:<value>` 格式 | 便于前端按类型解析和展示；清晰区分不同 runtime 类型的 handle |
| 7 | P2 安全边界不因 P3-A 设计而降级 | `execution_enabled` 翻转前必须全部 gate 通过；翻转是显式的、有审计记录的 |

---

## 附录 B: 与 AO 关键机制的对比总结

| 机制 | AO 实现 | AI-Dev P3-A 设计 | 差异 |
|------|---------|-----------------|------|
| Runtime 创建 | `Runtime.create(config)` → `RuntimeHandle` | `RuntimeAdapter.launch(session, workspace_path)` → `RuntimeHandle` | AO 通过插件系统动态查找；AI-Dev 通过 adapter contract 显式选择 |
| 探活 | `Runtime.isAlive(handle)` → bool | `RuntimeAdapter.is_alive(handle)` → bool | 语义一致 |
| 活动检测 | `Agent.getActivityState()` + `ActivitySignal` | `coding_status`/`activity_state` 由 Runtime 状态推导 + probe 驱动 | AO 有独立的 ActivitySignal 层（native/terminal/hook）；AI-Dev 暂不引入 |
| CleanupStack | LIFO undo stack, `dismiss()` on success | 建议在 P3-B 中引入相同模式 | P2 无 rollback（P1 已知缺口）；P3-B 应补齐 |
| 状态推导 | `deriveLegacyStatus()` 从三元组联合推导 | 四轴独立字段 + `coding_status` 承载联合推导结果 | AO 不存储冗余 "整体状态"；AI-Dev 显式存储 `coding_status` 作为快照 |
| Runtime handle | `RuntimeHandle { id, runtimeName, data }` | `runtime_handle_id: str` (格式: `pid:NNN`) | AO 使用结构化对象；AI-Dev 使用字符串以保持模型简单 |

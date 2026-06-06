# Coding Session Runtime Lifecycle P3 阶段收口

> **文档类型**: P3 阶段收口审计
> **生成日期**: 2026-06-06
> **基准 commit**: `5b9e4edad9811639b95ce653ecab809481064d84`
> **参考项目**: ComposioHQ Agent Orchestrator (`c3eeecb`)
> **前置文档**:
> - `.kkr/skills/ai-project-director-command-governance/SKILL.md`
> - `docs/product/ai-project-director/coding-session-runtime-lifecycle-p3a-design-20260605.md`
> - `docs/product/ai-project-director/coding-session-worktree-p2-worker-context-closure-20260605.md`
> - `docs/product/ai-project-director/coding-session-worktree-p1-lifecycle-closure-20260605.md`
> - `docs/product/ai-project-director/gap-analysis/ai-project-director-ideal-gap-after-p1-20260605.md`
> - `docs/product/ai-project-director/coding-session-lifecycle-design-20260604.md`
> - `docs/product/ai-project-director/page-information-architecture-20260518.md`
> **边界**: 收口审计，不改代码，不新增功能
> **状态**: P3 Runtime Lifecycle Evidence: Pass；AI Project Director 总闭环 Partial

---

## 0. 核对过的文件清单

### AI-Dev-Orchestrator 后端

| 文件 | 用途 |
|------|------|
| `runtime/orchestrator/app/workers/runtime_adapter.py` | RuntimeAdapter contract + FakeRuntimeAdapter + RuntimeLifecycleSnapshot + gate chain |
| `runtime/orchestrator/app/workers/task_worker.py` | `WorkerRunResult` P3 evidence 字段 + gate chain 接入 + executor 阻断 |
| `runtime/orchestrator/app/api/routes/workers.py` | `WorkerRunOnceResponse` P3 evidence 字段 + `RuntimeLifecycleSnapshotResponse` |
| `runtime/orchestrator/app/domain/runtime_lifecycle.py` | `AgentSessionRuntimeLifecycleSnapshot` 派生逻辑 + runtime/session 双轴拆分 |
| `runtime/orchestrator/app/api/routes/agent_threads.py` | `AgentSessionResponse.RuntimeLifecycleSnapshotResponse` API DTO |
| `runtime/orchestrator/tests/test_runtime_adapter_fake.py` | P3-B1 25 targeted tests |
| `runtime/orchestrator/tests/test_worker_workspace_readonly_validation.py` | P2 12 tests (regression baseline) |

### AI-Dev-Orchestrator 前端

| 文件 | 用途 |
|------|------|
| `apps/web/src/features/task-actions/WorkerRuntimeLaunchGateEvidenceCard.tsx` | P3-B3 运行时启动门禁证据卡片（只读展示 gate chain + safety flags） |
| `apps/web/src/features/agents/components/AgentCodingSessionSnapshot.tsx` | P3-C1 会话运行状态卡片（运行时轴 / 会话派生轴双轴拆分 + 中文化） |

### Agent Orchestrator 参考

| 文件 | 参考要点 |
|------|---------|
| `packages/core/src/types.ts` | `CanonicalSessionLifecycle` 三元组 (session/pr/runtime)；`RuntimeHandle`；`ActivitySignal` |
| `packages/core/src/session-manager.ts` | CleanupStack LIFO undo；spawn → workspace.create → runtime.create → agent 顺序 |
| `packages/core/src/lifecycle-manager.ts` | 轮询循环 + status detection + reaction engine；PR/CI/review 状态推导 |
| `packages/core/src/lifecycle-state.ts` | `deriveLegacyStatus()` 三元组联合推导；`CanonicalSessionLifecycle` Zod schema |
| `packages/core/src/cleanup-stack.ts` | LIFO undo stack, `dismiss()` on success, `runAll()` on failure |
| `packages/plugins/workspace-worktree/src/index.ts` | `workspacePath` 作为 runtime/command seam；`destroy()`: git worktree remove --force |

---

## A. P3 阶段目标

P3 阶段的目标是 **Runtime Lifecycle 的受控闭环设计和证据链路建设**。在 P1（worktree 创建/清理）和 P2（Worker Context / Runtime Dry-run / Safe Command Proof）的基础上，P3 负责：

1. 设计 Runtime Axis 的完整生命周期状态机（P3-A）
2. 建立 RuntimeAdapter 抽象合同和 Fake Runtime 实现（P3-B）
3. 建设 Runtime Launch Gate 的证据链路——从 Worker 内部计算 → WorkerRunResult → WorkerRunOnceResponse API → 前端只读展示（P3-B2 / P3-B3）
4. 建设 AgentSession Runtime Lifecycle Snapshot——从 AgentSession 持久化字段派生运行时轴/会话轴双轴快照 → API → 前端只读展示（P3-C1）

**P3 明确不是**：
- P3 不是 AI 自动编码
- P3 不是真实 runtime launch（没有 subprocess/tmux/docker 真实进程）
- P3 不是 runtime probe（没有进程探活）
- P3 不是 PR / CI / merge 闭环

P3 的核心语义继承了 P2 的 "证明可以，但不执行"——证明 runtime adapter 合同可以有效工作、gate chain 可以正确阻断、前端可以读懂证据——但所有真实执行开关（`execution_enabled`、`launches_runtime`、`runs_real_command`、`fake_launch_started`、`real_runtime_started`、`runtime_probe_started`）全部保持 `false`。

---

## B. 当前结论

| 能力 | 结论 | 说明 |
|------|------|------|
| P3 Runtime Lifecycle Evidence | **Pass** | P3-A 设计 + P3-B 实现 + P3-C 快照全部完成 |
| RuntimeAdapter Contract + Fake Runtime | **Pass** | `RuntimeAdapter` ABC + `FakeRuntimeAdapter` 实现完成，25 targeted tests 通过 |
| Runtime Launch Gate Evidence | **Pass** | `check_runtime_launch_gates()` → `WorkerRunResult` → `WorkerRunOnceResponse` → 前端 `WorkerRuntimeLaunchGateEvidenceCard` 全链路完成 |
| Runtime Launch Gate 阻断 | **Pass** | gate 不通过 → executor 硬阻断，不调用 `executor_service.execute_task()` |
| AgentSession Runtime Lifecycle Snapshot | **Pass** | `build_agent_session_runtime_lifecycle_snapshot()` 从 AgentSession 持久化字段派生双轴快照 |
| Runtime 轴与 Session 轴拆分 | **Pass** | `AgentSessionRuntimeLifecycleSnapshot` 区分 runtime 轴（未知/存活/退出等）和 session 轴（处理中/空闲/卡住等） |
| 前端只读展示 | **Pass** | `WorkerRuntimeLaunchGateEvidenceCard` + `AgentCodingSessionSnapshot` 双组件 |
| **真实 runtime 启动** | **Not started** | 没有 subprocess/tmux/docker 真实进程创建 |
| **Runtime probe（探活）** | **Not started** | 没有 `ps`/`tmux ls`/`docker ps` 探活 |
| **AI 自动编码** | **Not started** | Agent 未进入 worktree 自主改代码 |
| **Git add / commit / push / PR 产品闭环** | **Not started** | Delivery Axis 全部未实现 |
| **AI Project Director 总闭环** | **Partial** | P1/P2/P3 全部 Pass，但 Runtime/Delivery 真实闭环未实现，Conversation Hub 未建设 |

---

## C. P3-A 完成内容

P3-A（`coding-session-runtime-lifecycle-p3a-design-20260605.md`）完成了 Runtime Axis 的完整生命周期设计。

### 运行时生命周期状态设计

六个状态，形成一条完整的状态链：

```
未探测（unknown）→ 启动中（spawning）→ 已存活（alive）→ 已退出（exited）
                                              → 已丢失（missing）
                                              → 探测失败（probe_failed）
```

- **未探测**（unknown）: 会话已创建，runtime 尚未启动——这是 P3-A 所有设计的起点
- **启动中**（spawning）: 适配器已调用 `launch()`，但第一次探活尚未返回——这是一个瞬态
- **已存活**（alive）: 探活确认进程在运行——这是唯一的正常运行态
- **已退出**（exited）: 进程已结束，exit code 已知——终态，不可恢复
- **已丢失**（missing）: 进程意外消失（如 tmux 被外部 kill）——终态，不可恢复
- **探测失败**（probe_failed）: 无法确认进程状态——唯一可恢复的非正常态，最多重试 3 次

### 运行时启动前置条件

设计了一条五道门禁链（gate chain）：

| 门禁 | 检查内容 | 依赖阶段 |
|------|---------|---------|
| G1: 工作区校验 | `workspace_context.ready` | P2-B |
| G2: 工作区上下文 | `uses_agent_workspace == True` | P2-B |
| G3: 运行时预览 | `runtime_dry_run.ready` | P2-C |
| G4: 安全命令证明 | `safe_command_proof.ready` | P2-D |
| G5: 适配器能力 | `runtime_adapter.can_launch()` | P3-B1 |

五道门禁全部通过，系统才认为 "有条件进入 runtime 阶段"。但门禁通过 ≠ runtime 已启动——这是 P3-A 的核心设计原则。

### 运行时句柄绑定原则

`runtime_handle_id` 只是一个标识符，**不等于进程已存活**。它的含义：

- 格式：`<类型>:<值>`，例如 `fake:pid:90001`、`pid:48291`、`tmux:aido-abc123`
- 填充时机：`RuntimeAdapter.launch()` 成功返回后
- 有 handle ≠ alive ——需要 `is_alive()` 探活结果来确认

### blocked / failed / exited / missing / probe_failed 的设计方向

每个状态都有明确的回写目标：

| 状态 | 会话编码状态 | 会话活动状态 | 是否终态 |
|------|------------|------------|---------|
| 启动中 | 正在准备 | 有新动作 | 否（瞬态） |
| 已存活 | 正在处理 | 有新动作 | 否（正常） |
| 已退出（正常） | 任务已完成 | 本轮已结束 | **是** |
| 已退出（异常） | 任务失败 | 本轮已结束 | **是** |
| 已丢失 | 已停止 | 本轮已结束 | **是** |
| 探测失败 | 需要关注 | 遇到阻塞 | 否（可恢复） |

### 与 P2 安全命令证明的关系

P2-D 的 `WorkerWorktreeSafeCommandProof` 是 P3 gate chain 的**第四道门禁（G4）**。只有当 `pwd` 证明 `observed_pwd == workspace_path` 时，G4 才通过。这是 runtime launch 启动前的最后一道安全验证——P2 的 "证明可以，但不执行" 在 P3 中变成了 "门禁通过，但 runtime 尚未启动"。

---

## D. P3-B 完成内容

P3-B 将 P3-A 的设计实现为可工作的代码合同和证据链路。

### RuntimeAdapter 合同已建立

文件：`runtime/orchestrator/app/workers/runtime_adapter.py`

抽象基类 `RuntimeAdapter` 定义了四个标准方法：

```python
class RuntimeAdapter(ABC):
    def adapter_kind(self) -> str: ...
    def can_launch(self, *, agent_type, runtime_type) -> bool: ...
    def launch(self, *, request: RuntimeLaunchRequest) -> RuntimeLaunchResult: ...
    def is_alive(self, *, handle: RuntimeHandle) -> RuntimeProbeResult: ...
    def kill(self, *, handle: RuntimeHandle) -> RuntimeProbeResult: ...
```

这个合同使得未来可以用 `SubprocessRuntimeAdapter`、`TmuxRuntimeAdapter`、`DockerRuntimeAdapter` 替换当前实现，而不改变 Worker 的调用代码。

### FakeRuntimeAdapter 只做证据模拟

`FakeRuntimeAdapter` 是当前唯一的合同实现，它的核心约定：

- `launch()` 不调用 `subprocess.Popen`，不创建真实进程——只返回 `fake:pid:90001` 格式的句柄
- `is_alive()` 不运行 `ps`/`tmux ls`/`docker ps`——默认返回 `alive`，可通过 `set_probe_result()` 覆盖来控制测试状态
- `kill()` 不发 OS 信号（SIGTERM/SIGKILL）——只返回 `exited` 状态
- 所有方法都是纯内存操作，不接触文件系统、进程表、网络

### run_fake_runtime_simulation 已被限制只能接受 FakeRuntimeAdapter

`run_fake_runtime_simulation()` 函数把 gate chain + fake launch 连成一条完整的参考流程：

1. 调用 `check_runtime_launch_gates()` 逐门禁验证
2. 门禁不通过 → 返回 gate 结果，不执行 launch
3. 门禁全通过 → 调用 `runtime_adapter.launch()` —— 但 P3-B1 提供的适配器永远是 `FakeRuntimeAdapter`

真实 runtime 的启动被 `execution_enabled=False` 硬限制在 P3+ 阶段。

### 门禁证据已接入 WorkerRunResult / WorkerRunOnceResponse

文件：`runtime/orchestrator/app/workers/task_worker.py`（L177–L188）
文件：`runtime/orchestrator/app/api/routes/workers.py`

`WorkerRunResult` 新增了完整的 runtime launch gate evidence 字段：

| 字段 | 含义 |
|------|------|
| `runtime_launch_gate_ready` | 门禁链全部通过？ |
| `runtime_launch_gate_gates_passed` | 已通过的门禁名称列表 |
| `runtime_launch_gate_gates_failed` | 失败的门禁名称列表 |
| `runtime_launch_gate_blocking_reason_code` | 第一个失败门禁的原因码 |
| `runtime_launch_gate_blocking_summary` | 人类可读的阻断说明 |
| `runtime_launch_gate_changes_process_cwd` | 门禁是否改变进程目录？**固定 false** |
| `runtime_launch_gate_runs_real_command` | 门禁是否执行真实命令？**固定 false** |
| `runtime_launch_gate_runs_git` | 门禁是否执行 git？**固定 false** |
| `runtime_launch_gate_runs_write_git` | 门禁是否执行写 git？**固定 false** |
| `runtime_launch_gate_launches_ai_runtime` | 门禁是否启动 AI 运行时？**固定 false** |
| `runtime_launch_gate_execution_enabled` | 真实执行是否开启？**固定 false** |
| `runtime_lifecycle_snapshot` | P3-C1 的完整快照对象 |

这些字段通过 `WorkerRunOnceResponse` API 全部透传给前端。

### 门禁失败会在 executor 前硬阻断

在 `TaskWorker.run_once()` 中，`check_runtime_launch_gates()` 的结果决定了是否允许进入 executor 调用链。门禁失败时：

- 任务状态设为 `BLOCKED`
- Run 状态设为 `CANCELLED`
- failure_category 设为 `EXECUTION_FAILED`
- `executor_service.execute_task()` 不会被调用
- 阻断摘要写入 `last_workspace_error`

这是在 P2-D（safe command proof 阻断 executor）的基础上，将阻断条件从 "一项 proof 失败" 升级为 "五道门禁任一失败"。

### 前端已展示运行时门禁证据

文件：`apps/web/src/features/task-actions/WorkerRuntimeLaunchGateEvidenceCard.tsx`

前端 `WorkerRuntimeLaunchGateEvidenceCard` 组件展示三个区域的只读证据：

1. **上下文区**（Context Fields）: AgentSession ID、智能体和运行载体、运行时句柄、编码/活动状态、工作区上下文状态
2. **门禁链区**（Gate Chain Evidence）: 已通过的门禁列表、失败的门禁列表、阻断原因码、阻断摘要
3. **安全标志区**（Safety Flags）: 以 "Safety Flags (all false means no launch)" 形式展示所有执行开关

门禁状态有三种展示：

- **受控阻断**（Controlled Blocked）: 红色，门禁失败 → "该阻断是设计行为，不是系统崩溃。"
- **门禁通过（仅门禁）**（Ready — gates only）: 绿色，门禁全通过 → "所有门禁已通过，但这只表示前置条件就绪；模拟启动和真实运行时均未触发。"
- **未收到证据**（Evidence not received）: 灰色，Worker 响应中没有门禁数据

---

## E. P3-C 完成内容

P3-C 将 runtime lifecycle 快照能力从 Worker 内部（P3-B）扩展到 AgentSession 持久化层（P3-C1），让前端可以在 Worker 运行之外、通过 AgentSession API 直接读取运行时生命周期状态。

### 新增 AgentSession Runtime Lifecycle Snapshot

文件：`runtime/orchestrator/app/domain/runtime_lifecycle.py`

`AgentSessionRuntimeLifecycleSnapshot` 是一个纯证据域模型。它从 AgentSession 的持久化字段（`agent_type`、`runtime_type`、`runtime_handle_id`、`coding_status`、`activity_state`）派生运行时轴和会话轴的双轴快照，而不导入任何 Worker 运行时适配器。

核心原则：
- **不启动**——不调用 FakeRuntimeAdapter.launch()
- **不探测**——不调用 RuntimeAdapter.is_alive()
- **不改变**——不修改 AgentSession 的任何字段
- **只派生**——从已有数据推导可展示的状态

### 运行时轴和会话状态轴已拆分

P3-C1 明确区分了两个独立的轴：

**运行时轴**（Runtime Axis）—— `state` + `reason`：
- 状态永远是 `unknown`（未探测）
- 原因有三种：`handle_not_assigned`（尚未分配运行时句柄）、`handle_recorded_no_probe`（已有句柄记录，但本阶段未做探测）、`snapshot_only_no_runtime_probe`（仅基于会话记录生成快照，未做运行时探测）

**会话派生轴**（Session Derived Axis）—— `session_lifecycle_state` + `session_lifecycle_reason`：
- 从 `coding_status` 和 `activity_state` 派生，不使用 `agent_session.status`
- 七个状态：未开始（not_started）、处理中（working）、空闲（idle）、等待输入（needs_input）、卡住（stuck）、已完成（done）、已终止（terminated）

双轴分离的意义：运行时轴如实暴露 "未探测" 的事实，不会被会话处理状态（如 `coding_status=completed`）掩盖。用户看到 "运行时轴：未探测；会话派生状态：处理中" 就知道——编码状态显示在处理中，但运行时本身没有经过探测。

### P3-C1 不做 runtime probe

所有安全标志硬编码为 `false`：

```python
runtime_probe_started=False
fake_launch_started=False
real_runtime_started=False
execution_enabled=False
launches_ai_runtime=False
runs_real_command=False
changes_process_cwd=False
runs_git=False
runs_write_git=False
```

`runtime_handle_id` 只表示 "AgentSession 记录了一个运行时句柄"（`runtime_handle_recorded = True`），不表示 "运行时已验证存活"。前端展示时会用红色/黄色/绿色三色区分：有句柄的记录是有风险的信号（因为无法确认是否存活），没有句柄的记录是安全的（因为没有声称启动了 runtime）。

### 前端用户可见文案已中文化

文件：`apps/web/src/features/agents/components/AgentCodingSessionSnapshot.tsx`

前端已经完整覆盖了中文化标签映射：

| 英文枚举 | 中文展示 |
|---------|---------|
| `unknown` | 运行时未探测 |
| `alive` | 运行时已确认存活 |
| `exited` | 运行时已确认退出 |
| `missing` | 运行时句柄丢失 |
| `probe_failed` | 运行时探测失败 |
| `handle_not_assigned` | 尚未分配运行时句柄 |
| `handle_recorded_no_probe` | 已有运行时句柄记录，但本阶段未做探测 |
| `snapshot_only_no_runtime_probe` | 仅基于会话记录生成快照，未做运行时探测 |
| `session not_started` | 会话未开始 |
| `session working` | 会话处理中 |
| `coding completed` | 编码会话已完成 |
| `coding stuck` | 编码会话需要关注 |

组件底部的中文声明完整说明了双轴拆分的含义：
> "当前阶段只读展示智能体会话与时间线已有数据……P3-C1 的运行时轴只展示已有证据；未启动或未探测时不会把会话处理状态误标为运行时存活。"

---

## F. 当前已形成的证据链

从 P1 到 P3，以下 evidence 链路已经完整形成（按 Worker 执行顺序）：

### 1. AgentSession 工作区绑定
**文件**: `agent_session.py` → `workspace_type`、`workspace_path`、`workspace_clean`、`branch_name`
**说明**: P1 通过 `WorktreeCreateService` 在创建 worktree 后写回 AgentSession；cleanup 时通过 `mark_workspace_cleaned()` 解绑。

### 2. Worker 工作区上下文
**文件**: `task_worker.py` → `validate_worker_agent_workspace()` + `resolve_worker_workspace_context()`
**字段**: `workspace_context_ready`、`workspace_context_source`、`workspace_context_uses_agent_workspace` 等 10 个字段
**说明**: Worker 在执行前只读校验 AgentSession 的工作区元数据——路径存在、绝对路径、目录类型、工作区干净。

### 3. 运行时启动预览
**文件**: `task_worker.py` → `build_worker_runtime_launch_dry_run()`
**字段**: `runtime_launch_dry_run_ready`、`runtime_launch_dry_run_launch_cwd_preview`、`runtime_launch_dry_run_launch_command_preview` 等 18 个字段
**说明**: 生成 `RuntimeCreateConfig(...)` 预览字符串，证明未来的 runtime 能绑定到 worktree。`execution_enabled=False`。

### 4. 工作区安全命令证明
**文件**: `worktree_safe_command.py` → `WorkerWorktreeSafeCommandProofRunner.run_probe()`
**字段**: `worktree_safe_command_proof_ready`、`worktree_safe_command_proof_observed_pwd`、`worktree_safe_command_proof_pwd_matches_workspace_path` 等 21 个字段
**说明**: 执行唯一的 allowlisted `pwd` 命令，验证 `observed_pwd == AgentSession.workspace_path`。

### 5. 运行时启动门禁
**文件**: `runtime_adapter.py` → `check_runtime_launch_gates()`
**字段**: `runtime_launch_gate_ready`、`runtime_launch_gate_gates_passed`、`runtime_launch_gate_gates_failed` 等 12 个字段
**说明**: 串联 G1–G5 五道门禁，任一失败即阻断。`execution_enabled=False`。

### 6. WorkerRunResult / WorkerRunOnceResponse 证据
**文件**: `task_worker.py` → `WorkerRunResult`；`workers.py` → `WorkerRunOnceResponse`
**说明**: 所有 P3 evidence 字段在 Worker 内部通过 `WorkerRunResult` 收集，通过 `WorkerRunOnceResponse` API DTO 暴露给前端。

### 7. 前端 Worker 证据卡片
**文件**: `WorkerRuntimeLaunchGateEvidenceCard.tsx`
**说明**: 三个区域的只读展示——上下文区、门禁链区、安全标志区。所有执行开关用绿色（false = 安全）和红色（true = 风险）区分。

### 8. AgentSession 运行时生命周期快照
**文件**: `runtime_lifecycle.py` → `build_agent_session_runtime_lifecycle_snapshot()`
**说明**: 从 AgentSession 持久化字段派生双轴快照，不依赖 Worker。

### 9. 前端 AgentSession 运行时快照
**文件**: `AgentCodingSessionSnapshot.tsx`
**说明**: 在 Agent 线程页面展示双轴状态。运行时轴独立展示 "未探测" 或 "已记录句柄但未探测"；会话派生轴展示 "处理中/已完成/卡住" 等状态。

---

## G. 安全边界

P3 阶段的全部安全开关当前状态（逐条写明）：

| 安全开关 | 当前值 | 位置 | 含义 |
|---------|--------|------|------|
| `execution_enabled` | **false** | `RuntimeLaunchGateResult` + `RuntimeLifecycleSnapshot` | 真实执行尚未开启 |
| `launches_ai_runtime` | **false** | `RuntimeLaunchGateResult` + `RuntimeLifecycleSnapshot` + `WorkerRuntimeLaunchDryRun` | 未启动任何 AI 运行时 |
| `runs_real_command` | **false** | `RuntimeLaunchGateResult` + `RuntimeLifecycleSnapshot` | 未执行任何真实命令 |
| `runs_git` | **false** | `RuntimeLaunchGateResult` + `RuntimeLifecycleSnapshot` | 未执行任何 git 命令 |
| `runs_write_git` | **false** | `RuntimeLaunchGateResult` + `RuntimeLifecycleSnapshot` | 未执行任何 git 写命令 |
| `changes_process_cwd` | **false** | `RuntimeLaunchGateResult` + `RuntimeLifecycleSnapshot` | 未改变进程工作目录 |
| `fake_launch_started` | **false** | `RuntimeLifecycleSnapshot` + `AgentSessionRuntimeLifecycleSnapshot` | 未触发模拟启动 |
| `real_runtime_started` | **false** | `RuntimeLifecycleSnapshot` + `AgentSessionRuntimeLifecycleSnapshot` | 未启动真实 runtime |
| `runtime_probe_started` | **false** | `RuntimeLifecycleSnapshot` + `AgentSessionRuntimeLifecycleSnapshot` | 未启动运行时探测 |

额外禁区（全阶段统一）：

- 不启动 Claude Code / Codex / DeepSeek / OpenCode
- 不让 AI runtime 进入 worktree
- 不创建 PR
- 不提交业务代码变更
- 不创建 / 删除 worktree（P1 已完成的除外）
- 不创建 / 删除 branch（P1 已完成的除外）
- 不改变 executor_service.execute_task() 的 cwd / 入参

---

## H. 参考 Agent Orchestrator 的机制

AI-Dev-Orchestrator 在 P3 阶段的设计和实现中，重点参考了 ComposioHQ Agent Orchestrator 的以下思路，但保持了完整的独立性。

### 参考了的机制

| AO 机制 | 学习要点 | AI-Dev 对应实现 |
|---------|---------|---------------|
| **session / runtime 分轴** | `CanonicalSessionLifecycle` 将 session/pr/runtime 三个维度分开记录，独立推导 | P3-C1 的 `AgentSessionRuntimeLifecycleSnapshot` 明确将 runtime 轴和 session 派生轴拆分为两个独立字段组 |
| **lifecycle state 分层** | `CanonicalSessionState` 和 `CanonicalRuntimeState` 是两个独立的类型，不是同一个枚举的不同值 | `RuntimeLifecycleState`（P3-B1）和 `AgentSessionDerivedLifecycleState`（P3-C1）是两个独立枚举 |
| **runtime handle 只是身份标识** | `RuntimeHandle` 是 `{id, runtimeName, data}` 的结构体，不等于 `isAlive()` 的结果 | `RuntimeHandle` 只记录 `handle_kind:handle_value`；探活需要单独调用 `is_alive()`，P3 阶段不调用 |
| **gate / preflight / evidence 分层** | AO 的 `LifecycleManager.determineStatus()` 先收集 PR/CI/review 数据，再推导状态——gate 收集证据，transition 触发动作 | `check_runtime_launch_gates()` 收集 5 道门禁的证据 → 返回 gate 结果 → Worker 决定是否继续——门禁和动作是分开的 |
| **workspace path 作为 runtime cwd seam** | `RuntimeCreateConfig.workspacePath` 是 runtime 启动的关键参数 | `RuntimeLaunchRequest.workspace_path` 和 `WorkerRuntimeLaunchDryRun.launch_cwd_preview` 复用了同一设计原则 |
| **cleanup stack / rollback** | `CleanupStack` 用 LIFO 栈管理副作用回滚：成功时 dismiss，失败时 runAll | P3 阶段暂未实现 CleanupStack，但 P3-A 设计已将其列为 P3-B 的必备特性（P1 的已知缺口） |

### 没有照搬的内容

| AO 内容 | 为什么不照搬 |
|---------|------------|
| 插件架构 (`PluginModule`/`PluginManifest`/8 类 slot) | AI-Dev 不需要插件系统；runtime adapter 通过 Python ABC 合同管理 |
| Node.js / TypeScript 技术栈 | AI-Dev 用 Python + FastAPI + SQLite |
| Next.js dashboard / CLI `ao` 工具 | AI-Dev 有自己的 React 前端和 web-first API |
| tmux 作为默认 runtime | P3 阶段不做真实 runtime launch |
| `Runtime.create()` 真实进程创建 + `sendMessage()` | P3 阶段只做 fake simulation |
| `LifecycleManager` 轮询循环 + reaction engine | P3 阶段没有真实进程可轮询 |
| `ActivitySignal` (native/terminal/hook 三层探活) | P3 阶段不做 runtime probe |
| SCM integration (PR/CI/review) | Delivery Axis 属于 P4+ |

---

## I. 仍然没有开始的能力

以下能力在 P3 收口时明确为 **Not started**：

| # | 能力 | 说明 |
|---|------|------|
| 1 | **真实 runtime launch** | 没有 subprocess/tmux/docker 进程创建 |
| 2 | **SubprocessRuntimeAdapter** | `RuntimeAdapter` 只有一个实现：`FakeRuntimeAdapter` |
| 3 | **TmuxRuntimeAdapter** | 未实现 |
| 4 | **DockerRuntimeAdapter** | 未实现 |
| 5 | **Runtime liveness probe** | 没有 `ps` / `tmux ls` / `docker ps` 探活 |
| 6 | **Runtime process missing 检测** | 无法检测运行时进程意外消失 |
| 7 | **Runtime exited / probe_failed 真实回写** | 没有 `record_runtime_state_change()` 实现 |
| 8 | **AI 自动改代码** | Agent 未进入 worktree 自主编码 |
| 9 | **git add / commit / push** | Delivery Axis 全部未实现 |
| 10 | **PR 创建与审核** | 无 SCM 集成 |
| 11 | **CI / review / merge loop** | 无异步轮询 |
| 12 | **Project Director Conversation Hub** | 工作台对话中枢未建设 |
| 13 | **CleanupStack / rollback** | P1 已知缺口，P3 仍未补齐 |
| 14 | **Runtime lifecycle event / audit 落 AgentMessage** | P3-A 设计了 `runtime_*` event 类型，但未实现 |

---

## J. 为什么不能把 AI Project Director 总闭环标为 Pass

引用 `gap-analysis/ai-project-director-ideal-gap-after-p1-20260605.md` 的核心结论：

> 即使 session / worktree / lifecycle / cleanup 这些机制继续补齐，它们也不会自然长成理想 AI 主管体验。这些机制是必要条件，但不是充分条件。

P3 完成了 Runtime Lifecycle 的受控证据链路——设计（P3-A）、合同（P3-B1）、证据（P3-B2）、前端展示（P3-B3）、快照（P3-C1）。但：

1. **Runtime Axis 的真实执行未落地** — 没有真实进程、没有探活、没有退出检测。`runtime_lifecycle_state` 永远是 `unknown`。
2. **Delivery Axis 全部未实现** — 没有 git push、PR、CI、review、merge。
3. **Worker ↔ AgentSession ↔ Runtime 的三向关系** — P3 建立了证据链，但 "进程退了 → 自动更新会话状态 → 触发复盘" 这个闭环还是没有。
4. **Project Director Conversation Hub 完全未建设** — 工作台仍然缺少持续对话、跨页面消息路由、上下文汇总、提案审批应用等中枢能力。仅靠 session / worktree / runtime / lifecycle 机制不会自然长出 "像 GPT 一样持续讨论、可质疑、可影响计划的 AI 项目主管"。

**结论: AI Project Director 总闭环仍为 Partial。** 只有当 Runtime Axis 完成真实闭环（P4+）、Delivery Axis 完成 PR/CI 闭环（P5+）、且 Project Director Conversation Hub 建成后，总闭环才有条件从 Partial 升级。

---

## K. 下一阶段建议

建议不直接进入 AI 自动编码（真实 runtime launch），而是先在以下方向继续收口：

### P3-D：Runtime Lifecycle Event / Audit 只读事件落点设计

**范围**: 设计文档，不改代码
- 定义 `runtime_spawning`、`runtime_alive`、`runtime_exited`、`runtime_missing`、`runtime_probe_failed` 等事件类型
- 定义每种事件的 `AgentMessage` 写入格式（`event_type`、`content_summary`、`content_detail` JSON 结构）
- 定义与 `RunLog` 的双通道审计模式
- 参考 AO 的 `recordActivityEvent()` 模式

### P3-E：Fake Runtime Lifecycle Simulation 前后端闭环展示

**范围**: 前端 + 可能的 API 适配
- 将 P3-B3 的 Worker 证据卡片和 P3-C1 的 AgentSession 快照合并为统一的 "Runtime Lifecycle 总览面板"
- 设计 runtime 轴的 phase transition 可视化
- 考虑新增一个专用的 runtime lifecycle API（`GET /agent-sessions/{id}/runtime-lifecycle`）

### P3-F：真实 Runtime 启动前 Guardrail 文档和 Feature Flag

**范围**: 设计文档 + 可能的配置
- 定义 `execution_enabled` 从 `false` 翻转为 `true` 的显式 feature flag
- 定义 feature flag 的修改审计要求（需要用户确认、需要记录变更事件）
- 定义真实 runtime 启动的最小安全契约（adapter 必须通过 can_launch、必须记录 launch event、必须在 launch 失败时回滚）

### P4：Git add / commit / push / PR 产品闭环设计

**范围**: 设计文档
- Delivery Axis 的状态机设计
- PR 创建/审核/合并的 SCM 集成设计

### Conversation Hub：AI Project Director 对话中枢

**范围**: 设计文档 → 实现
- 从 gap analysis 的 P7 路线切入
- 建设 `ProjectDirectorConversation`、`ConversationList`、`Inbox`、`Router`、`ContextAssembler`

---

## 附录 A: P3 提交历史

| Commit | 说明 |
|--------|------|
| `711bc6c` | feat: add P3-B1 fake runtime adapter contract |
| `e5116d1` | test: harden P3-B1 fake runtime simulation safety |
| `5d38c82` | feat: expose runtime launch gate evidence |
| `81afa58` | fix: block executor on runtime launch gate failure |
| `f08a2f1` | feat: display P3-B3 runtime launch gate evidence |
| `797ab0d` | fix: clarify runtime gate evidence copy |
| `64806af` | feat: add P3-C1 runtime lifecycle snapshot |
| `8df0eac` | fix: expose P3-C1 AgentSession runtime lifecycle snapshot |
| `8336b04` | fix: clarify P3-C1 runtime lifecycle states |
| `5b9e4ed` | fix: localize P3-C1 runtime lifecycle user copy |

---

## 附录 B: 测试结果

### P3-B1 targeted tests (25 tests)

```
runtime/orchestrator/.venv/bin/pytest runtime/orchestrator/tests/test_runtime_adapter_fake.py -q
25 passed
```

### P2 regression (12 tests)

```
runtime/orchestrator/.venv/bin/pytest runtime/orchestrator/tests/test_worker_workspace_readonly_validation.py -q
12 passed
```

---

## 附录 C: Gate 结论

| Gate | 结论 |
|------|------|
| P3 Runtime Lifecycle Evidence | **Pass** |
| P3-A 设计收口 | **Design Complete** |
| P3-B RuntimeAdapter Contract + Fake Runtime | **Pass** |
| P3-B2 Gate Evidence → WorkerRunResult/WorkerRunOnceResponse | **Pass** |
| P3-B3 Gate Evidence 前端只读展示 | **Pass** |
| P3-C1 AgentSession Runtime Lifecycle Snapshot | **Pass** |
| P3-C1-R2 Runtime 轴与会话状态轴拆分 | **Pass** |
| P3-C1-R3 用户可见文案中文化 | **Pass** |
| 真实 runtime 启动 | **Not started** |
| Runtime probe | **Not started** |
| AI 自动编码 | **Not started** |
| Git add / commit / push / PR 产品闭环 | **Not started** |
| **AI Project Director 总闭环** | **Partial** |

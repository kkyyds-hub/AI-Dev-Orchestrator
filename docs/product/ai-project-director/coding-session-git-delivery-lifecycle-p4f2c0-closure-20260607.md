# Coding Session Git Delivery Lifecycle P4-F2-C0 Delivery Evidence Snapshot Source 收口

> **文档类型**: P4-F2-C0 阶段收口审计 + Gate 证据  
> **生成日期**: 2026-06-07  
> **远端基准**: `origin/main` = `a0b8ffb0463bbc5b43a7da0ac682f751e59191a1`  
> **P4-F2-C0 实现 commit**: `a0b8ffb0463bbc5b43a7da0ac682f751e59191a1` (`fix: guard P4-F2C delivery evidence snapshot writes`)  
> **路线文档**: `docs/product/ai-project-director/p1-p7参考规划复用说明书.md`  
> **前置 closure 文档**: `docs/product/ai-project-director/coding-session-git-delivery-lifecycle-p4f2b-human-approval-api-design-20260606.md`  
> **边界**: 本轮只做 P4-F2-C0 收口复核与文档回填；不改 Python 业务代码、不改 API、不改 Worker、不改前端、不改数据库 / migration、不写 AgentMessage、不实现 approval API、不实现确认按钮、不实现产品运行时 Git 写操作。  
> **状态**: P4-F2-C0 Closure: Pass；P4-F2-C Approval API: Not started；P4-F3: Not started；AI Project Director 总闭环: Partial

---

## 0. 阶段定位

P4-F2-C0 是 P4-F2（Human Approval Passthrough）的证据缓存基础设施。它在当前的 run log JSONL 中建立一个稳定的只读证据快照，使后续 P4-F2-C Approval API 可以直接从 run log 读取 P4-C operation dry-run 和 P4-D delivery gate evidence，而不需要重新扫描 Git 或依赖内存中的 WorkerRunResult。

### 0.1 为什么需要 P4-F2-C0

P4-F2-B 设计文档在第 5.2 节指出了关键风险：

```text
⚠ 当前 P4-C / P4-D evidence 主要存在于 WorkerRunResult / run-once response 内存中。
API 实现 P4-F2-C 前必须明确 evidence persistence / snapshot 来源。
```

P4-F2-C0 直接解决这个风险：在 Worker 成功执行后，将 P4-C / P4-D evidence 以结构化快照的形式写入 run log JSONL 文件。后续 P4-F2-C Approval API 可以通过 `read_latest_delivery_evidence_snapshot()` 读取这个快照，作为 `HumanApprovalGateBuilder.evaluate()` 的输入。

### 0.2 本阶段范围

| 项目 | 状态 |
|------|------|
| snapshot event contract 常量定义 | Pass |
| `append_delivery_evidence_snapshot()` 写入方法 | Pass |
| `read_latest_delivery_evidence_snapshot()` 读取方法 | Pass |
| Worker 写入 guard（三重空值检查） | Pass |
| snapshot data 包含完整 P4-C/P4-D evidence | Pass |
| 所有 Git 写操作安全标志均为 False | Pass |
| targeted tests | Pass |

### 0.3 本阶段明确不做

| 项目 | 状态 |
|------|------|
| 调用 `HumanApprovalGateBuilder.evaluate()` | 不做 |
| 生成 human approval evidence | 不做 |
| 实现 approval API | 不做（P4-F2-C） |
| 写 AgentMessage | 不做（P4-F2-D） |
| 前端确认按钮 | 不做（P4-F3） |
| 产品运行时 Git 写操作 | 不做 |
| 重扫 Git | 不做 |
| 信任前端 evidence | 不做 |

---

## 1. 基准提交

| 项目 | 值 |
|------|-----|
| 当前 `origin/main` hash | `a0b8ffb0463bbc5b43a7da0ac682f751e59191a1` |
| 当前 `origin/main` commit message | `fix: guard P4-F2C delivery evidence snapshot writes` |

---

## 2. Snapshot Event Contract

### 2.1 常量定义

文件：`runtime/orchestrator/app/services/run_logging_service.py`（第 18–21 行）

```python
DELIVERY_EVIDENCE_SNAPSHOT_EVENT = "delivery_evidence_snapshot"
DELIVERY_EVIDENCE_SNAPSHOT_SCHEMA_VERSION = "p4f2c0.v1"
DELIVERY_EVIDENCE_SNAPSHOT_SOURCE_RUN_LOG_JSONL = "run_log_jsonl"
DELIVERY_EVIDENCE_SNAPSHOT_MESSAGE = (
    "记录交付前只读证据快照：提交预览与交付前检查已生成，尚未执行提交或推送。"
)
```

| 常量 | 值 | 说明 |
|------|-----|------|
| `DELIVERY_EVIDENCE_SNAPSHOT_EVENT` | `"delivery_evidence_snapshot"` | JSONL event type 标识 |
| `DELIVERY_EVIDENCE_SNAPSHOT_SCHEMA_VERSION` | `"p4f2c0.v1"` | snapshot data schema 版本 |
| `DELIVERY_EVIDENCE_SNAPSHOT_SOURCE_RUN_LOG_JSONL` | `"run_log_jsonl"` | snapshot 存储介质声明 |
| `DELIVERY_EVIDENCE_SNAPSHOT_MESSAGE` | `"记录交付前只读证据快照：提交预览与交付前检查已生成，尚未执行提交或推送。"` | 用户可见中文文案 |

### 2.2 中文文案审计

`DELIVERY_EVIDENCE_SNAPSHOT_MESSAGE` 包含以下关键语义：

| 语义 | 是否正确 |
|------|---------|
| "记录交付前只读证据快照" | ✅ 明确是只读快照 |
| "提交预览与交付前检查已生成" | ✅ 仅表示 evidence 已生成 |
| "尚未执行提交或推送" | ✅ 明确否定事实 |
| 不包含"代码已提交/已推送/PR已创建/审批已通过"等误导文案 | ✅ 审计通过 |

---

## 3. 写入方法

### 3.1 `append_delivery_evidence_snapshot()`

文件：`runtime/orchestrator/app/services/run_logging_service.py`（第 230–282 行）

```python
def append_delivery_evidence_snapshot(
    self,
    *,
    log_path: str | None,
    run_id: UUID,
    operation_dry_run: Any | None,
    delivery_gate_evidence: Any | None,
) -> None:
```

### 3.2 写入 Guard（三重空值检查）

```python
if (
    log_path is None
    or operation_dry_run is None
    or delivery_gate_evidence is None
):
    return
```

| Guard | 含义 | 行为 |
|-------|------|------|
| `log_path is None` | run log 文件未创建 | 不写 |
| `operation_dry_run is None` | P4-C evidence 不存在 | 不写 |
| `delivery_gate_evidence is None` | P4-D evidence 不存在 | 不写 |

三个条件**全部满足**（即全部非 None）才会写入快照。任何一个缺失都会静默跳过。

### 3.3 Snapshot Data 结构

写入的 `data` 字典包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | `"p4f2c0.v1"` | 固定 schema 版本 |
| `snapshot_source` | `"run_log_jsonl"` | 存储介质声明 |
| `purpose` | `"delivery_human_approval_evidence_source"` | 快照使用目的 |
| `run_id` | `str` | 关联的 run UUID |
| `operation_dry_run_available` | `bool` | P4-C evidence 是否存在 |
| `operation_dry_run_ready` | `bool \| None` | P4-C evidence ready 状态 |
| `delivery_gate_evidence_available` | `bool` | P4-D evidence 是否存在 |
| `delivery_gate_evidence_ready` | `bool \| None` | P4-D evidence ready 状态 |
| `operation_dry_run` | `dict \| None` | P4-C evidence 完整 `model_dump(mode="json")` |
| `delivery_gate_evidence` | `dict \| None` | P4-D evidence 完整 `model_dump(mode="json")` |
| `human_approval_evaluated` | `False` | **未调用** HumanApprovalGateBuilder.evaluate() |
| `approval_record_created` | `False` | **未创建** HumanApprovalRecord |
| `runs_write_git` | `False` | 未执行写 Git |
| `git_add_triggered` | `False` | 未触发 `git add` |
| `git_commit_triggered` | `False` | 未触发 `git commit` |
| `git_push_triggered` | `False` | 未触发 `git push` |
| `pr_opened` | `False` | 未创建 PR |
| `ci_triggered` | `False` | 未触发 CI |
| `gate_allows_write` | `False` | 未授权写仓库 |

### 3.4 辅助函数

| 函数 | 位置 | 作用 |
|------|------|------|
| `_snapshot_payload()` | `run_logging_service.py` L318–330 | 将 Pydantic model 或 dict 转换为 JSON 兼容的 dict |
| `_value()` | `run_logging_service.py` L333–338 | 从 model/dict/object 安全读取字段值 |

---

## 4. 读取方法

### 4.1 `read_latest_delivery_evidence_snapshot()`

文件：`runtime/orchestrator/app/services/run_logging_service.py`（第 141–178 行）

```python
def read_latest_delivery_evidence_snapshot(
    self,
    *,
    log_path: str | None,
) -> RunLogEvent | None:
```

### 4.2 读取逻辑

1. 如果 `log_path is None` → 返回 `None`
2. 如果 log 文件不存在 → 返回 `None`
3. 从文件末尾**反向遍历** JSONL 行
4. 找到第一个 `event == "delivery_evidence_snapshot"` 的行
5. 返回该 `RunLogEvent`（包含 `timestamp`、`event`、`message`、`data`）
6. 如果未找到任何 snapshot event → 返回 `None`

### 4.3 返回值

| 返回值 | 含义 |
|--------|------|
| `RunLogEvent` | 最新的一条 snapshot event，`data` 字段包含完整 P4-C/P4-D evidence |
| `None` | 无 log_path、文件不存在、或文件中无 snapshot event |

### 4.4 与 P4-F2-C Approval API 的关系

P4-F2-C 实现时，Approval API 调用流程：

```text
1. API handler 接收 POST /runs/{run_id}/delivery-human-approval
2. 从 run 获取 log_path
3. 调用 read_latest_delivery_evidence_snapshot(log_path=log_path)
4. 如果返回 None → 返回 ready=False, reason_code="delivery_evidence_snapshot_missing"
5. 从 snapshot event.data 中提取:
   - operation_dry_run → 构造 GitOperationDryRunResult
   - delivery_gate_evidence → 构造 DeliveryGateEvidenceResult
6. 从 agent_session 获取 session 上下文
7. 调用 HumanApprovalGateBuilder.evaluate(...)
8. 返回 DeliveryHumanApprovalResponse
```

---

## 5. Worker 写入条件

### 5.1 写入位置

文件：`runtime/orchestrator/app/workers/task_worker.py`（第 2959–2969 行）

```python
if (
    execution_quality_passed
    and git_operation_dry_run_result is not None
    and delivery_gate_evidence_result is not None
):
    self.run_logging_service.append_delivery_evidence_snapshot(
        log_path=run.log_path,
        run_id=run.id,
        operation_dry_run=git_operation_dry_run_result,
        delivery_gate_evidence=delivery_gate_evidence_result,
    )
```

### 5.2 写入条件（三重 AND）

| 条件 | 含义 | 不满足时的行为 |
|------|------|-------------|
| `execution_quality_passed` is truthy | Worker 执行成功且质量门通过 | 不写（执行失败或质量门未通过） |
| `git_operation_dry_run_result is not None` | P4-C evidence 已生成 | 不写（P4-C 未就绪） |
| `delivery_gate_evidence_result is not None` | P4-D evidence 已生成 | 不写（P4-D 未就绪） |

### 5.3 不在以下 Worker 路径写入

| Worker 路径 | 是否写入 snapshot | 原因 |
|------------|------------------|------|
| 无 pending task (claimed=False) | 否 | 无 run，无 log_path |
| budget guard blocked | 否 | 执行未发生 |
| workspace validation blocked | 否 | `execution_quality_passed` 不满足 |
| worktree safe command proof blocked | 否 | `execution_quality_passed` 不满足 |
| runtime launch gate blocked | 否 | `execution_quality_passed` 不满足 |
| execution failed | 否 | `execution_quality_passed` 不满足 |
| execution succeeded but P4-C/P4-D evidence 未生成 | 否 | `git_operation_dry_run_result is None` 或 `delivery_gate_evidence_result is None` |
| execution succeeded + P4-C + P4-D 全部就绪 | **是** | 唯一写入路径 |

---

## 6. 测试证据

### 6.1 测试文件

`runtime/orchestrator/tests/test_run_logging_service_delivery_evidence_snapshot.py`

### 6.2 测试命令与结果（上一轮记录）

```bash
cd runtime/orchestrator
python -m pytest tests/test_run_logging_service_delivery_evidence_snapshot.py \
  tests/test_worker_workspace_readonly_validation.py \
  tests/test_human_approval_gate.py \
  tests/test_git_operation_dry_run.py \
  tests/test_delivery_gate_evidence.py -q
```

结果：

```text
79 passed, 4 warnings in <1s
```

### 6.3 测试覆盖清单

| 测试 | 覆盖项 | 状态 |
|------|--------|------|
| `test_delivery_evidence_snapshot_contract_constants_are_stable` | event/schema/message 常量值稳定 | Pass |
| `test_run_logging_service_writes_delivery_evidence_snapshot` | 完整写入+读回：event/message/data 全字段断言 | Pass |
| `test_run_logging_service_skips_delivery_evidence_snapshot_when_evidence_missing` | 三重空值 guard：log_path=None、operation_dry_run=None、delivery_gate_evidence=None | Pass |
| `test_run_logging_service_reads_latest_delivery_evidence_snapshot` | 最新 snapshot 读取：反向遍历、跳过非 snapshot event、missing log_path 返回 None | Pass |

### 6.4 关键断言覆盖

| 断言 | 测试 |
|------|------|
| `event == "delivery_evidence_snapshot"` | ✅ 全部 |
| `message` 为正确中文文案 | ✅ 全部 |
| `schema_version == "p4f2c0.v1"` | ✅ 全部 |
| `snapshot_source == "run_log_jsonl"` | ✅ 全部 |
| `operation_dry_run_available is True` | ✅ write test |
| `operation_dry_run_ready is True` | ✅ write test |
| `delivery_gate_evidence_available is True` | ✅ write test |
| `delivery_gate_evidence_ready is True` | ✅ write test |
| `human_approval_evaluated is False` | ✅ 全部 |
| `approval_record_created is False` | ✅ 全部 |
| `runs_write_git is False` | ✅ write test |
| `git_add_triggered is False` | ✅ write test |
| `git_commit_triggered is False` | ✅ 全部 |
| `git_push_triggered is False` | ✅ write test |
| `pr_opened is False` | ✅ write test |
| `ci_triggered is False` | ✅ write test |
| `gate_allows_write is False` | ✅ 全部 |
| `operation_dry_run` 完整 payload 在 snapshot 中 | ✅ write test + latest test |
| `delivery_gate_evidence` 完整 payload 在 snapshot 中 | ✅ write test + latest test |
| `operation_dry_run.safety_flags.git_commit_triggered is False` | ✅ write test |
| `delivery_gate_evidence.safety_flags.gate_allows_write is False` | ✅ write test + latest test |
| `delivery_gate_evidence.safety_flags.gate_allows_user_confirmation is True` | ✅ latest test |
| log_path=None 跳过写入 | ✅ skip test |
| missing evidence 跳过写入 | ✅ skip test |
| `read_latest_delivery_evidence_snapshot(log_path=None)` 返回 None | ✅ latest test |
| missing log_path 返回 None | ✅ latest test |
| 非 snapshot 事件被跳过（只返回最新 delivery_evidence_snapshot） | ✅ latest test |

---

## 7. 安全边界

### 7.1 不做什么（代码级审计）

| # | 边界 | 代码证据 |
|---|------|---------|
| 1 | 不重扫 Git | snapshot 只消费已有的 `operation_dry_run` 和 `delivery_gate_evidence` 对象 |
| 2 | 不信任前端 evidence | snapshot 数据全部来自 Worker 内存中由 Builder 生成的后端 evidence |
| 3 | 不生成 human approval evidence | `human_approval_evaluated=False`；无 `HumanApprovalGateBuilder.evaluate()` 调用 |
| 4 | 不调用 `HumanApprovalGateBuilder.evaluate()` | `run_logging_service.py` 和 `task_worker.py` 的 snapshot 写入路径均无调用 |
| 5 | 不执行产品运行时 `git add` | `git_add_triggered: False` |
| 6 | 不执行产品运行时 `git commit` | `git_commit_triggered: False` |
| 7 | 不执行产品运行时 `git push` | `git_push_triggered: False` |
| 8 | 不创建 PR | `pr_opened: False` |
| 9 | 不触发 CI | `ci_triggered: False` |
| 10 | 不写数据库 | 只写本地 JSONL 文件 |
| 11 | 不写 AgentMessage | 无 `agent_message_repository` 调用 |
| 12 | 不实现 approval API | 不在本阶段范围 |
| 13 | 不实现前端确认按钮 | 不在本阶段范围 |
| 14 | 不授权写仓库 | `gate_allows_write: False` |

### 7.2 数据流向

```text
Worker 成功执行
  ↓
P4-C GitOperationDryRunBuilder.build_from_diff_evidence() → git_operation_dry_run_result
P4-D DeliveryGateEvidenceBuilder.evaluate() → delivery_gate_evidence_result
  ↓
execution_quality_passed AND both not None?
  ├── No  → 不写 snapshot（静默跳过）
  └── Yes → append_delivery_evidence_snapshot(log_path, run_id, op, gate)
                ↓
              run_log JSONL file (本地文件系统)
                ↓
              read_latest_delivery_evidence_snapshot(log_path)
                ↓
              P4-F2-C Approval API (后续实现)
```

---

## 8. 当前 Not started 清单

| # | 能力 | 状态 | 计划阶段 |
|---|------|------|---------|
| 1 | P4-F2-C Approval API 最小实现 | Not started | P4-F2-C |
| 2 | P4-F2-D Approval Audit / AgentMessage | Not started | P4-F2-D |
| 3 | P4-F3 前端确认入口 | Not started | P4-F3 |
| 4 | P4-F4 Human Approval E2E Closure | Not started | P4-F4 |
| 5 | P5 Failure Recovery / 失败回流 | Not started | P5 |
| 6 | P6 Agent Orchestration / AI 主管调度 | Not started | P6 |
| 7 | P7 Project Director Conversation Hub + Governance | Not started | P7 |
| 8 | 产品运行时 `git add` | Not started | 后续真实写入阶段 |
| 9 | 产品运行时 `git commit` | Not started | 后续真实写入阶段 |
| 10 | 产品运行时 `git push` | Not started | 后续真实写入阶段 |
| 11 | PR 创建 / merge / CI | Not started | 后续真实写入阶段 |
| 12 | AI Project Director 总闭环 Pass | Not started | P7 完成后 |

---

## 9. Gate 结论

| Gate | 结论 | 证据 |
|------|------|------|
| `origin/main` HEAD 为 P4-F2-C0 实现 commit | Pass | `a0b8ffb0463bbc5b43a7da0ac682f751e59191a1` |
| Event contract 常量定义 | Pass | `event="delivery_evidence_snapshot"`, `schema_version="p4f2c0.v1"` |
| 中文 message 文案安全 | Pass | "尚未执行提交或推送" |
| `append_delivery_evidence_snapshot()` 写入方法 | Pass | 三重空值 guard |
| `read_latest_delivery_evidence_snapshot()` 读取方法 | Pass | 反向遍历 JSONL + 日志缺失安全返回 None |
| Worker 写入条件 | Pass | `execution_quality_passed` + P4-C not None + P4-D not None |
| Snapshot data 完整 | Pass | 包含 `operation_dry_run` 和 `delivery_gate_evidence` 的 `model_dump(mode="json")` |
| 所有 Git 写安全标志 = False | Pass | 7 个标志全部 False |
| `human_approval_evaluated=False` | Pass | 未调用 `HumanApprovalGateBuilder.evaluate()` |
| `approval_record_created=False` | Pass | 未创建 `HumanApprovalRecord` |
| Targeted tests 通过 | Pass | 79 passed, 4 warnings (含 P4-C/P4-D/P4-F1/workspace 相邻 regression) |
| 未重扫 Git | Pass | 仅消费已有 evidence |
| 未写 DB | Pass | 只写本地 JSONL |
| 未写 AgentMessage | Pass | 无 repository 调用 |
| 未实现产品运行时 Git 写操作 | Pass | 所有 write flag = False |
| **P4-F2-C0 Closure** | **Pass** | — |
| P4-F2-C Approval API | Not started | — |
| P4-F3 前端确认入口 | Not started | — |
| **AI Project Director 总闭环** | **Partial** | P7 完成前不得写 Pass |

---

## 10. 本轮收口声明

| 声明 | 结论 |
|------|------|
| 是否修改 Python 业务代码 | 否 |
| 是否修改测试代码 | 否 |
| 是否修改 Worker | 否 |
| 是否修改 API | 否 |
| 是否修改前端 | 否 |
| 是否修改数据库 / migration | 否 |
| 是否写 AgentMessage | 否 |
| 是否实现 approval API | 否 |
| 是否实现确认按钮 | 否 |
| 是否实现产品运行时 Git 写操作 | 否 |
| 是否只新增 P4-F2-C0 closure 文档 | 是 |

开发流程中的文档提交不代表 AI-Dev-Orchestrator 产品运行时具备 Git 写操作能力。

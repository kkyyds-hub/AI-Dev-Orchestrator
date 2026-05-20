# AI Project Director Confirmation Inbox Phase1 — 验收文档

> 文档日期：2026-05-19
> 仓库：kkyyds-hub/AI-Dev-Orchestrator
> 阶段：BCG-03 Phase1 后端闭环补齐
> 性质：后端实现级验收
> 配套文档：
> - `backend-closure-gap-freeze-20260519-v2.md`
> - `execution-plan-backfill-ledger-20260519.md`
> - `verification-project-director-session-phase1-20260519.md`
> - `verification-project-director-plan-version-phase1-20260519.md`

---

## 1. 实现范围

本阶段新增 Pending Confirmation Inbox 只读聚合接口，统一列出当前系统中等用户确认的事项。

Phase1 只做读取和聚合，不做 approve/reject，不改状态，不创建任务。

---

## 2. 新增 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/project-director/confirmations` | 全局查询所有 pending confirmations |
| GET | `/project-director/projects/{project_id}/confirmations` | 按 project_id 过滤 |
| GET | `/project-director/sessions/{session_id}/confirmations` | 按 session_id 过滤 |

所有接口均只读，返回格式：

```json
{
  "items": [...],
  "total": N
}
```

---

## 3. 聚合来源

| source_type | 源 | 状态条件 |
|---|---|---|
| `goal_confirmation` | ProjectDirectorSession | status = ready_to_confirm |
| `plan_confirmation` | ProjectDirectorPlanVersion | status = pending_confirmation |

### Confirmation Item 字段

| 字段 | 说明 |
|---|---|
| `id` | 复合 ID：`{source_type}:{source_id}` |
| `source_type` | `goal_confirmation` 或 `plan_confirmation` |
| `source_id` | 源对象 UUID |
| `project_id` | 关联项目 ID（可为 null） |
| `session_id` | 关联 session ID |
| `title` | 人类可读标题 |
| `summary` | 摘要（含状态、进度等上下文） |
| `status` | 源对象当前状态 |
| `risk_level` | 风险等级（Phase1 默认为 normal） |
| `next_action` | 建议下一步动作 |
| `confirm_api_hint` | 引导确认的 API 端点 |
| `created_at` | 源对象创建时间 |
| `updated_at` | 源对象更新时间 |

---

## 4. 新增文件

| 文件 | 说明 |
|---|---|
| `app/services/project_director_confirmation_service.py` | 只读聚合服务 |
| `tests/test_project_director_confirmations.py` | 12 个测试 |

### 修改文件

| 文件 | 变更 |
|---|---|
| `app/repositories/project_director_session_repository.py` | 新增 `list_by_status()` |
| `app/repositories/project_director_plan_version_repository.py` | 新增 `list_by_status()` |
| `app/api/routes/project_director.py` | 新增 ConfirmationItemResponse DTO + 3 个只读路由 |

---

## 5. 测试命令

```bash
cd runtime/orchestrator
python -m pytest tests/test_project_director_confirmations.py -v
```

## 6. 测试结果

```
============================= 15 passed =============================
```

全局回归：

```
python -m pytest tests/test_project_director_sessions.py tests/test_project_director_plan_versions.py tests/test_project_director_confirmations.py -v
============================= 77 passed =============================
```

### 测试覆盖

| 测试 | 覆盖内容 |
|---|---|
| `test_ready_to_confirm_session_appears` | ready_to_confirm session 出现在 inbox |
| `test_confirmed_session_does_not_appear` | confirmed session 不出现在 inbox |
| `test_pending_confirmation_plan_version_appears` | pending_confirmation plan 出现在 inbox |
| `test_confirmed_plan_version_does_not_appear` | confirmed plan 不出现在 inbox |
| `test_both_goal_and_plan_pending_appear` | goal + plan 同时 pending 都返回 |
| `test_filter_by_random_project_id_returns_empty` | 随机 project_id 返回空（负向） |
| `test_project_id_positive_filter_goal_confirmation` | 创建真实 project + 带 project_id 的 session → project 过滤命中 goal_confirmation |
| `test_project_id_positive_filter_plan_confirmation` | 创建真实 project + 带 project_id 的 session + plan version → project 过滤命中 plan_confirmation |
| `test_plan_version_read_only_state_invariant` | 三端点查询后 plan version 状态不变 |
| `test_filter_by_session_id` | 按 session_id 过滤 |
| `test_empty_inbox` | 空 inbox |
| `test_inbox_sorted_by_updated_at_desc` | updated_at 倒序 |
| `test_does_not_change_source_state` | 查询不改变源状态（session） |
| `test_confirm_api_hint_present` | 每个 item 含 confirm_api_hint |
| `test_all_required_fields_present` | 13 个必需字段齐全 |

---

## 7. 未覆盖范围

- 前端页面（本阶段未改前端）
- approve/reject/request-changes 写接口
- 更多聚合源（approval_requests、preflight、human interventions 等）
- 任务创建
- Worker 调度
- 仓库写入
- 运行证据（截图、E2E 联调）

---

## 8. BCG-03 Hardening Patch（2026-05-20）

### 性质

后端闭环测试证据补强（不新增功能，不新增 API，不改前端）。

### 补强内容

1. **project_id 正向过滤测试（goal_confirmation）**：
   - 创建真实 project，创建带 project_id 的 session 并进入 ready_to_confirm
   - `GET /project-director/projects/{project_id}/confirmations` 返回 goal_confirmation
   - `project_id` 字段正确填充，随机 project_id 返回空

2. **project_id 正向过滤测试（plan_confirmation）**：
   - 创建真实 project，从带 project_id 的 confirmed session 创建 plan version
   - `GET /project-director/projects/{project_id}/confirmations` 返回 plan_confirmation
   - plan version 继承 session 的 project_id

3. **plan version 只读状态不变测试**：
   - 创建 pending_confirmation plan version
   - 连续调用三个 inbox 端点后，plan version 状态仍为 pending_confirmation

### 测试结果

- 确认收件箱测试：15/15 通过（新增 3 个，原 12 个全部保留）
- 全局回归：77/77 通过（38 sessions + 24 plan versions + 15 confirmations）

### 严格边界

- 不改前端
- 不新增写接口
- 不创建任务
- 不调用 planning/apply
- 不调用 Worker
- 不写仓库
- 不接真实 AI
- 不调用 Provider
- 未运行 apps/web build

---

## 9. Gate 结论

```text
Gate 结论：Partial
后端实现：Backend Pass
运行证据：Runtime Evidence Missing
总闭环：Partial（BCG-03 Phase1 仅完成只读 confirmation inbox 聚合，不代表审批动作闭环，不代表 AI Project Director 总闭环 Pass）
```

### 理由

- 3 个只读 API 聚合 goal_confirmation + plan_confirmation 两种确认类型
- 支持按 project_id / session_id 过滤，支持全局查询
- project_id 正向过滤（goal + plan）和负向过滤均已覆盖
- plan version 查询状态不变已验证
- confirm_api_hint 指引用户到正确的确认端点
- 查询不改变任何源对象状态（纯只读）
- 15 个测试全部通过，原有 62 个测试无回归
- 未改前端、未接 AI、未创建任务、未调度 Worker、未写仓库

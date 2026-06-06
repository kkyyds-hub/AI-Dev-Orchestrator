# AI Project Director Role / Skill Consumption Evidence R1-K Audit

> 文档类型：Role/Skill consumption evidence audit + live HTTP + tests + frontend verification
> 审计日期：2026-05-30（Phase 1 gap analysis）/ 2026-05-31（Phase 2 runtime evidence）
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`f911bff`（Codex 已完成治理中心消费证据闭环补丁）
> 前置阶段：R1-J Runtime Pass (CL-14 approval closure)
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应验收项：CL-15（角色/Skill 是否记录消费证据）
> Phase 1 结论：Evidence Partial（Worker/Run 链路完整，治理中心前端缺口）
> **Phase 2 结论：Runtime Pass（治理中心消费聚合 API + 前端接入完成）**

---

## 1. 审计范围

重新验证 CL-15：Codex 已完成治理中心角色/Skill 消费证据闭环补丁后，端到端验证 Worker 调度 → Run 持久化 → consumption 聚合 API → GovernancePage 前端真实展示。

### 1.1 已检查文件

**Phase 2 新增：**
- `runtime/orchestrator/app/api/routes/roles.py` (+126 行：consumption API + response models)
- `runtime/orchestrator/tests/test_governance_role_skill_consumption.py` (new, 239 行)
- `apps/web/src/features/roles/api.ts` (+consumption fetch)
- `apps/web/src/features/roles/hooks.ts` (+useProjectRoleSkillConsumption)
- `apps/web/src/features/roles/types.ts` (+consumption response types)
- `apps/web/src/pages/governance/GovernancePage.tsx` (consumption 接入)

---

## 2. Codex 补丁概要（commit `f911bff` + `a45903e`）

### 2.1 后端：Consumption 聚合 API

新增 `GET /roles/projects/{project_id}/consumption` — 只读治理快照：

```python
# 签名
def get_project_role_skill_consumption(project_id: UUID, session: Session)
  → ProjectRoleSkillConsumptionResponse

# 实现
- 查询 project 下所有 Run（通过 TaskTable JOIN）
- 聚合 owner_role_code → role_consumption
- 聚合 strategy_decision.selected_skill_codes → skill_consumption
- 排序：按 run_count 降序
```

**Response 模型：**

```python
class ProjectRoleSkillConsumptionResponse:
    project_id: UUID
    total_run_count: int
    role_consumption_count: int
    skill_consumption_count: int
    roles: list[ProjectRoleConsumptionItemResponse]
    skills: list[ProjectSkillConsumptionItemResponse]
    generated_at: datetime

class ProjectRoleConsumptionItemResponse:
    role_code: ProjectRoleCode
    run_count: int
    succeeded_run_count: int
    failed_run_count: int
    total_tokens: int
    estimated_cost: float
    latest_run_id / latest_task_id
    latest_run_status / latest_run_created_at / latest_run_finished_at
    latest_run_summary

class ProjectSkillConsumptionItemResponse:
    skill_code: str
    skill_name: str | None
    run_count: int
    succeeded_run_count / failed_run_count
    total_tokens / estimated_cost
    latest_run_id / latest_task_id
    latest_owner_role_code
    latest_run_status / latest_run_created_at / latest_run_finished_at
    latest_run_summary
```

### 2.2 前端：GovernancePage 接入

| 位置 | 变更 |
|---|---|
| 本项目 AI 团队 (team tab) | 接入 `useProjectRoleSkillConsumption` → 展示 `total_run_count` / `role_consumption_count` / `skill_consumption_count` |
| 角色治理 (roles tab) | "最近消费证据" 从 "暂无消费证据" → 真实 `run_count` / `succeeded` / `failed` / `estimated_cost` |
| Skill 治理 (skills tab) | "最近消费证据" 从 "暂无消费证据" → 真实 `run_count` / `latest_owner_role_code` |
| 空状态 | "暂无消费证据" → "暂无运行时消费证据（已接入消费聚合 API）" |

Dashboard 文案从 "基于角色目录静态基线，待接入真实运行时消费证据" → "运行时消费证据来自 GET /roles/projects/:id/consumption：N 次 Run，M 个角色，K 个 Skill。"

### 2.3 测试

`tests/test_governance_role_skill_consumption.py` (3 tests):
1. `test_project_role_skill_consumption_aggregates_persisted_runs` — 验证跨项目隔离、角色/Skill 计数、tokens/cost 聚合、latest_run 指向
2. `test_project_role_skill_consumption_returns_empty_aggregate_for_project_without_runs` — 无 Run 项目返回空数组
3. `test_project_role_skill_consumption_returns_404_for_missing_project` — 不存在项目 404

---

## 3. Live HTTP Evidence（Phase 2）

> Backend: `WORKER_SIMULATE_EXECUTION_OVERRIDE=1`
> 3 Worker runs → 3 tasks completed

### Worker Runs

| Run | owner_role_code | selected_skill_codes |
|---|---|---|
| 1 | architect | dependency_analysis, solution_design, risk_assessment |
| 2 | architect | dependency_analysis, solution_design, risk_assessment |
| 3 | reviewer | review_checklist, quality_gate, risk_replay |

### Consumption API Readback

```
GET /roles/projects/{pid}/consumption → 200

project_id=3781d841-5d31-480e-ab7c-9017f36865c0
total_run_count=3
role_consumption_count=2
skill_consumption_count=6

Roles:
  architect: run_count=2 succeeded=2 failed=0 total_tokens=1191
  reviewer:  run_count=1 succeeded=1 failed=0 total_tokens=1032

Skills:
  dependency_analysis: name=依赖分析 run_count=2 latest_owner_role=architect
  risk_assessment:     name=风险评估  run_count=2 latest_owner_role=architect
  solution_design:     name=方案设计  run_count=2 latest_owner_role=architect
  quality_gate:        name=质量闸门  run_count=1 latest_owner_role=reviewer
  review_checklist:    name=审查清单  run_count=1 latest_owner_role=reviewer
  risk_replay:         name=风险回放  run_count=1 latest_owner_role=reviewer
```

Aggregation confirmed: 3 runs → 2 roles (architect ×2, reviewer ×1) → 6 skills (dedup by code, cross-role)

### Error Cases

```
GET /roles/projects/11111111-1111-1111-1111-111111111111/consumption → 404
"Project not found: ..."
```

---

## 4. Frontend GovernancePage Verification

### 4.1 Static Code Analysis

| Check | Result |
|---|---|
| `useProjectRoleSkillConsumption` hook exists | ✓ (`apps/web/src/features/roles/hooks.ts:28`) |
| `api.ts` calls `/roles/projects/{id}/consumption` | ✓ (`apps/web/src/features/roles/api.ts:25`) |
| `types.ts` has `ProjectRoleSkillConsumptionResponse` + sub-types | ✓ |
| GovernancePage TeamTab uses `consumptionQuery` | ✓ (line 167) |
| GovernancePage RolesTab uses `consumptionQuery` | ✓ (line 237) |
| GovernancePage SkillsTab uses `consumptionQuery` | ✓ (line 404) |
| No "待接入真实运行时消费证据" text | ✓ (replaced) |
| No "暂无消费证据" text (without "已接入" suffix) | ✓ (replaced) |
| Empty state: "暂无运行时消费证据（已接入消费聚合 API）" | ✓ (line 208) |
| Dashboard summary: "运行时消费证据来自 GET /roles/projects/:id/consumption" | ✓ (line 179) |

### 4.2 Build

```
cd apps/web && npm.cmd run build → built in 14.74s
```

---

## 5. Tests

```bash
cd runtime/orchestrator
python -m pytest tests/test_governance_role_skill_consumption.py -q
→ 3 passed in 2.11s
```

---

## 6. End-to-End Chain Confirmed

```
Worker dispatch (owner_role_code + selected_skill_codes)
  → Run persistence (strategy_decision_json)
    → GET /roles/projects/{pid}/consumption (aggregation API)
      → GovernancePage (TeamTab / RolesTab / SkillsTab)
```

All four layers verified:
- Layer 1: Worker live HTTP (3 runs with role/skill data)
- Layer 2: Run persistence (confirmed via consumption API aggregation)
- Layer 3: Consumption API (200 with correct role/skill counts, tokens, costs)
- Layer 4: Frontend (static analysis shows hook usage, no outdated placeholders, build passes)

---

## 7. CL-15 Status

**Runtime Pass** (upgraded from Phase 1 Evidence Partial)

Codex patch added:
1. `/roles/projects/{pid}/consumption` — governance aggregation API
2. `useProjectRoleSkillConsumption` — frontend hook
3. GovernancePage TeamTab/RolesTab/SkillsTab — full consumption data display
4. Tests (3 paths: with runs, empty, 404)

All four layers now form a complete end-to-end chain.

---

## 8. Gate Conclusion

### 8.1 R1-K Gate

**Runtime Pass**

Worker→Run→Consumption API→GovernancePage 全链路闭合。3 backend tests + live HTTP evidence + frontend build 通过。

### 8.2 AI Project Director Total Closure

**仍为 Partial**

CL-16（成本闭环端到端接入）、CL-18 尚未完成。

# AI Project Director Role / Skill Team Governance R1-N Audit

> 文档类型：CL-05/CL-06 role-skill team governance audit + live HTTP + frontend
> 审计日期：2026-05-31
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit：`cf6e7de`
> 前置阶段：R1-M Documentation Pass (total gate)
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应验收项：CL-05（是否生成角色与 Skill 方案）、CL-06（是否区分模板资产与项目实例）

---

## 1. 审计范围

验证 CL-05（是否生成角色与 Skill 方案）和 CL-06（角色 / Skill 是否区分模板资产与项目实例）。

### 1.1 已检查文件

- `runtime/orchestrator/app/api/routes/roles.py`
- `runtime/orchestrator/app/api/routes/skills.py`
- `runtime/orchestrator/app/services/role_catalog_service.py`
- `runtime/orchestrator/app/services/skill_registry_service.py`
- `runtime/orchestrator/app/workers/task_worker.py` (owner_role_code + selected_skill_codes)
- `runtime/orchestrator/tests/test_governance_role_skill_consumption.py`
- `apps/web/src/pages/governance/GovernancePage.tsx` (RolesTab, SkillsTab)
- `apps/web/src/features/roles/hooks.ts`
- `apps/web/src/features/skills/hooks.ts`

---

## 2. Role / Skill API Inventory

### 2.1 System Templates (Template Layer)

| Method | Path | Purpose |
|---|---|---|
| GET | `/roles/catalog` | 系统内置角色目录（4 roles） |
| GET | `/skills/registry` | 系统 Skill 注册表（12 skills） |

### 2.2 Project Instances (Instance Layer)

| Method | Path | Purpose |
|---|---|---|
| GET | `/roles/projects/{pid}` | 项目级角色配置实例 |
| PUT | `/roles/projects/{pid}/{role_code}` | 自定义项目角色实例 |
| GET | `/skills/projects/{pid}/bindings` | 项目级角色-Skill 绑定 |

### 2.3 Worker Consumption (Runtime Layer)

| Field | Source |
|---|---|
| owner_role_code | StrategyEngine → uses project role config |
| selected_skill_codes | StrategyEngine → uses project skill bindings |
| handoff chain (upstream/downstream) | TaskRouter |

---

## 3. Live HTTP Evidence

> project_id=`39e39271-6c6e-4743-b37f-eb1048b6cbea`

### 3.1 System Role Catalog

```
GET /roles/catalog → 200
4 built-in roles:
  product_manager (sort=10, 3 default skills)
  architect (sort=20, 3 default skills)
  engineer (sort=30, 3 default skills)
  reviewer (sort=40, 3 default skills)
```

Each role has: code, name, summary, responsibilities[], input_boundary[], output_boundary[], default_skill_slots[], enabled_by_default, sort_order.

### 3.2 Project Role Instances

```
GET /roles/projects/{pid} → 200
4 project instances (auto-initialized from catalog):
  each has: id (UUID) + project_id + role_code + name + enabled + custom_notes
```

Auto-initialization: on first access, catalog roles are cloned into project instances with unique UUIDs and project_id binding.

### 3.3 Project Instance Customization

```
PUT /roles/projects/{pid}/architect → 200
Before: name="架构师", skills=[3 default], custom_notes=None
After:  name="Custom Architect", skills=[4 including custom_arch_skill],
        custom_notes="Extended for this project: includes security review scope"

GET readback → confirms changes persisted
```

### 3.4 Template vs Instance Distinction

| Property | System Template | Project Instance |
|---|---|---|
| id | N/A | UUID (9fd9249d-9c6..2157) |
| project_id | N/A | 39e39271-6c6e-4743-b37f-eb1048b6cbea |
| name | 架构师 | **Custom Architect** |
| default_skill_slots | [3 system skills] | [4 skills, inc. custom_arch_skill] |
| custom_notes | N/A | "Extended for this project..." |
| lifecycle | built-in / template_stable | project_local |

**Template ≠ Instance: confirmed.** Project customization does not mutate the system catalog.

### 3.5 Skill Registry

```
GET /skills/registry → 200
12 system-level skill templates:
  requirements_clarification, scope_breakdown, priority_planning,
  solution_design, dependency_analysis, risk_assessment,
  implementation, local_verification, change_description,
  review_checklist, quality_gate, risk_replay
```

### 3.6 Project Skill Bindings

```
GET /skills/projects/{pid}/bindings → 200
4 role binding groups:
  product_manager: 3 bindings
  architect: 3 bindings
  engineer: 3 bindings
  reviewer: 3 bindings
```

Auto-initialized from catalog default_skill_slots on first project access.

### 3.7 Worker Role/Skill Consumption (from CL-15)

Worker dispatch uses project role/skill configuration:
- owner_role_code = "architect" (from project role config)
- selected_skill_codes = ["dependency_analysis", "solution_design", "risk_assessment"] (from project skill bindings)
- Verified live HTTP in R1-K

---

## 4. Frontend GovernancePage Verification

| Tab | Source | Display |
|---|---|---|
| 角色治理 (RolesTab) | useSystemRoleCatalog() + useProjectRoleCatalog() | 角色目录模板 → 项目实例双视图；lifecycle badge (project_local / template_candidate / template_stable) |
| Skill 治理 (SkillsTab) | useSkillRegistry() + useProjectSkillBindings() | Skill 模板注册表 → 项目绑定双视图；每个 Skill 显示 applicable_role_codes |

Lifecycle tabs:
- "项目实例" (project_local) — project-level customized instances
- "候选模板" (template_candidate) — proposed templates
- "稳定模板" (template_stable) — system built-in / stable templates

---

## 5. Tests

```
python -m pytest tests/test_governance_role_skill_consumption.py -q
→ 3 passed in 2.07s
```

---

## 6. CL-05 Status

**Runtime Pass**

- System role catalog (4 roles) with responsibilities, skill slots, boundaries ✓
- Project role instances auto-initialized from catalog ✓
- Project role instances customizable without mutating templates ✓
- Worker dispatch uses project role config (owner_role_code) ✓
- Frontend GovernancePage displays both template and instance layers ✓

### 7. CL-06 Status

**Runtime Pass**

- System templates: id-less, no project_id, immutable catalog ✓
- Project instances: UUID + project_id, customizable name/skills/notes ✓
- Lifecycle labels: project_local / template_candidate / template_stable ✓
- Customization mutation confined to project instance (template unchanged) ✓
- Frontend lifecycle tabs filter by source ✓

---

## 8. Gate Conclusion

### 8.1 R1-N Gate

**Runtime Pass**

CL-05 (role/Skill 方案生成) + CL-06 (模板 vs 实例区分) 均通过 live HTTP + frontend 验证。系统目录→项目实例→自定义→Worker 消费全链路闭合。

### 8.2 AI Project Director Total Closure

**仍为 Partial**

CL-12 / CL-16 Evidence Partial 尚未消除。更新后的状态：
14 Runtime Pass + 2 Evidence Partial + 2 Not Started → 0 Not Started (CL-05/06 now Runtime Pass)。
Total closure 不能在 CL-12/CL-16 仍有缺口时标记为 Pass。

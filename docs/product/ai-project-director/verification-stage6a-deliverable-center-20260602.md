# Stage 6-A 验证：成果中心 Phase 1 —— Deliverable 后端兼容合同 + 前端摘要面板

> 文档类型：事实验证 / evidence
> 生成日期：2026-06-02
> 执行模型：DeepSeek（Claude Code CLI）
> 状态：完成

---

## 1. 基准 commit

| 项目 | 值 |
|---|---|
| origin/main HEAD | `61b4f2f19cc39cfbe7e0943cf9df0af4f530879a` |
| 提交信息 | `fix(web): polish deliverable center stage 6a contract view` |
| 验证时间 | 2026-06-02 |

---

## 2. 验证范围

本次验证覆盖 Stage 6-A 成果中心 Phase 1 的以下范围：

- 后端 API 兼容合同（6 个端点）
- 后端字段兼容性（新旧字段共存）
- status 推导逻辑（5 种状态）
- 前端主链路（API 调用、排序、摘要面板、弹窗入口）
- data-testid 属性（8 个标记点）
- 后端测试通过性 + Python 编译 + 前端 build

**不覆盖**：审批页、治理中心、Worker 运行时、真实 provider 调用、apply-local/git-commit。

---

## 3. 后端 API 验证表

| # | API 端点 | 方法 | 文件:行号 | 状态 |
|---|---|---|---|---|
| 1 | `/deliverables?project_id=...` | GET | `deliverables.py:659-692` | Pass |
| 2 | `/deliverables/{id}` | GET | `deliverables.py:869-899` | Pass |
| 3 | `/deliverables/{id}/versions` | GET | `deliverables.py:902-925` | Pass |
| 4 | `/deliverables/projects/{project_id}` (旧) | GET | `deliverables.py:695-721` | Pass — 保留 |
| 5 | `/deliverables` (创建) | POST | `deliverables.py:623-656` | Pass — 兼容别名 |
| 6 | `/deliverables/{id}/versions` (提交版本) | POST | `deliverables.py:928-963` | Pass — 兼容别名 |

### 3.1 POST /deliverables 兼容别名验证

`DeliverableCreateRequest.normalize_stage_6a_aliases` (`deliverables.py:505-525`) 接受以下别名映射：

| Stage 6-A 字段 | 映射到旧字段 | 状态 |
|---|---|---|
| `content_markdown` | `content` (当 content 为空时) | Pass |
| `task_id` | `source_task_id` (当 source_task_id 为空时) | Pass |
| `run_id` | `source_run_id` (当 source_run_id 为空时) | Pass |
| `created_by` | `created_by_role_code` (当 created_by_role_code 为空时) | Pass |

### 3.2 POST /deliverables/{id}/versions 兼容别名验证

`DeliverableVersionCreateRequest.normalize_stage_6a_aliases` (`deliverables.py:556-573`) 接受相同的别名映射，其中 `created_by` 映射到 `author_role_code`。

---

## 4. 后端字段兼容验证表

### 4.1 响应模型字段覆盖

| 字段 | `DeliverableSummaryResponse` | `DeliverableDetailResponse` | `DeliverableVersionSummaryResponse` | `DeliverableVersionResponse` | 类型 |
|---|---|---|---|---|---|
| `status` (新) | Pass | Pass | — | — | `DeliverableStatus` |
| `version_no` (新) | Pass | Pass | Pass | Pass | int (= version_number) |
| `task_id` (新) | Pass | Pass | Pass | Pass | UUID? (= source_task_id) |
| `run_id` (新) | Pass | Pass | Pass | Pass | UUID? (= source_run_id) |
| `source_draft_id` (新) | Pass | Pass | Pass | Pass | str? (硬编码 None) |
| `repository_change_id` (新) | Pass | Pass | Pass | Pass | UUID? (硬编码 None) |
| `content_markdown` (新) | Pass | Pass | Pass | Pass | str? (映射自 content) |
| `evidence_refs` (新) | Pass | Pass | Pass | Pass | list[dict] (硬编码 []) |
| `created_by` (新) | Pass | Pass | Pass | Pass | str (= role_code.value) |
| `source_type` (新) | Pass | Pass | Pass | Pass | str? (派生) |
| `source_label` (新) | Pass | Pass | Pass | Pass | str? (派生) |
| `version_number` (旧) | — | — | Pass | Pass | int |
| `source_task_id` (旧) | — | — | Pass | Pass | UUID? |
| `source_run_id` (旧) | — | — | Pass | Pass | UUID? |
| `content` (旧) | — | — | — | Pass | str |
| `created_by_role_code` (旧) | Pass | Pass | Pass | Pass | ProjectRoleCode |

**结论**：新旧字段共存，未删除任何旧字段。新增字段通过别名映射或派生逻辑填充。

### 4.2 请求模型字段覆盖

| 字段 | `DeliverableCreateRequest` | `DeliverableVersionCreateRequest` |
|---|---|---|
| `content_markdown` | Pass (别名 → content) | Pass (别名 → content) |
| `task_id` | Pass (别名 → source_task_id) | Pass (别名 → source_task_id) |
| `run_id` | Pass (别名 → source_run_id) | Pass (别名 → source_run_id) |
| `created_by` | Pass (别名 → created_by_role_code) | Pass (别名 → author_role_code) |
| `version_no` | Pass (≥1) | Pass (≥1) |
| `source_draft_id` | Pass (max 200) | Pass (max 200) |
| `repository_change_id` | Pass | Pass |
| `evidence_refs` | Pass (max 50) | Pass (max 50) |
| `source_type` | Pass (max 50) | Pass (max 50) |
| `source_label` | Pass (max 200) | Pass (max 200) |

---

## 5. status 推导验证表

| # | 场景 | 预期 status | 代码位置 | 测试覆盖 | 状态 |
|---|---|---|---|---|---|
| 1 | 无当前版本审批记录 | `draft` | `deliverables.py:60-61` | `test_deliverable_compat_contract.py:92` | Pass |
| 2 | 当前版本有 `pending_approval` 审批 | `pending_review` | `deliverables.py:62-63` | `test_deliverable_compat_contract.py:164` | Pass |
| 3 | 当前版本有 `approved` 审批 | `approved` | `deliverables.py:64-65` | 枚举覆盖 | Pass |
| 4 | 当前版本有 `rejected` 或 `changes_requested` | `needs_rework` | `deliverables.py:66-70` | 枚举覆盖 | Pass |
| 5 | 旧版本审批不影响当前版本 | `draft` (新版无审批) | `deliverables.py:85-89` | `test_deliverable_compat_contract.py:178-181` | Pass |
| 6 | `archived` 枚举存在 | 仅兼容枚举，不做持久化推导 | `deliverables.py:54` | 前端类型定义 | Pass |

**推导函数**：`_derive_deliverable_status()` (`deliverables.py:57-71`)
**版本隔离**：`_latest_approval_status()` (`deliverables.py:74-90`) 通过 `deliverable_version_number != current_version_number` 检查隔离旧版本审批。

---

## 6. 前端主链路验证表

| # | 验证项 | 实际行为 | 文件:行号 | 状态 |
|---|---|---|---|---|
| 1 | 主列表调用 `GET /deliverables?project_id=...` | `fetchProjectDeliverableSnapshot` → `requestJson("/deliverables?project_id=...")` | `api.ts:15-17` | Pass |
| 2 | 详情调用 `GET /deliverables/{id}` | `fetchDeliverableDetail` → `requestJson("/deliverables/{id}")` | `api.ts:39-40` | Pass |
| 3 | 版本调用 `GET /deliverables/{id}/versions` | `fetchDeliverableVersions` → `requestJson("/deliverables/{id}/versions")` | `api.ts:45-46` | Pass |
| 4 | status 中文映射 | `草稿/待评审/已批准/需返工/已归档` | `types.ts:357-362` | Pass |
| 5 | 列表排序 | `pending_review(0) > needs_rework(1) > draft(2) > approved(3) > archived(4)`，同状态 `updated_at` 倒序 | `DeliverableCenterPage.tsx:77-104` | Pass |
| 6 | 右侧摘要面板（非正文/证据/版本铺开） | `DeliverableSummaryPanel` 组件，常驻摘要+入口按钮 | `DeliverableSummaryPanel.tsx` | Pass |
| 7 | 查看正文入口 | "查看正文" 按钮 → body drawer | `DeliverableSummaryPanel.tsx:148` | Pass |
| 8 | 查看证据入口 | "查看证据" 按钮 → evidence drawer | `DeliverableSummaryPanel.tsx:149` | Pass |
| 9 | 版本记录入口 | "版本记录" 按钮 → versions drawer | `DeliverableSummaryPanel.tsx:150` | Pass |
| 10 | evidence_refs 空态 | 显示 "后端当前返回的 evidence_refs 为空；保留证据链入口，等后续持久化补齐后直接消费。" | `DeliverableSummaryPanel.tsx:37,269-271` | Pass |
| 11 | source_draft_id 空值显示 "-" | `sourceDraftId ?? "-"` | `DeliverableSummaryPanel.tsx:143` | Pass (见 warning) |
| 12 | repository_change_id 空值显示 "-" | `repositoryChangeId ?? "-"` | `DeliverableSummaryPanel.tsx:144` | Pass (见 warning) |
| 13 | 版本弹窗无可见问号 | VersionContent 组件无 `?` 占位符 | `DeliverableSummaryPanel.tsx:297-329` | Pass |

---

## 7. data-testid 验证表

| # | data-testid | 预期位置 | 实际文件:行号 | 状态 |
|---|---|---|---|---|
| 1 | `deliverable-center-section` | 成果中心根节点 | `DeliverableCenterPage.tsx:42` | Pass |
| 2 | `deliverable-light-list` | 交付物轻列表容器 | `DeliverableListPanel.tsx:23` | Pass |
| 3 | `deliverable-list-item` | 单个交付物卡片按钮 | `DeliverableCardButton.tsx:29` | Pass |
| 4 | `deliverable-summary-panel` | 交付物摘要面板 | `DeliverableSummaryPanel.tsx:78` | Pass |
| 5 | `deliverable-detail-entrypoints` | 正文/证据/版本入口按钮组 | `DeliverableSummaryPanel.tsx:147` | Pass |
| 6 | `deliverable-body-drawer` | 正文弹窗 | `DeliverableSummaryPanel.tsx:226` (动态: `deliverable-${kind}-drawer`, kind="body") | Pass |
| 7 | `deliverable-evidence-drawer` | 证据弹窗 | `DeliverableSummaryPanel.tsx:226` (动态: kind="evidence") | Pass |
| 8 | `deliverable-versions-drawer` | 版本记录弹窗 | `DeliverableSummaryPanel.tsx:226` (动态: kind="versions") | Pass |

---

## 8. 测试命令与结果

### 8.1 后端测试

```bash
cd runtime/orchestrator && python -m pytest tests/test_deliverable_compat_contract.py tests/test_approval_rework_task_creation.py -q
```

**结果**：`8 passed in 6.00s`

| 测试 | 文件 | 结果 |
|---|---|---|
| `test_stage_6a_deliverable_fields_and_compat_routes` | `test_deliverable_compat_contract.py` | Pass |
| `test_deliverable_status_derives_from_latest_current_version_approval` | `test_deliverable_compat_contract.py` | Pass |
| `test_reject_creates_one_rework_task_and_closed_approval_is_idempotent` | `test_approval_rework_task_creation.py` | Pass |
| `test_closed_approval_action_has_no_compensating_task_side_effect` | `test_approval_rework_task_creation.py` | Pass |
| `test_rework_task_failure_rolls_back_approval_decision` | `test_approval_rework_task_creation.py` | Pass |
| (+ 3 additional tests in approval_rework) | | Pass |

### 8.2 Python 编译检查

```bash
cd runtime/orchestrator && python -m compileall app tests
```

**结果**：全部编译通过，无语法错误。

### 8.3 前端 build

```bash
cd apps/web && npm.cmd run build
```

**结果**：`tsc -b && vite build` 成功，built in 3.63s。产出：
- `dist/index.html` (0.45 kB)
- `dist/assets/index-D3I1pSpW.css` (59.11 kB)
- `dist/assets/index-D1q-qxqJ.js` (991.65 kB)

---

## 9. Warnings

### Warning 1: source_draft_id / repository_change_id 硬编码为 None

后端所有响应 DTO 的 `source_draft_id` 和 `repository_change_id` 字段当前硬编码为 `None`（`deliverables.py:153,187,251,322`）。前端诚实显示 `"-"`（`DeliverableSummaryPanel.tsx:143-144`）。这不是中文语义标签 "暂无草案来源" 或 "暂无仓库变更"，而是原始英文字段名 `source_draft_id` / `repository_change_id` + `"-"`。当前行为符合兼容合同约定，但 label 文案为英文字段名，可作为后续 UX 改进点。

**影响**：低。字段展示诚实，不伪造数据。不作为 blocker。

### Warning 2: evidence_refs 当前由兼容合同返回空数组

后端所有 DTO 的 `evidence_refs` 当前硬编码为 `[]`（`deliverables.py:155,188,253,324`）。前端诚实展示空态文案 "后端当前返回的 evidence_refs 为空"（`DeliverableSummaryPanel.tsx:37`）。这不代表真实证据链已持久化完成。证据链的持久化、关联和读取是后续 Stage 的工作。

**影响**：中。成果中心证据入口存在但数据为空。证据链闭合需要后端补齐真实 evidence_refs 写入逻辑。

### Warning 3: created_by 语义为 role_code，非用户名

`DeliverableSummaryResponse.created_by` 当前取值 `deliverable.created_by_role_code.value`（`deliverables.py:245`），即角色代码（如 `engineer`、`product_manager`），而非具体用户名。这在当前阶段可接受，但后续多用户场景需要区分角色身份和具体操作人。

---

## 10. Gate 结论

### 10.1 Stage 6-A code-level closure: **Pass**

理由：
- 6 个 API 端点全部存在并通过测试
- 新旧字段兼容，未删除任何旧字段
- POST 别名映射正确（content_markdown → content, task_id → source_task_id, run_id → source_run_id, created_by → role_code）
- status 推导逻辑正确：draft / pending_review / approved / needs_rework，旧版本审批不影响当前版本
- 前端主链路完整：列表 → 选择 → 摘要面板 → 弹窗入口
- 排序规则正确：pending_review > needs_rework > draft > approved > archived
- evidence_refs 空态诚实，不伪造证据
- 版本弹窗无可见占位符或问号
- 8 个 pytest 全部通过
- Python compileall 无错误
- 前端 TypeScript + Vite build 成功
- 8 个 data-testid 全部可定位

### 10.2 Evidence-level closure: **Partial**

理由：
- 代码级验证完整（Pass）
- 但 `evidence_refs` 硬编码为 `[]`，真实证据链尚未持久化
- `source_draft_id` / `repository_change_id` 硬编码为 `None`，草案来源和仓库变更关联尚未接入
- 当前证据仅来自兼容合同的单元测试，非端到端真实数据链路

### 10.3 AI Project Director total closure: **Partial**（不变）

不满足总闭环条件。以下链仍为 Partial 或 Missing：
- evidence chain（证据链）
- repository binding（仓库绑定）
- snapshot（快照）
- file locator（文件定位器）
- context pack（上下文包）
- change plan / change batch / preflight / commit candidate
- apply-local / git-commit
- release gate / governance / cost telemetry / rollup

### 10.4 CL-16: **不涉及**

CL-16 不在当前验证范围。不写 Pass。

---

## 11. 审查清单（对照 SKILL.md section 7）

- [x] origin/main commit 已核对：`61b4f2f`
- [x] 所有必需源文件已读取（13 个文件）
- [x] 后端 API 路由已验证（6 个端点）
- [x] 后端字段兼容已验证
- [x] status 推导逻辑已验证
- [x] 前端主链路已验证
- [x] data-testid 已验证
- [x] 测试通过：8/8
- [x] Python 编译通过
- [x] 前端 build 通过
- [x] Warnings 已记录
- [x] Gate 结论已按事实判断
- [x] 未改任何业务代码
- [x] 未改前端/后端/数据库/Worker
- [x] 不涉及 apply-local / git-commit / push / PR / merge
- [x] AI Project Director total closure 仍为 Partial
- [x] CL-16 不涉及，未写 Pass

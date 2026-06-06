# Stage 7-A0：真实 Provider / Worker 首次验收准备审计

> 文档类型：只读审计 / readiness assessment
> 生成日期：2026-06-02
> 执行模型：DeepSeek（Claude Code CLI）
> 基准 commit：`ee82083653a244fa91b4d749b8b521ea7967c104`
> 状态：完成
> 覆盖：Stage 7-A0 — 用户首次真实 Provider/Worker 运行前的准备条件审计

---

## 1. 基准 commit

| 项目 | 值 |
|---|---|
| origin/main HEAD | `ee82083653a244fa91b4d749b8b521ea7967c104` |
| 提交信息 | `docs: fix total closure gap count summary` |
| 审计时间 | 2026-06-02 |

---

## 2. 审计范围

本次审计只读检查当前系统是否已具备"用户本人手动完成第一次真实 Provider / Worker 运行验收"的准备条件。范围：

- Provider 配置（设置页 + 后端）
- Worker simulate / real 模式控制
- 首次真实运行安全护栏
- 运行后验收路径（Run / logs / summary / cost / deliverable / approval）

**不覆盖**：真实运行本身、真实 provider 调用、Worker 启动、Run 创建、代码修改。

---

## 3. Provider 配置准备度

### 3.1 后端端点

| # | 端点 | 方法 | 代码位置 | 状态 |
|---|---|---|---|---|
| 1 | `/provider-settings/openai` | GET | `provider_settings.py:105-119` | Pass |
| 2 | `/provider-settings/openai` | PUT | `provider_settings.py:122-150` | Pass |
| 3 | `/provider-settings/openai/test` | POST | `provider_settings.py:153-176` | Pass |

### 3.2 配置能力

| # | 能力 | 后端实现 | 前端实现 | 状态 |
|---|---|---|---|---|
| 1 | 配置 base_url | `OpenAIProviderSettingsUpdateRequest.base_url` | SettingsPage ProviderSection，text input | Pass |
| 2 | 配置 API Key | `OpenAIProviderSettingsUpdateRequest.api_key` | `<input type="password">`，留空保留当前 Key | Pass |
| 3 | 配置 timeout | `OpenAIProviderSettingsUpdateRequest.timeout_seconds`（≥1） | SettingsPage timeout input | Pass |
| 4 | 配置 model_preset | `openai`/`deepseek`/`custom` 三选一 | SettingsPage preset selector | Pass |
| 5 | 配置 model_names (custom) | economy/balanced/premium 三级 | SettingsPage custom model names form | Pass |
| 6 | 保存配置 | `PUT /provider-settings/openai` → JSON 文件持久化 | `updateProvider()` API call | Pass |
| 7 | 读取配置 | `GET /provider-settings/openai` → 返回 summary | `fetchProvider()` → 展示当前状态 | Pass |
| 8 | 测试连接 | `POST /provider-settings/openai/test` → 返回 auth_valid/endpoint_reachable/model_usable | "测试连接" 按钮 | Pass |
| 9 | 区分 DeepSeek/OpenAI/兼容 | `ProviderConfigService.detect_provider_type()`（基于 hostname） | `detected_provider_type` 字段展示 | Pass |

### 3.3 API Key 安全

| # | 安全项 | 实现 | 状态 |
|---|---|---|---|
| 1 | API Key 不回显明文 | `_mask_api_key()`：`********XXXX` 格式（仅保留末 4 位） | Pass |
| 2 | 前端输入 type=password | `<input type="password">` 掩码输入 | Pass |
| 3 | 环境变量 fallback | `OPENAI_API_KEY` 环境变量可被读取，但 API 响应仅返回 masked | Pass |
| 4 | 诊断信息不含 API Key | 设置页诊断功能明确标注"不含 API Key 明文" | Pass |

### 3.4 Provider Config 配置来源与优先级

`provider_config_service.py:169-215`（`resolve_openai_runtime_config()`）：

```
saved_config (JSON file) > env (OPENAI_API_KEY) > none
```

| 来源 | source 字段 | 触发条件 |
|---|---|---|
| 用户通过设置页保存 | `saved_config` | JSON 文件存在且含 api_key |
| 环境变量 | `env` | 无 saved_config 且 `OPENAI_API_KEY` 已设置 |
| 未配置 | `none` | 均无 |

---

## 4. Worker Simulate / Real 模式准备度

### 4.1 模式控制机制

**控制变量**：`WORKER_SIMULATE_EXECUTION_OVERRIDE` 环境变量（`config.py:156-159`）

| 值 | 行为 | 当前默认值 |
|---|---|---|
| `True` / `1` / `yes` / `on` | 强制 simulate 模式，所有 provider 路径退化为 mock | — |
| `False`（默认） | 允许真实 provider 调用 | **`False`** |

**执行模式路由**（`executor_service.py:370-388`，`build_execution_plan()`）：

```python
if self.force_simulate_execution_override:
    return SIMULATE   # 强制 simulate
if routing_contract.primary_mode == PROVIDER:
    return PROVIDER   # 真实 provider 调用
return default_mode   # 取决于 task input
```

### 4.2 Run 详情页模式标签

**前端**：`runUserSummary.ts:123-148` 已为不同 execution_mode 提供中文标签：

| execution_mode | 前端标签 |
|---|---|
| `simulate` | "模拟模型执行（不可作为真实交付依据）" |
| `provider_mock` | "降级执行（不可作为真实交付依据）" |
| `provider_openai` | "模型服务 {name} 已真实执行成功" |

**重要**：模式标签仅在 Run 详情页 **事后** 展示。用户点击"启动一次执行"前看不到任何当前模式提示。

### 4.3 当前缺口：用户不清楚当前是 simulate 还是 real

| 缺口 | 详情 |
|---|---|
| 位置 | 工作台 "启动一次执行" 按钮（`DirectorChatEntry.tsx:571-581`） |
| 问题 | 按钮文案仅为"启动一次执行"，不显示当前是否处于 simulate 模式 |
| 影响 | `WORKER_SIMULATE_EXECUTION_OVERRIDE` 默认为 `False`（允许真实调用），但用户可能不知情。如果用户之前设置过 `True`，也可能忘记已切换回 simulate |
| 建议 | **Codex P0**：在"启动一次执行"按钮附近增加 execution_mode 标签 |

---

## 5. 首次真实运行安全护栏

### 5.1 已存在护栏

| # | 护栏 | 代码位置 | 状态 |
|---|---|---|---|
| 1 | 不调用 apply-local | `task_worker.py` 全文件搜索 0 匹配 | **Pass** |
| 2 | 不调用 git-commit | `task_worker.py` 全文件搜索 0 匹配 | **Pass** |
| 3 | 不调用 git-push | `task_worker.py` 全文件搜索 0 匹配 | **Pass** |
| 4 | Budget Guard（日预算） | `DAILY_BUDGET_USD` 默认 $0.05 | Pass |
| 5 | Budget Guard（会话预算） | `SESSION_BUDGET_USD` 默认 $0.20 | Pass |
| 6 | 最大重试限制 | `MAX_TASK_RETRIES` 默认 2 | Pass |
| 7 | 只对真实 provider 成功生成交付物 | `_auto_create_run_deliverable()` 排除 `fallback_applied` 和 `provider_mock` | Pass |
| 8 | Stage 4 配置确认边界 | `ProjectDirectorSetupReadinessCard` 明确"不会自动启动 Worker" | Pass |

### 5.2 缺失护栏（建议在首次真实运行前补齐）

| # | 缺失项 | 严重度 | 建议模型 | 可否 Deferred |
|---|---|---|---|---|
| 1 | **运行前无 execution_mode 标签**：用户不知道当前是 simulate 还是 real | **高** | Codex | **否** |
| 2 | **运行前无安全确认**：无对话框确认"将调用真实 AI provider，可能产生费用" | **高** | Codex | **否** |
| 3 | **运行前无成本提示**：不显示 daily_budget/session_budget 余额 | 中 | Codex | 可（用户可手动查看设置/治理页预算） |
| 4 | **运行前无"不会改仓库"安全声明**：用户可能误以为会 git commit | 中 | Codex | 可（当前无 git 操作是代码事实，但用户不知） |
| 5 | **Provider 未配置时"启动一次执行"仍可点击**：`canRunWorkerOnce` 不检查 provider 配置状态 | **高** | Codex | **否** |

### 5.3 canRunWorkerOnce 当前逻辑

`DirectorChatEntry.tsx` 中 `canRunWorkerOnce` 的条件（需确认）：

目前不检查：
- Provider 是否已配置
- 当前是否 simulate 模式
- 日/会话预算是否充足

建议首次真实运行前增加 provider 配置检查。

---

## 6. 运行后验收路径

用户完成一次真实 Worker 运行后，可按以下路径验收：

| # | 验收项 | 前端入口 | 后端端点 | API 存在 | 前端存在 |
|---|---|---|---|---|---|
| 1 | 运行结果摘要 | 工作台 → 运行结果卡片 | `POST /workers/run-once` 返回 `WorkerRunOnceResponse` | Pass | Pass |
| 2 | 查看 Run 详情 | `/runs?runId=xxx` | `GET /runs/{id}/decision-trace` | Pass | Pass |
| 3 | 查看运行日志 | Run 详情页 → 技术日志 | `GET /runs/{id}/logs` | Pass | Pass |
| 4 | 查看 AI 摘要 | Run 详情页 `RunPrimarySummaryCard` | `GET /runs/{id}/ai-summary` | Pass | Pass |
| 5 | 查看执行模式 | Run 详情页 `executionModeLabel` | `WorkerRunOnceResponse.execution_mode` | Pass | Pass |
| 6 | 查看成本 | Run 详情页 cost 展示 | `WorkerRunOnceResponse.estimated_cost` / `token_pricing_source` | Pass | Pass |
| 7 | 查看交付物 | 成果中心 `/delivery` | `GET /deliverables?project_id=...` | Pass | Pass |
| 8 | 查看审批 | 成果中心 `/delivery?tab=approvals` | `GET /approvals/projects/{id}` | Pass | Pass |
| 9 | 查看任务状态 | 执行中心 `/execution?tab=tasks` | `GET /tasks` | Pass | Pass |
| 10 | 查看运行观测 | 执行中心 `/execution?tab=runs` | `GET /runs` | Pass | Pass |

**结论**：运行后验收路径全部畅通。

---

## 7. 当前缺口分类

### 7.1 必须 Codex 修（首次真实运行前）

| # | 缺口 | 优先级 | 改动范围 |
|---|---|---|---|
| 1 | "启动一次执行"按钮附近增加 execution_mode 标签 | P0 | `DirectorChatEntry.tsx`（前端 ~15 行） |
| 2 | 运行前增加安全确认对话框或文案（"将调用真实 AI provider"） | P0 | `DirectorChatEntry.tsx`（前端 ~20 行） |
| 3 | `canRunWorkerOnce` 增加 provider 配置状态检查 | P0 | `DirectorChatEntry.tsx`（前端 ~10 行） |

### 7.2 只需用户手动配置

| # | 配置项 | 操作 |
|---|---|---|
| 1 | API Key | 打开设置页 → 输入 DeepSeek/OpenAI API Key → 保存 |
| 2 | Base URL | 如需自定义端点，设置页修改 base_url |
| 3 | Model preset | 选择 DeepSeek / OpenAI / 自定义 |
| 4 | 测试连接 | 点击"测试连接"确认 auth_valid + endpoint_reachable |
| 5 | 确认 `WORKER_SIMULATE_EXECUTION_OVERRIDE` 未设置或为 `False` | 环境变量检查（本次为手动） |

### 7.3 必须等用户真实运行后才能判定

| # | 判定项 | 当前状态 |
|---|---|---|
| 1 | 真实 provider 调用是否成功 | simulate-only，未验证 |
| 2 | 真实 token/cost 数据是否准确 | 当前全部 heuristic |
| 3 | AI summary 在真实 provider 下质量 | simulate-only |
| 4 | Deliverable 自动创建在真实 provider 下是否正常 | guard 逻辑已验证，真实数据未验证 |
| 5 | Approval 自动创建在真实 provider 下是否正常 | guard 逻辑已验证，真实数据未验证 |
| 6 | GAP-01 和 GAP-05 是否可解除 | 取决于上述判定 |

---

## 8. GAP-01 / GAP-05 解除条件

### 8.1 GAP-01（真实 Provider 运行态证据）解除标准

以下全部满足 → GAP-01 可从 Partial 升至 Pass：

1. 用户在设置页完成 provider 配置（API Key + Base URL）
2. 用户通过"测试连接"按钮确认 auth_valid=true 且 model_usable=true
3. 用户手动点击"启动一次执行"
4. Worker 返回 `claimed=true` 且 `execution_mode` 包含 `provider_openai` 或 `provider_deepseek`
5. Run 记录中 `token_pricing_source` 为 `provider_reported`（而非 `heuristic.*`）
6. Run 记录中 `total_tokens > 0` 且 `estimated_cost > 0`
7. `GET /runs/{id}/ai-summary` 返回 AI 摘要且 `source` 非 simulate
8. 成果中心出现对应的交付物（自动生成）
9. 审批中心出现对应的待审批项（自动创建）

### 8.2 GAP-05（成本台账非 heuristic）解除标准

GAP-01 条件满足 + 以下附加条件：

1. 至少 1 条 Run 的 `token_pricing_source` = `provider_reported`
2. 至少 1 条 Run 的 `token_accounting_mode` ≠ `heuristic`
3. Cost Dashboard API 中 `mode_breakdown` 含 `provider_reported` 条目
4. GovernancePage CostMemoryTab 中成本来源标注从 heuristic 变为 provider_reported

---

## 9. 下一条 Codex 最小实现建议

```text
建议使用模型：Codex
任务类型：最小前端安全护栏（不改后端/Worker/Provider）
原因：首次真实运行前需要让用户明确知道当前是 simulate 还是 real，并获得安全确认。

目标：在"启动一次执行"按钮周围增加三个最小安全护栏。

改动文件：
仅 apps/web/src/pages/workbench/components/DirectorChatEntry.tsx

要求：
1. execution_mode 标签：在"启动一次执行"按钮上方展示当前模式
   - 如果后端 GET /provider-settings/openai 返回 configured=true → 显示"真实执行"标签
   - 如果未配置 → 显示"未配置 Provider"标签并禁用按钮
   - （WORKER_SIMULATE_EXECUTION_OVERRIDE 的判断暂不实现，留到后续）
2. 安全声明文案：在按钮下方增加一行小字
   "本次仅产生 Run/日志/摘要/交付物/审批，不会 git commit / git push / apply-local。"
3. 成本提示：如果 provider 已配置，显示
   "每日预算: ${daily_budget_usd}，本次可能产生费用。"

严格边界：
- 不改后端
- 不改 Worker
- 不改 Provider 配置逻辑
- 不自动启动 Worker
- 不新增路由
- 只改 DirectorChatEntry.tsx
```

---

## 10. Gate 结论

### 10.1 Stage 7-A0 audit: **Pass**

审计完成。Provider 配置后端+前端完整，安全护栏已识别（7 个已有 + 5 个缺失），验收路径全部畅通，GAP-01/GAP-05 解除标准已明确。

**当前判断**：系统**基本具备**用户手动首次真实运行的条件，但**建议首次运行前至少补齐 3 个 P0 安全护栏**（运行前 execution_mode 标签、安全确认文案、provider 配置检查）。

### 10.2 Stage 7-A implementation: **Pending**

等待 Codex 补齐安全护栏，然后用户手动执行首次真实运行。

### 10.3 AI Project Director total closure: **Partial**（不变）

GAP-01（真实 Provider 运行态证据）和 GAP-05（成本台账）的解除必须等用户真实运行后。CL-16 仍为 Evidence Partial。

### 10.4 CL-16: **不涉及**

CL-16 不得写 Pass。

---

## 11. 审查清单

- [x] origin/main commit 已核对：`ee82083653a244fa91b4d749b8b521ea7967c104`
- [x] `provider_settings.py` + `provider_config_service.py` + `config.py` 已审计
- [x] `executor_service.py` simulate/real 模式路由已审计
- [x] `task_worker.py` 安全护栏已确认（无 apply-local/git-commit/git-push）
- [x] `SettingsPage.tsx` Provider 配置前端已审计
- [x] `DirectorChatEntry.tsx` 启动执行按钮已审计
- [x] `runUserSummary.ts` execution mode 标签已确认
- [x] `runs.py` Run/summary/logs/decision-trace 端点已审计
- [x] `workers.py` Worker/run-once 端点已审计
- [x] 运行后验收路径全部 10 项已验证
- [x] 缺口分类：3 个 Codex P0 / 5 个用户配置 / 6 个待运行后判定
- [x] GAP-01/GAP-05 解除标准已明确
- [x] 下一条 Codex 建议已给出
- [x] 未改任何业务代码
- [x] 未改前端/后端/数据库/Worker
- [x] AI Project Director total closure 仍为 Partial
- [x] CL-16 不涉及，未写 Pass

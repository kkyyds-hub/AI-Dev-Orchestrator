# Day05：Provider 抽象层与执行路由后端主链

- 版本：`V5`
- Phase：`Phase 1`
- 模块：`模块B：Provider、Prompt、Token 与记忆主链`
- 工作包：`provider-gateway-and-executor-routing-backend`
- 当前状态：**已完成（工作包级）**
- owner skill：`write-v5-runtime-backend`
- 文档定位：**逐日执行包总入口 / 2026-04-14 最新回填**

---

## 1. 本日定位

截至 `2026-04-14`，Day05 已具备 provider 抽象层与执行路由后端主链，并且已有固定 `model=gpt-5.4` 的真实成功外呼证据；同时保留了 `provider_mock / simulate / shell` 安全回退链。该结论仅为 Day05 工作包级，不上升为 Phase 1 已完成。

## 2. 背景归属

- Phase：Phase 1
- 模块：模块B
- 工作包：`provider-gateway-and-executor-routing-backend`
- 关联母本章节：`2.3`、`2.4`、`2.8`、`2.9`、`#10`、`#12`
- 下一线程第一顺位：`write-v5-runtime-backend（Day06）`
- 下一线程第二顺位：`drive-v5-orchestrator-delivery（Day07）`

## 3. 当前真实状态

- `config.py`、`provider_config_service.py`、`openai_provider_executor_service.py`、`executor_service.py` 已形成真实 provider 最小闭环入口。
- 成功样本已存在：`runtime/data/logs/task-runs/6ed62fb9-b17a-4d97-af99-187be926d61b/370c6cbb-7321-4181-9bfc-2527835c20a7.jsonl`。
- 成功样本关键字段：`model_name=gpt-5.4`、`actual_execution_mode=provider_openai`、`fallback_applied=false`、`provider_receipt_source=real_provider`、`token_pricing_source=openai.chat_completions.usage`。
- 失败回退样本已存在：`runtime/data/logs/task-runs/d9d9a456-515a-4466-bc75-ff80e88f42a6/3f797d15-3229-44f1-b422-e0ad7abbd830.jsonl`（`endpoint_forbidden -> provider_mock`）。
- `shell:` / `simulate:` 分支仍保留，且回退字段结构化可观察。

## 4. 本日纳入范围

1. provider gateway / model routing 的后端主链。
2. executor 从策略结果进入 provider 抽象层。
3. 保留 shell/simulate fallback，并给 Day06 留 receipt/usage/token 接力条件。

## 5. 本日明确不纳入

1. 不把 Day05 写成 Phase 1 已完成。
2. 不在 Day05 宣称多 provider 矩阵已完成。
3. 不在 Day05 宣称成本产品化/外部账单对账已完成。
4. 不进入 `apps/web/` 前端改造。

## 6. 当日产物与改动焦点

- 已确认产物：
1. provider routing 主链与真实成功样本。
2. 真实 provider 失败回退样本。
3. `provider_mock / simulate / shell` 保留与结构化观察字段。
- 重点改动面：
1. `runtime/orchestrator/app/services/executor_service.py`
2. `runtime/orchestrator/app/services/openai_provider_executor_service.py`
3. `runtime/orchestrator/app/services/provider_config_service.py`
4. `runtime/orchestrator/app/services/mock_provider_executor_service.py`
5. `runtime/orchestrator/app/workers/task_worker.py`

## 7. 完成定义 / 非完成定义

### 完成定义
1. 真实 provider 最小调用闭环成立。
2. 至少 1 条真实 provider 成功证据存在（含 receipt/source）。
3. 至少 1 条真实 provider 失败回退证据存在。
4. 旧 `shell` / `simulate` 模式可用且可观察。

### 非完成定义
1. 把 Day05 写成 Phase 1 完成。
2. 把最小真实闭环夸大成多 provider 或成本产品化完成。
3. 用 mock/fallback 证据冒充真实 provider 成功证据。

## 8. 最低验证与证据要求

1. 真实 provider 成功样本（含 `gpt-5.4`、`provider_openai`、`fallback=false`）。
2. 真实 provider 失败回退样本（可观察 `fallback_reason_category`）。
3. `shell` / `simulate` 回归不被破坏。

## 9. 风险与交接

- 当前风险：
- 外部账单对账证据仍缺。
- 文档历史口径 `provider_reported` 与最新运行口径 `provider_openai` 并存，后续需统一说明。
- 假完成风险：**Day05 已完成不等于 Phase 1 已完成。**
- 本线程状态结论：`已完成（工作包级）`（本线程不做验收裁定）
- 下一线程 owner：`write-v5-runtime-backend（Day06）` / `drive-v5-orchestrator-delivery（Day07）`

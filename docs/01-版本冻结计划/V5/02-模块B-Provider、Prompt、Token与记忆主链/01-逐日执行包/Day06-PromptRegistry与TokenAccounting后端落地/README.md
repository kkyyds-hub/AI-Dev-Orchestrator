# Day06：Prompt Registry 与 Token Accounting v1 后端落地

- 版本：`V5`
- Phase：`Phase 1`
- 模块：`模块B：Provider、Prompt、Token 与记忆主链`
- 工作包：`prompt-registry-and-token-accounting-backend`
- 当前状态：**已完成（工作包级）**
- owner skill：`write-v5-runtime-backend`
- 文档定位：**逐日执行包总入口 / 2026-04-14 最新回填**

---

## 1. 本日定位

Day06 已具备工作包级主链与证据分层能力：真实 provider / mock / heuristic 三类口径可区分，fallback 已结构化可观察，run/log 中可区分真实 provider 与 mock/fallback。该结论不等于 Phase 1 已完成。

## 2. 背景归属

- Phase：Phase 1
- 模块：模块B
- 工作包：`prompt-registry-and-token-accounting-backend`
- 关联母本章节：`2.3`、`2.4`、`2.8`、`2.9`、`#10`、`#12`
- 下一线程第一顺位：`drive-v5-orchestrator-delivery`
- 下一线程第二顺位：`verify-v5-runtime-and-regression`

## 3. 当前真实状态

- `prompt_registry_service.py`、`prompt_builder_service.py`、`token_accounting_service.py` 已接入 worker 主链。
- 最新真实成功样本（`run_id=370c6cbb...`）已落盘：`token_accounting_mode=provider_openai`、`token_pricing_source=openai.chat_completions.usage`。
- 最新失败回退样本（`run_id=3f797d15...`）已落盘：`token_accounting_mode=provider_mock`，并具备结构化 fallback 字段。
- `task_worker.py` 的 `execution_finished` / `run_finalized` 已能观察 `actual_execution_mode` 与 fallback 相关字段。
- 兼容说明：`provider_reported` 仍存在于历史枚举/旧样本，本次正式回填以最新运行真值 `provider_openai/provider_mock/heuristic` 为主口径。

## 4. 本日纳入范围

1. prompt registry / builder 最小后端主链。
2. token accounting 的真实、mock、heuristic 证据分层。
3. run/log 可观察字段与 Day07 可消费合同。

## 5. 本日明确不纳入

1. 不把 Day06 写成 Phase 1 已完成。
2. 不承诺多 provider 细粒度账单矩阵已完成。
3. 不写成外部账单对账已完成。
4. 不提前吞 Day07 跨层联调。

## 6. 当日产物与改动焦点

- 实际产物：
1. prompt template / registry / builder 最小后端契约。
2. token accounting 分层口径与 fallback 可观察字段。
3. run 持久化字段与 Day07 消费合同。
- 重点改动面：
1. `runtime/orchestrator/app/services/prompt_registry_service.py`
2. `runtime/orchestrator/app/services/prompt_builder_service.py`
3. `runtime/orchestrator/app/services/token_accounting_service.py`
4. `runtime/orchestrator/app/services/executor_service.py`
5. `runtime/orchestrator/app/services/cost_estimator_service.py`
6. `runtime/orchestrator/app/workers/task_worker.py`

## 7. 完成定义 / 非完成定义

### 完成定义
1. 三类证据口径可区分：`provider_openai / provider_mock / heuristic`。
2. fallback 结构化可观察（run/log 字段可追踪）。
3. run/log 可区分真实 provider 与 mock/fallback。
4. token/pricing source 已有真实 provider 成功样本。

### 非完成定义
1. 只剩 schema 或文档叙述，没有运行证据。
2. 仅有 mock 证据却写成真实 provider 完成。
3. 把 Day06 写成 Phase 1 完成。

## 8. 最低验证与证据要求

1. 至少 1 条真实 provider 成功样本。
2. 至少 1 条真实 provider 失败回退样本。
3. 至少 1 条 heuristic 样本。
4. 关键字段（`token_accounting_mode`、`provider_receipt_id`、`token_pricing_source`、fallback 字段）可在 run/log 复核。

## 9. 风险与交接

- 当前风险：
- 旧口径 `provider_reported` 与新样本 `provider_openai` 并存，后续需统一对外口径说明。
- 外部账单对账证据仍缺，不能写成成本产品化完成。
- 下一线程 owner：`drive-v5-orchestrator-delivery`
- 当前不要误判为完成：Day06 工作包已完成，不等于 Phase 1 / 多 provider / 成本产品化已完成。

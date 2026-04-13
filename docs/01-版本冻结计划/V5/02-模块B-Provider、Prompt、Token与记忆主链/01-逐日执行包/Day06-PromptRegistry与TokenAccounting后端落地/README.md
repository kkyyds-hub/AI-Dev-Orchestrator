# Day06：Prompt Registry 与 Token Accounting v1 后端落地

- 版本：`V5`
- Phase：`Phase 1`
- 模块：`模块B：Provider、Prompt、Token 与记忆主链`
- 工作包：`prompt-registry-and-token-accounting-backend`
- 当前状态：**已完成**
- owner skill：`write-v5-runtime-backend`
- 文档定位：**逐日执行包总入口 / 完整展开**

---

## 1. 本日定位

Day06 是 Phase 1 的正式执行包；截至 `2026-04-12`，本包已完成工作包级实现、验证与正式裁定收口，但该结论只覆盖 Day06，不上升为 Phase 1 完成。

## 2. 背景归属

- Phase：Phase 1
- 模块：模块B
- 工作包：`prompt-registry-and-token-accounting-backend`
- 关联母本章节：`2.3`、`2.4`、`2.8`、`2.9`、`#10`、`#12`
- 下一线程第一顺位：`write-v5-runtime-backend`
- 下一线程第二顺位：`drive-v5-orchestrator-delivery`

## 3. 当前真实状态

- `prompt_registry_service.py`、`prompt_builder_service.py`、`token_accounting_service.py` 已落地并接入 worker 主链。
- `TokenAccountingService.build_snapshot(...)` 已统一 provider / non-provider 的 receipt 语义入口：provider 路径写 `provider_reported`，非 provider 路径显式写 `heuristic`。
- Run 持久化与 worker 返回已提供 `prompt_template_key`、`prompt_template_version`、`prompt_char_count`、`token_accounting_mode`、`provider_receipt_id`、`token_pricing_source` 等字段，可供 Day07 继续消费。
- 真实外部 provider 成本闭环与真实 provider receipt 对账证据仍未完成，但不属于 Day06 当前工作包 Pass 的必备闭环。

## 4. 本日纳入范围

1. 冻结 prompt template / registry / builder 的最小后端主链。
2. 冻结 token accounting v1 的真实 receipt 优先、fallback 显式记录的落盘口径。
3. 冻结 run / task / thread 后续可消费的 prompt render record 与 token usage 记录接口。

## 5. 本日明确不纳入

1. 不把 Prompt 产品中心完整 UI 放入 Day06。
2. 不承诺多 provider 细粒度账单兼容矩阵一次到位。
3. 不在 Day06 提前完成 Day07 的跨层联调。

## 6. 当日产物与改动焦点

- 实际产物：
1. prompt template / registry / builder 最小后端契约说明
2. token accounting service 与 receipt/fallback 口径说明
3. run 记录中的 prompt render / token usage 回填规则
4. Day07 可直接消费的 API / 字段 / 回显合同
- 重点改动面：
1. runtime/orchestrator/app/services/prompt_registry_service.py
2. runtime/orchestrator/app/services/prompt_builder_service.py
3. runtime/orchestrator/app/services/token_accounting_service.py
4. runtime/orchestrator/app/services/executor_service.py
5. runtime/orchestrator/app/services/cost_estimator_service.py
6. runtime/orchestrator/app/workers/task_worker.py

## 7. 开始前必须先读

1. docs/01-版本冻结计划/V5/00-V5总纲.md
2. docs/01-版本冻结计划/V5/00-V5正式冻结执行计划.md
3. docs/01-版本冻结计划/V5/02-模块B-Provider、Prompt、Token与记忆主链/00-模块说明.md
4. docs/01-版本冻结计划/V5/02-模块B-Provider、Prompt、Token与记忆主链/01-逐日执行包/Day05-Provider抽象层与执行路由后端主链/README.md
5. docs/01-版本冻结计划/V5/02-模块B-Provider、Prompt、Token与记忆主链/01-逐日执行包/Day05-Provider抽象层与执行路由后端主链/01-执行说明.md
6. runtime/orchestrator/app/services/executor_service.py
7. runtime/orchestrator/app/services/cost_estimator_service.py
8. runtime/orchestrator/app/workers/task_worker.py

## 8. 完成定义 / 非完成定义

### 完成定义
1. prompt template / registry / builder 已形成最小主链，而不是只有 schema。
2. token accounting v1 能写下 receipt 或 fallback 记录，不再只有启发式口径的隐式估算。
3. run 记录中可以回放 prompt render 与 token usage 的最小证据。
4. Day07 已有明确的跨层消费字段与接口契约。

### 非完成定义
1. 只有 prompt template schema，没有 builder / render 主链。
2. 只有 token 表字段，没有真实 receipt 或 fallback 记录链路。
3. 仍完全停留在字符数估算却宣称 receipt 已完成。
4. 没有给 Day07 留下可回显、可观察的接口合同。

## 9. 最低验证与证据要求

1. 至少 1 条 prompt render 证据。
2. 至少 1 条 token receipt 或 fallback 记录证据。
3. compile / smoke 不因 Day06 改动破坏 Day05 provider 路由。
4. Day07 需要消费的关键字段和示例响应已冻结。

## 10. 风险与交接

- 当前风险：
- 后续线程若把 mock provider receipt 误写成真实 provider 成本闭环，会放大 Day06 结论。
- token accounting 口径若再次与旧 cost estimate 混淆，Day07/Day08 会失去正式计量依据。
- 真实 provider receipt 对账证据未补齐前，Phase 1 不得写成已完成。
- 线程收尾后必须留下：
1. 实际新增/修改的 prompt 与 token 相关文件列表。
2. prompt render record 的最小字段定义。
3. token usage / receipt / fallback 字段说明。
4. Day07 需要消费的接口样例与回显字段。
5. 当前不要误判为 Prompt 产品中心已完成。
- 下一线程 owner：`drive-v5-orchestrator-delivery`
- 当前不要误判为完成：`Day06` 已完成，但这不等于真实外部 provider 成本闭环完成，也不等于 Phase 1 已完成。

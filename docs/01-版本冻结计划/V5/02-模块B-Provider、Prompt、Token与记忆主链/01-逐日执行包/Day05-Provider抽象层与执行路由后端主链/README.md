# Day05：Provider 抽象层与执行路由后端主链

- 版本：`V5`
- Phase：`Phase 1`
- 模块：`模块B：Provider、Prompt、Token 与记忆主链`
- 工作包：`provider-gateway-and-executor-routing-backend`
- 当前状态：**已完成**
- owner skill：`write-v5-runtime-backend`
- 文档定位：**逐日执行包总入口 / 正式裁定后版本**

---

## 1. 本日定位

Day05 已完成正式裁定，结论为 **Pass**。本次 Pass 只覆盖 Day05 工作包本身：provider 抽象层与执行路由后端主链、mock provider 最小执行证据、shell / simulate 回归，以及 Day06 可接手的契约交接；**不上升为 Phase 1 完成**。

## 2. 背景归属

- Phase：Phase 1
- 模块：模块B
- 工作包：`provider-gateway-and-executor-routing-backend`
- 关联母本章节：`2.3`、`2.4`、`2.8`、`2.9`、`#10`、`#12`
- 下一线程第一顺位：`write-v5-runtime-backend（Day06）`
- 下一线程第二顺位：`verify-v5-runtime-and-regression`

## 3. 当前真实状态

- `model_policy.py` 与 `model_routing_service.py` 已落下 provider / model routing 合同骨架。
- `task_worker.py -> executor_service.py` 已接入 routing contract；默认任务输入会先形成 execution plan，并已验证可进入 `provider_mock`。
- `shell:` / `simulate:` 显式前缀仍保留优先级，未被 provider contract 覆盖。
- `03-验证记录模板.md` 已回填 `2026-04-06` 的 compile / smoke / `provider_mock` / `shell_override` / `simulate_override` 证据。
- `receipt / usage / token` 的真实闭环仍未完成，但它们属于 Day06 及后续承接范围，不阻断 Day05 Pass。

## 4. 本日纳入范围

1. 新增或落定 provider gateway / model routing 的后端主链入口。
2. 让 executor 能从策略结果进入 provider 抽象层，而不是只停留在 shell / simulate。
3. 保留 shell / simulate fallback，并冻结 Day06 可接手的 receipt / usage 契约接口。

## 5. 本日明确不纳入

1. 不在 Day05 完成真实 provider adapter / registry / usage / token / receipt 全量闭环。
2. 不在 Day05 完成 prompt registry、token accounting 全量闭环。
3. 不进入 `apps/web/` 前端控制面改造。
4. 不把 worker 默认 memory recall、role model policy 或 Phase 1 整体闭环提前吞进 Day05。

## 6. 当日产物与改动焦点

- 已确认产物：
1. provider gateway / model routing 后端主链说明与对应代码改动面清单。
2. executor 接入 provider 抽象层的执行路径说明。
3. shell / simulate fallback 保留说明。
4. Day06 可直接接手的 receipt / usage / token 契约交接说明。
- 重点改动面：
1. `runtime/orchestrator/app/services/executor_service.py`
2. `runtime/orchestrator/app/services/strategy_engine_service.py`
3. `runtime/orchestrator/app/services/model_routing_service.py`
4. `runtime/orchestrator/app/domain/model_policy.py`
5. `runtime/orchestrator/app/services/mock_provider_executor_service.py`
6. `runtime/orchestrator/app/workers/task_worker.py`

## 7. 开始前必须先读

1. `docs/01-版本冻结计划/V5/00-V5总纲.md`
2. `docs/01-版本冻结计划/V5/00-V5总览.md`
3. `docs/01-版本冻结计划/V5/00-V5正式冻结执行计划.md`
4. `docs/01-版本冻结计划/V5/02-模块B-Provider、Prompt、Token与记忆主链/00-模块说明.md`
5. `docs/01-版本冻结计划/V5/01-模块A-规划冻结与执行编排/01-逐日执行包/Day03-验证验收与风险口径冻结/README.md`
6. `docs/01-版本冻结计划/V5/01-模块A-规划冻结与执行编排/01-逐日执行包/Day04-正式发布与Day05启动包冻结/README.md`
7. `docs/01-版本冻结计划/V5/02-模块B-Provider、Prompt、Token与记忆主链/01-逐日执行包/Day05-Provider抽象层与执行路由后端主链/03-验证记录模板.md`
8. `docs/01-版本冻结计划/V5/02-模块B-Provider、Prompt、Token与记忆主链/01-逐日执行包/Day05-Provider抽象层与执行路由后端主链/04-交接模板.md`

## 8. 完成定义 / 非完成定义

### 完成定义
1. executor 已具备 provider 抽象层入口，不再只有 shell / simulate 两条主线路径。
2. provider 路由依据与 `strategy_engine_service.py` 产出的模型策略存在实际接线。
3. 旧 `shell` / `simulate` 模式仍然可用，没有被 V5 改造破坏。
4. 至少有 1 条 provider 路由最小调用或 mock 调用证据。
5. 已给 Day06 留下明确的 receipt / usage / token 契约接力点。

### 非完成定义
1. 只有 provider interface / schema 草案，没有 executor 主链接线。
2. 只改了策略展示，不改执行链。
3. provider 路由建立后反而破坏了 shell / simulate 回退。
4. 没有任何 smoke / compile / 调用证据。
5. 把 Day06 的 prompt/token 工作提前混进来，却没有先把 Day05 自身主链收稳。

## 9. 最低验证与证据要求

1. Python compile 或最小 smoke 通过。
2. executor 经 provider gateway 路由的调用证据。
3. shell / simulate 回归未破坏的证据。
4. 若真实 provider 凭据不可用，允许以 mock / fallback 路由证据完成 Day05 验收，但必须诚实标记限制。

## 10. 风险与交接

- 当前风险：
- 真实 provider 风险：真实 provider adapter / registry / usage / token / receipt 闭环仍未形成，留给 Day06 及后续工作包承接。
- 兼容性风险：本轮仅确认最小回归无阻断证据；后续若继续扩展 provider 接线，仍需持续守住 `shell` / `simulate` 回退。
- 范围膨胀风险：Day05 只收 provider routing 主链，不进入 prompt / token / web。
- 假完成风险：**Day05 Pass 不等于真实 provider 已完成，不等于 usage / token / receipt 已闭环，不等于 Phase 1 已完成。**
- 线程收尾后已留下：
1. 实际改动的后端文件列表。
2. provider 路由契约说明。
3. 旧模式回归通过的最小证据。
4. Day06 可直接接手的 receipt / usage 契约。
5. Day05 已完成与未完成边界。
- 正式裁定：`Pass`
- 下一线程 owner：`write-v5-runtime-backend（Day06）`
- 本轮边界：`只完成 Day05 裁定与收口，不进入 Day06。`

# Day14：cache、成本聚合与 dashboard 联调

- 版本：`V5`
- Phase：`Phase 4`
- 模块：`模块D：Multi-Agent 协作与老板控制面`
- 工作包：`cache-and-cost-dashboard-delivery`
- 当前状态：**已规划**
- owner skill：`drive-v5-orchestrator-delivery`
- 文档定位：**逐日执行包总入口 / 完整展开**

---

## 本日定位

Day14 负责把 cache hit/miss、task/thread/role 三级成本聚合与 dashboard 最小版冻结成 Day15 可直接验证的正式执行包。

## 当前真实状态

- `apps/web/src/features/costs/` 当前不存在。
- `token_accounting_service.py` 当前不存在，因此不能假装已有真实成本拆账主链。
- `cost_estimator_service.py` 仍是启发式估算基线。
- `runtime/orchestrator/scripts/` 已有 V3/V4 smoke 脚本，但尚未看到 V5 专用脚本。

## 本日纳入范围

1. 冻结 cache / 成本聚合 / dashboard 的最小联调边界。
2. 冻结 Day15 verify 可直接验证的聚合字段、页面入口与 smoke 路线。
3. 冻结 token accounting 缺失时的 fallback / 缺证口径。

## 本日明确不纳入

1. 不展开 Day15 verify 实施细节。
2. 不提前进入 Day16 裁定结论。
3. 不把长期降本指标写成已经具备。

## 当日产物

1. cache / 成本聚合 / dashboard 最小联调合同说明
2. Day15 可直接验证的聚合字段、页面入口与 smoke 路线
3. token accounting 缺失时的 fallback / 缺证口径
4. Phase 4 联调风险与缺证说明

## 重点改动面

1. apps/web/src/features/costs/（计划新增）
2. apps/web/src/features/projects/ProjectOverviewPage.tsx
3. runtime/orchestrator/app/services/cost_estimator_service.py
4. runtime/orchestrator/app/services/token_accounting_service.py（计划新增）
5. runtime/orchestrator/scripts/ 下 V5 smoke 入口（后续线程）

## 开始前必须先读

1. docs/01-版本冻结计划/V5/00-V5总纲.md
2. docs/01-版本冻结计划/V5/00-V5正式冻结执行计划.md
3. docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/00-模块说明.md
4. docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/01-逐日执行包/Day13-TeamAssembly与TeamControlCenter串联交付/README.md
5. docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/01-逐日执行包/Day13-TeamAssembly与TeamControlCenter串联交付/04-交接模板.md
6. runtime/orchestrator/app/services/cost_estimator_service.py

## 完成定义

1. cache / 成本聚合 / dashboard 的最小联调边界已冻结。
2. Day15 verify 线程已拿到可直接验证的字段、入口与 smoke 路线。
3. fallback / 缺证口径已写清，不再把启发式估算伪装成真实 token accounting。
4. 风险与未完成项已诚实回填。

## 非完成定义

1. 只有静态成本卡片，没有聚合字段来源。
2. 只有 cost 表字段，没有 dashboard / API 联调合同。
3. 把启发式估算写成真实成本拆账。
4. 提前把 Day15 verify 结果写成已通过。

## 最低验证

1. 至少 1 条 cache 或成本聚合证据入口。
2. Day15 要验证的页面/接口/脚本入口已冻结。
3. fallback / 缺证说明已写入正式包。
4. 若 token accounting 仍缺失，必须明确不能写成完整成本闭环。

## 风险与接力

- 成本口径与 token accounting 口径混淆。
- dashboard 缺少稳定数据来源，导致 Day15 无法验证。
- 把 Day14 联调范围扩大成完整运营报表，破坏 16 天边界。

- 下一日接力：`verify-v5-runtime-and-regression` → `Day15：V5 E2E、回归与风险汇总`
- 当前不要误判为完成：`Day14` 仍是 **已规划**。

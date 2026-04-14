# Day15：V5 E2E、回归与风险汇总

- 版本：`V5`
- Phase：`Phase 5`
- 模块：`模块E：优化验收与正式收口`
- 工作包：`v5-e2e-regression-and-risk-rollup`
- 当前状态：**已规划**
- owner skill：`verify-v5-runtime-and-regression`
- 文档定位：**逐日执行包总入口 / 完整展开**

---

## 本日定位

Day15 负责把 V5 的 smoke、回归与风险汇总要求冻结成可直接交给验证线程执行的正式包。

## 当前真实状态

- `runtime/orchestrator/scripts/` 已存在 V3/V4 smoke 脚本组织方式，但尚未看到 V5 专用 smoke/e2e 脚本。
- Day15 的 owner 是 verify 线程 owner，因此必须先冻结验证对象、材料结构与缺证口径。
- 如果 Day05-Day14 任一关键链路仍缺证，Day15 只能形成 Partial / Blocked 输入。

## 本日纳入范围

1. 冻结 V5 E2E smoke、回归验证、风险分级汇总的正式材料结构。
2. 冻结 Day16 裁定需要消费的 verify 输出集合。
3. 冻结旧模式回归、缺证说明与 Partial / Blocked 输入边界。

## 本日明确不纳入

1. 不进入 Day16 裁定线程。
2. 不在 Day15 补写 Day13-Day14 的实现。
3. 不把 verify 计划写成 verify 已通过。

## 当日产物

1. V5 E2E / regression / risk rollup 验证包结构说明
2. Day16 可直接消费的 verify 输出材料清单
3. 旧模式回归与缺证说明模板
4. Phase 5 verify 风险与阻塞说明

## 重点改动面

1. runtime/orchestrator/scripts/ 下 V5 smoke / e2e 入口（后续线程）
2. Day05-Day14 的验证记录模板与交接模板
3. docs/01-版本冻结计划/V5/05-模块E-优化验收与正式收口/

## 开始前必须先读

1. docs/01-版本冻结计划/V5/00-V5总纲.md
2. docs/01-版本冻结计划/V5/00-V5正式冻结执行计划.md
3. docs/01-版本冻结计划/V5/05-模块E-优化验收与正式收口/00-模块说明.md
4. docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/01-逐日执行包/Day14-Cache成本聚合与Dashboard联调/README.md
5. docs/01-版本冻结计划/V5/04-模块D-Multi-Agent协作与老板控制面/01-逐日执行包/Day14-Cache成本聚合与Dashboard联调/04-交接模板.md
6. runtime/orchestrator/scripts/

## 完成定义

1. 至少 1 条 V5 闭环 smoke 路线被正式定义并可收证。
2. 回归记录、风险分级、缺证说明都有正式位置。
3. Day16 已拿到 verify 输出材料清单，而不是只拿到口头总结。
4. 若证据不足，已明确只能写成已实现待验证 / 进行中 / 阻塞。

## 非完成定义

1. 只有局部接口 smoke，没有 V5 闭环验证路线。
2. 发现回归但没有正式记录。
3. 没有 verify 输出清单就声称可以进入裁定。
4. 把 Day15 写成已经验证通过。

## 最低验证

1. 后端 smoke / API smoke / 页面 build / 闭环 smoke 至少各有正式记录入口。
2. 旧模式回归检查已被列为必填项。
3. 缺证时的状态口径与阻塞说明已预写。
4. Day16 需要消费的 verify 输出材料已经冻结。

## 风险与接力

- 验证范围过窄，只测局部链路。
- 风险分级与缺证说明未结构化，导致 Day16 裁定依据失真。
- 把 verify 计划当成 verify 已完成。

- 下一日接力：`accept-v5-milestone-gate` → `Day16：Pass / Partial / Blocked 裁定与正式收口`
- 当前不要误判为完成：`Day15` 仍是 **已规划**。

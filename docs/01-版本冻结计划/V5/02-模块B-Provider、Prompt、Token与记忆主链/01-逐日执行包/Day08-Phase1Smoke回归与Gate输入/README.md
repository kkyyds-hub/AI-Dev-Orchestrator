# Day08：Phase 1 Smoke、回归与 Gate 输入

- 版本：`V5`
- Phase：`Phase 1`
- 模块：`模块B：Provider、Prompt、Token 与记忆主链`
- 工作包：`phase1-smoke-and-gate-input`
- 当前状态：**已规划**
- owner skill：`verify-v5-runtime-and-regression`
- 文档定位：**逐日执行包总入口 / 完整展开**

---

## 1. 本日定位

Day08 是 Phase 1 的正式执行包，当前已经完整展开到后续线程可直接接手的粒度，但仍然只是**正式规划冻结**，不是已开始实现。

## 2. 背景归属

- Phase：Phase 1
- 模块：模块B
- 工作包：`phase1-smoke-and-gate-input`
- 关联母本章节：`2.3`、`2.4`、`2.8`、`2.9`、`#10`、`#12`
- 下一线程第一顺位：`verify-v5-runtime-and-regression`
- 下一线程第二顺位：`accept-v5-milestone-gate`

## 3. 当前真实状态

- Day08 的 owner 不是实现者，而是验证线程 owner，因此正式规划必须先写清验证对象与缺证口径。
- Phase 1 要验证的不只是 provider 调用，还包括 prompt render、token receipt/fallback、memory recall 与控制面回显是否形成闭环。
- 若 Day05-Day07 仍有缺证或回归未核，Day08 只能输出 partial/gap 输入，而不能伪装成通过材料。

## 4. 本日纳入范围

1. 冻结 Phase 1 的 smoke 证据清单、回归记录结构与 gate 输入材料构成。
2. 冻结 provider → prompt → token → memory recall → control surface 的最小闭环验证路线。
3. 冻结进入 M1 门槛时需要提交给 `accept-v5-milestone-gate` 的正式材料集合。

## 5. 本日明确不纳入

1. 不在 Day08 承担实现返工线程。
2. 不提前裁定 Pass / Partial / Blocked。
3. 不扩展到 Phase 2 / Day09 的执行细化。

## 6. 当日产物与改动焦点

- 预期产物：
1. Phase 1 smoke 场景与证据清单
2. 旧模式回归记录模板与最小必测项
3. Phase 1 gate 输入包目录与材料要求
4. Day09 继续推进前允许 / 不允许进入的口径说明
- 重点改动面：
1. Day05-Day07 的状态回填模板与验证记录模板
2. V5 根文档中的 M1 门槛定义
3. 后续 verify / accept 线程要引用的正式证据目录（文档层）

## 7. 开始前必须先读

1. docs/01-版本冻结计划/V5/00-V5总纲.md
2. docs/01-版本冻结计划/V5/00-V5正式冻结执行计划.md
3. docs/01-版本冻结计划/V5/02-模块B-Provider、Prompt、Token与记忆主链/00-模块说明.md
4. Day05 README / 执行说明 / 验证记录模板
5. Day06 README / 执行说明 / 验证记录模板
6. Day07 README / 执行说明 / 验证记录模板
7. V1~V4 与当前主线相关的 smoke / 回归基线材料

## 8. 完成定义 / 非完成定义

### 完成定义
1. 至少 1 条 provider → prompt → token → memory recall → control surface 闭环 smoke 路线被明确定义并可收证。
2. 旧模式回归检查项被正式写入验证包，而不是口头提醒。
3. 提交给 `accept-v5-milestone-gate` 的 gate 输入材料已写清构成、证据来源与缺证口径。
4. 若证据不足，已明确只能写成 `已实现待验证` / `进行中` / `阻塞`。

### 非完成定义
1. 只有局部接口 smoke，没有 Phase 1 闭环路线。
2. 发现回归但没有正式记录。
3. 只有实现说明，没有 verify 证据结构。
4. 没有 gate 输入材料清单就宣称可以进入裁定。

## 9. 最低验证与证据要求

1. 后端 smoke / API smoke / 页面 build / 闭环 smoke 至少各有对应记录入口。
2. shell / simulate 回归检查已被列为必填项。
3. 缺证时的状态口径与阻塞说明已预写。
4. 提交 accept 线程前的材料清单已经固定。

## 10. 风险与交接

- 当前风险：
- 验证范围过窄，只测 provider，不测 prompt/token/memory/UI 闭环。
- 发现问题但没有结构化记录，导致 Day16 裁定依据失真。
- 把 Day08 写成已经通过，而不是待 verify 线程执行。
- 线程收尾后必须留下：
1. Phase 1 smoke 场景清单与证据路径。
2. 回归记录与缺证说明。
3. 提交给 `accept-v5-milestone-gate` 的 gate 输入材料列表。
4. 若未满足 M1，必须明确是 Partial 还是回退补齐。
- 下一线程 owner：`accept-v5-milestone-gate`
- 当前不要误判为完成：`Day08` 仍处于 **已规划**，必须由后续真实线程回填状态。

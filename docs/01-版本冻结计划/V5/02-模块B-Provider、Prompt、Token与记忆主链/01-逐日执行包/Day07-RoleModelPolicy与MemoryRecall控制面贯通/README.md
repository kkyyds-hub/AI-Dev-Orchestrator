# Day07：Role Model Policy、Memory Recall 与控制面贯通

- 版本：`V5`
- Phase：`Phase 1`
- 模块：`模块B：Provider、Prompt、Token与记忆主链`
- 工作包：`phase1-cross-layer-delivery`
- 当前状态：**已完成**
- owner skill：`drive-v5-orchestrator-delivery`
- 文档定位：**逐日执行包总入口 / 正式回填后状态**

---

## 1. 本日定位

Day07 仍是 Phase 1 的正式执行包，截至 **2026-04-14** 的统一口径：

- Step2 已完成：worker 默认 `include_project_memory=True` 主链接线成立；
- Step3 已完成：memory recall 最小前端回显接点成立；
- Step5 已完成：`/workers/run-once` 已形成 Provider / Prompt / Token 字段合同（后端 DTO + 前端类型对齐）；
- Step6 已完成：首页“最近一次手动执行”区块已新增 Provider / Prompt / Token 最小回显卡片；
- Step8 / Step9 / Step10 已有事实并保持成立；
- **截至 2026-04-16：Day07 已完成；Day08 仅可准备输入，尚未开始执行。**

## 2. 背景归属

- Phase：`Phase 1`
- 模块：`模块B`
- 工作包：`phase1-cross-layer-delivery`
- 关联母本章节：`2.3`、`2.4`、`2.8`、`2.9`、`#10`、`#12`
- 下一线程第一顺位：`drive-v5-orchestrator-delivery`
- 下一线程第二顺位：`verify-v5-runtime-and-regression`

## 3. 当前真实状态

### 已成立
- `task_worker.py` 已显式把 `include_project_memory=True` 接入默认执行主链。
- `workers` API DTO 已对外返回 memory recall 字段：
  - `project_memory_enabled`
  - `project_memory_query_text`
  - `project_memory_item_count`
  - `project_memory_context_summary`
- `workers` API DTO 已对外返回 Provider / Prompt / Token 字段：
  - `provider_key`
  - `prompt_template_key`
  - `prompt_template_version`
  - `prompt_char_count`
  - `token_accounting_mode`
  - `provider_receipt_id`
  - `token_pricing_source`
  - `prompt_tokens` / `completion_tokens` / `total_tokens`
- 首页“最近一次手动执行”区域已真实挂载：
  - `Project Memory Recall` 卡片
  - `Provider / Prompt / Token` 卡片
- Role Model Policy 最小运行时闭环已成立，并贯通到 preview / worker / console latest run。
- latest run 控制面已增强并回显：
  - `provider / prompt / token`
  - `prompt_char_count / estimated_cost / created_at / finished_at`
- 浏览器级证据已固化：
  - `runtime/orchestrator/tmp/day07-browser-evidence/01-home-manual-entry.png`
  - `runtime/orchestrator/tmp/day07-browser-evidence/02-project-strategy-preview.png`
  - `runtime/orchestrator/tmp/day07-browser-evidence/03-project-latest-run-control-surface.png`

### 后续治理项（非 Day07 硬阻塞）
- provider / prompt / token 控制面已增强，但“完整老板治理面”属于后续治理目标。
- Day08 输入材料仍需按 verify 线程完成模板化收敛，但该项不阻塞 Day07 完成判定。

## 4. 本日纳入范围

1. worker 默认 memory recall 接入正式执行主链。
2. memory recall 字段最小前端回显。
3. Provider / Prompt / Token 合同接通与最小前端回显。

## 5. 本日明确不纳入

1. 不把 Day07 扩大为完整多页面 UI 重构。
2. 不提前进入 Day08。
3. 不做 Pass / Partial / Blocked 裁定。
4. 不把 Step2 / Step3 / Step5 / Step6 的局部证据外推成 Day07 全量完成。

## 6. 当前已固化证据

### Step2
- worker 默认 recall 主链已接通。
- 已记录降级路径证据：
  - `project_memory_enabled = true`
  - `project_memory_item_count = 0`
  - `project_memory_context_summary` 返回真实降级摘要

### Step3
- 首页“最近一次手动执行”区域已消费 memory recall 字段。
- 已接通字段：
  - `project_memory_enabled`
  - `project_memory_query_text`
  - `project_memory_item_count`
  - `project_memory_context_summary`

### Step5
- `/workers/run-once` 返回 DTO 与 `from_result` 映射已包含 Provider / Prompt / Token 字段。
- 前端 `WorkerRunOnceResponse` 类型已同步上述字段合同。
- 上游运行级证据沿用 Day06 持久化 smoke（`v5_day06_step6_run_persistence_smoke.py`）。

### Step6
- 首页“最近一次手动执行”区块新增 `Provider / Prompt / Token` 卡片，真实消费 Step5 合同字段。
- 编译级证据：`apps/web` 执行 `node .\\node_modules\\typescript\\bin\\tsc -b` 通过。
- 环境复核更新（2026-04-14）：
  - `npm.cmd run build` 当前环境已通过。
  - `playwright install chromium` 与 `chromium-headless-shell` 当前环境已通过。
  - 本机 `msedge` channel 可用于 Day07 浏览器截图联调。

## 7. 完成定义 / 非完成定义

### 当前已满足的子项
1. worker 默认 memory recall 已成为正式主链的一部分，并已有可观测证据。
2. memory recall 已不只是后端字段，老板首页已有最小前端回显接点。
3. Provider / Prompt / Token 已具备后端 DTO 到前端展示的最小闭环接点。
4. Role Model Policy 已形成最小运行时闭环并可在控制面观测。
5. 浏览器级截图证据已形成。

### 后续项（不构成 Day07 完成阻塞）
1. provider / prompt / token 的完整老板控制面仍未收口。
2. 多入口治理与更深控制面语义仍需补强。
3. Day08 输入线程的执行边界与记录模板仍需在 Day08 线程内确认。

## 8. 最低验证与证据要求

当前已固化的最低证据：
1. 至少 1 条 worker -> memory recall -> API / 页面回显链路证据。
2. Provider / Prompt / Token 合同字段在后端 DTO 与前端类型、页面三处一致。
3. 前端 TypeScript 编译通过（`tsc -b`）。

后续仍需补强：
1. 控制面从 latest run 扩展到更多老板入口并保持一致性。
2. Role Model Policy 的边界回归持续补强。
3. 在 Day07 范围内继续补强自动化证据密度。

## 9. 风险与交接

- 当前风险：Step2/3/5/6 证明了“最小接点已成立”，不等于 Day07 已收口。
- 当前缺口：Role Model Policy、provider / prompt / token 完整老板面、补强验证。
- 下一棒任务：继续补 Day07 剩余缺口或补强验证，不进入 Day08。
- 当前不要误判为完成：`Day07` 仍处于 **进行中**。

## 10. 2026-04-15 增量回填（same-sample drill-down 稳定锚点 + 聚合页减负）

- 本轮只推进 1 个 Day07 单切片：不扩后端合同，只把同一份 latest-run/runtime 事实在 homepage task row -> project detail latest run -> strategy preview 这条链上的观测与验证锚点稳定下来。
- 前端结构治理最小落点：
  - 将 boss drill-down 的 hash / authoritative project ownership / feedback 编排从 `ProjectOverviewPage.tsx` 下沉到 `features/projects/hooks.ts` 与 `features/projects/lib/bossDrilldown.ts`
  - 聚合页继续只保留入口挂载、项目选择、事件转发与区块编排，不继续堆叠 drill-down 细节实现
- 稳定锚点补齐：
  - homepage task row 新增 same-sample 运行时卡片、字段与 estimated cost 的 `data-testid`
  - `ProjectLatestRunControlSurface` 新增 drill-down 状态、runtime/policy 卡片与字段级 `data-testid`
  - `StrategyDecisionPanel` 新增 drill-down 状态、runtime/policy 卡片与字段级 `data-testid`
- 复用既有证据脚本并切到稳定锚点，不再主要依赖中文文案或布局筛选：
  - `apps/web/scripts/day07_same_sample_page_consistency.spec.mjs`
- 本轮最小验证：
  - `apps/web -> npm.cmd run build`
  - `npx.cmd --prefix apps/web playwright test apps/web/scripts/day07_same_sample_page_consistency.spec.mjs --workers=1`
- 状态口径：
  - 本轮只补上 Day07 一个前端治理型子缺口，不代表 Day07 已收口
  - 当前仍在 Day07，不进入 Day08

## 11. 2026-04-16 增量回填（Project Latest Run -> Strategy Preview 最小可操作路径）

- 本轮只推进 1 个新的 Day07 单切片：`Project Latest Run -> Strategy Preview` 同样本 run 维度 drill-down。
- 本轮纳入范围：
  - 复用既有 `ProjectLatestRunControlSurface` 入口按钮 `goto-strategy-preview-from-latest-run`，将 drill-down source 明确归因为 `project_latest_run`。
  - 复用既有 same-sample 浏览器脚本，在同一脚本内补充“project latest run 入口直达 strategy preview”的最小回归路径与证据落盘。
  - 证据索引链补充新别名与批次快照：
    - latest 别名：`42-day07-project-latest-run-to-strategy-preview-drilldown-evidence.json`
    - 截图证据：`41-project-latest-run-to-strategy-preview-drilldown.png`
- 本轮明确不做：
  - 不新增后端 route / DTO / worker / service / repository / schema。
  - 不扩成新老板治理面，不新增筛选系统，不进入 Day08。
  - 不做 Pass / Partial / Blocked 裁定。
- 本轮最小验证要求沿用 Day07 既有口径：
  - `apps/web -> npm.cmd run build`
  - `npx.cmd --prefix apps/web playwright test apps/web/scripts/day07_same_sample_page_consistency.spec.mjs --workers=1`
- 状态口径：
  - 本轮只是 Day07 单切片推进，Day07 仍为**进行中**。
  - 仍在 Day07，不进入 Day08。

## 12. 2026-04-16 增量回填（Project Latest Run -> Task Detail 最小可操作路径）

- 本轮只推进 1 个新的 Day07 单切片：`Project Latest Run -> Task Detail` 同样本 `task/run` 维度 drill-down。
- 本轮纳入范围：
  - 在 `ProjectLatestRunControlSurface` 新增入口按钮 `goto-task-detail-from-project-latest-run`，支持从项目 latest run 控制面直接进入 Task Detail。
  - 入口事件保持聚合页边界：由 `ProjectDetailSection` 仅做事件转发与滚动定位，不新增后端合同、不新增聚合逻辑堆叠。
  - 复用既有 same-sample 脚本并扩展同脚本回归路径，补充证据别名与批次快照：
    - latest 别名：`44-day07-project-latest-run-to-task-detail-drilldown-evidence.json`
    - 截图证据：`43-project-latest-run-to-task-detail-drilldown.png`
- 本轮明确不做：
  - 不新增后端 route / DTO / worker / service / repository / schema。
  - 不扩为新老板治理面、不新增筛选系统、不进入 Day08。
  - 不做 Pass / Partial / Blocked 裁定。
- 本轮最小验证要求沿用 Day07 既有口径：
  - `apps/web -> npm.cmd run build`
  - `npx.cmd --prefix apps/web playwright test apps/web/scripts/day07_same_sample_page_consistency.spec.mjs --workers=1`
- 状态口径：
  - 本轮只是 Day07 单切片推进，Day07 仍为**进行中**。
  - 仍在 Day07，不进入 Day08。

## 13. 2026-04-16 增量回填（latest same-sample 闭环复核收口）

- 本轮仅回填已被独立 verify 线程确认成立的 latest 批次事实，不新增实现、不扩验证范围。
- latest 批次与三元组（与索引一致）：
  - `evidence_batch_id=day07-same-sample-20260416t052038526z-93b2b0fa3637`
  - `project_id=464919fa-534a-4107-a828-f4d34a369870`
  - `task_id=dd034640-b07f-4646-89ce-6f5dd457a5a0`
  - `run_id=93b2b0fa-3637-4c3e-928c-a831a20a2acf`
- latest 索引入口：
  - `runtime/orchestrator/tmp/day07-browser-evidence/day07-same-sample-latest-batch-index.json`
  - `runtime/orchestrator/tmp/day07-browser-evidence/day07-same-sample-batch-index--day07-same-sample-20260416t052038526z-93b2b0fa3637.json`
- 当前 same-sample 闭环已成立的 6 条路径：
  1. `Project Latest Run -> Task Detail`
  2. `Project Latest Run -> Strategy Preview`
  3. `Project Latest Run -> Run Log`
  4. `Task Detail -> Strategy Preview`
  5. `Run Log -> Strategy Preview`
  6. `Strategy Preview -> Run Log`
- 当前状态边界：
  - Day07 当前 same-sample 闭环验证成立。
  - Day07 整体仍为**进行中**，不进入 Day08。
  - 仍未完成项保持不变：完整老板治理面、更深控制面语义、Day08 前正式收口。

## 14. 2026-04-16 增量回填（Strategy Preview -> Project Latest Run 最小可操作回跳）

- 本轮只推进 1 个新的 Day07 单切片：`Strategy Preview -> Project Latest Run` 同一样本 `task/run` 维度回跳。
- 本轮纳入范围：
  - 在 `StrategyDecisionPanel` 新增回跳入口 `goto-project-latest-run-from-strategy-preview`。
  - 回跳事件下沉到 `features/projects/hooks.ts`，由 drill-down context 写回 `source=strategy_preview` 并滚动定位 `project-latest-run-control-surface`。
  - 复用既有 same-sample 脚本并扩展同脚本回归路径，补充证据别名与批次快照：
    - latest 别名：`46-day07-strategy-preview-to-project-latest-run-drilldown-evidence.json`
    - 截图证据：`45-strategy-preview-to-project-latest-run-drilldown.png`
- latest 批次与三元组（与索引一致）：
  - `evidence_batch_id=day07-same-sample-20260416t054306607z-dc4372a2c1e4`
  - `project_id=6d12f5cc-2503-480a-b7e6-7b56b82df6da`
  - `task_id=9fc1d017-6d9f-4cc8-bc54-d91f10a25870`
  - `run_id=dc4372a2-c1e4-45c4-b3ec-9d04331e7102`
- latest 索引入口：
  - `runtime/orchestrator/tmp/day07-browser-evidence/day07-same-sample-latest-batch-index.json`
  - `runtime/orchestrator/tmp/day07-browser-evidence/day07-same-sample-batch-index--day07-same-sample-20260416t054306607z-dc4372a2c1e4.json`
- 当前 same-sample 闭环已成立路径更新为 7 条：
  1. `Project Latest Run -> Task Detail`
  2. `Project Latest Run -> Strategy Preview`
  3. `Project Latest Run -> Run Log`
  4. `Task Detail -> Strategy Preview`
  5. `Run Log -> Strategy Preview`
  6. `Strategy Preview -> Run Log`
  7. `Strategy Preview -> Project Latest Run`
- 本轮明确不做：
  - 不新增后端 route / DTO / worker / service / repository / schema。
  - 不扩完整老板治理面，不新增筛选系统，不进入 Day08。
  - 不做 Pass / Partial / Blocked 裁定。
- 状态口径：
  - 本轮只是 Day07 单切片推进，Day07 仍为**进行中**。
  - 仍在 Day07，不进入 Day08。

## 15. 2026-04-16 最终口径收束（Day07 正式收口 / Day08 输入可准备）

- 本节仅基于 latest 索引与 latest 批次索引做事实收束，不新增实现、不新增验证执行。
- latest 索引：
  - `runtime/orchestrator/tmp/day07-browser-evidence/day07-same-sample-latest-batch-index.json`
- latest 批次索引：
  - `runtime/orchestrator/tmp/day07-browser-evidence/day07-same-sample-batch-index--day07-same-sample-20260416t055217289z-165efd8ad38b.json`
- latest 三元组（与索引一致）：
  - `evidence_batch_id=day07-same-sample-20260416t055217289z-165efd8ad38b`
  - `project_id=03b69347-98cb-48f5-a507-9c347ee5d4ff`
  - `task_id=342a79d0-532e-4f66-98d7-121b8baaf71b`
  - `run_id=165efd8a-d38b-426f-9b74-6e1ebdba7f39`
- same-sample 关键 alias 与 latest 批次一致（9/9）：
  - `28 / 32 / 34 / 36 / 38 / 40 / 42 / 44 / 46`

### Day07 当前统一状态
- `已完成`。
- Day08 尚未开始执行；当前仅具备“输入可准备”条件。

### Day07 已成立事实
1. Step2 / Step3 / Step5 / Step6 / Step8 / Step9 / Step10 的既有事实仍成立。
2. same-sample drill-down 关键别名已统一指向 latest 批次。
3. latest 三元组可由 `latest-batch-index` 一次性定位并复核。
4. verify 已确认 7 条闭环路径成立：`Project Latest Run -> Task Detail`、`Project Latest Run -> Strategy Preview`、`Project Latest Run -> Run Log`、`Task Detail -> Strategy Preview`、`Run Log -> Strategy Preview`、`Strategy Preview -> Run Log`、`Strategy Preview -> Project Latest Run`。
5. 对照 `00-V5正式冻结执行计划.md` 的 Day07 合同，`role model policy + memory recall + 控制面最小贯通 + Day08 闭环 smoke 前提` 已具备。

### Day07 后续治理项（非硬阻塞）
1. 完整老板治理面尚未正式收口（后续更高愿景，不属于 Day07 最小完成定义）。
2. 更深控制面语义与多入口治理仍需补强（后续治理语义，不属于 Day07 硬要求）。
3. Day08 verify 输入模板化与回归优先级确认仍需补齐（属于 Day08 输入治理，不阻塞 Day07 完成）。

### 为什么当前可写“已完成”
1. Day07 合同要求是“最小贯通 + 闭环 smoke 前提”，不是“完整老板治理面全量交付”。
2. 当前剩余项均被归类为后续愿景/治理深化/Day08 输入材料，不属于 Day07 完成定义内硬阻塞。
3. 本轮不做 accept 裁定，也不进入 Day08 执行；仅完成 Day07 正式回填与边界澄清。

### Day08 输入准备（最小清单）
- 可直接消费：
  - latest 索引与 latest 批次索引
  - latest 三元组（project/task/run）
  - 关键 alias `28/32/34/36/38/40/42/44/46`
- 仍缺输入：
  - Day08 verify 线程的执行边界与最小回归优先级确认
  - Day08 线程要使用的固定“通过/失败记录模板”落点
- 禁止误写：
  - 不得把“Day08 输入准备完成”写成“进入 Day08 执行”
  - 不得把“Day08 输入可准备”写成“Day08 已开始执行”

### 根文档同步判断
- 本轮已最小同步 `00-V5总览.md` / `00-V5总纲.md`。
- 同步边界：仅更新 Day07 已完成与 Day08 未开始执行口径，不扩写 Day08 实施事实。

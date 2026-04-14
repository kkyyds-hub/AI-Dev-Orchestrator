# Day07：Role Model Policy、Memory Recall 与控制面贯通

- 版本：`V5`
- Phase：`Phase 1`
- 模块：`模块B：Provider、Prompt、Token与记忆主链`
- 工作包：`phase1-cross-layer-delivery`
- 当前状态：**进行中**
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
- **当前只是 Day07 的继续回填，不代表 Day07 已完成；当前仍在 Day07，不进入 Day08。**

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

### 仍未完成
- provider / prompt / token 控制面已增强，但仍非“完整老板治理面”。
- Day07 仍未达到可进入 Day08 的正式收口状态。

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

### 当前仍不满足的子项
1. provider / prompt / token 的完整老板控制面仍未收口。
2. 多入口治理与更深控制面语义仍需补强。
3. Day07 还未达到可进入 Day08 的正式收口状态。

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

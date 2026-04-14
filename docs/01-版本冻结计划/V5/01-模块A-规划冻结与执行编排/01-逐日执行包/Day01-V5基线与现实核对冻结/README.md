# Day01：V5 基线与现实核对冻结

- 版本：`V5`
- Phase：`冻结准备`
- 模块：`模块A：规划冻结与执行编排`
- 工作包：`v5-baseline-reality-audit`
- 当前状态：**已完成**
- owner skill：`manage-v5-plan-and-freeze-docs`
- 文档定位：**逐日执行包总入口 / Day01 正式收口入口**

---

## 1. 本日定位

Day01 已按“母本方向 + 仓库正式文档 + 当前代码现实”三线对齐完成 V5 基线冻结；本日收口只代表基线文档线程完成，不代表 V5 已实现。

## 2. 本日正式产物

1. `docs/01-版本冻结计划/V5/00-V5总纲.md`
2. `docs/01-版本冻结计划/V5/00-V5总览.md`
3. `docs/01-版本冻结计划/V5/00-V5正式冻结执行计划.md`
4. `docs/01-版本冻结计划/V5/01-模块A-规划冻结与执行编排/00-模块说明.md`
5. 本目录下的状态回填、验证记录、交接材料

## 3. 正式文档边界结论

1. 仓库正式入口只认 `docs/01-版本冻结计划/`；V5 正式边界只认 `docs/01-版本冻结计划/V5/`。
2. 桌面母本 `C:/Users/Administrator/Desktop/三省六部文件/AI-Dev-Orchestrator-V5-Plan.md` 是高优先输入，但不替代仓库正式落盘体系。
3. `.tmp/local-drafts/`、历史散落文档与桌面草案均不属于本轮正式交付物。

## 4. 范围内 / 范围外

### 范围内
1. 明确 V5 本轮 16 天承诺主线与 Phase 节奏。
2. 明确哪些能力是仓库已存在基础，哪些能力只是 V5 待新增工作包。
3. 把范围边界、现实差距、状态词依据与 Day02 接力条件写入正式文档。

### 范围外
1. 任何 backend / web / verify / review / accept 实现动作。
2. 把策略路由预览、记忆检索、项目总览页面写成 V5 已实现完成。
3. 提前进入 Day02 以后工作的目录合同冻结、验收口径冻结或实现细节深挖。

## 5. 现实差距结论

1. `strategy_engine_service.py` 已能做模型层级与路由解释，但 `executor_service.py` 当前仍只有 `shell / simulate` 最小执行模式，真实 Provider 主链未落地。
2. `project_memory_service.py` 与 `context_builder_service.py` 已支持任务记忆召回，但 `task_worker.py` 默认构建上下文时未显式接入 `include_project_memory=True`，记忆尚未进入默认执行主链。
3. `cost_estimator_service.py` 仍采用启发式 token / 成本估算，不是真实 Provider 计费口径。
4. 前端已有 `ProjectOverviewPage.tsx`、`StrategyDecisionPanel.tsx`、`ProjectMemoryPanel.tsx` 等基础面板，但未见 agent session / team control center / prompt registry / cache dashboard 的现成页面文件。
5. 本轮最小目录抽查未发现以 `provider`、`prompt`、`token`、`agent`、`team`、`cache` 命名的现成服务或页面文件，因此这些能力仍应被视为 V5 后续工作包，而非当前现实。

## 6. 当前状态词依据

- Day01 写为 `已完成`：因为正式文档、状态回填、验证记录、交接材料已完成回填。
- V5 写为 `进行中`：因为只完成了 Day01，Day02-Day16 尚未执行。
- Day02-Day16 保持 `已规划`：因为本轮没有推进对应日包内容。

## 7. 风险与交接

### 当前最重要的 3 条风险
1. 若 Day02 忽略 Day01 的现实差距，后续工作包合同会建立在错误假设上。
2. 若后续线程把“策略预览 / 记忆检索 / 项目总览”误写为“真实 Provider / 默认记忆主链 / 多 Agent 控制中心已完成”，会造成虚假完成。
3. 若 Day02 不继续冻结目录、改动面与 owner 口径，Day05 以后实现线程仍会重复拆包。

- 下一线程 owner：`manage-v5-plan-and-freeze-docs`
- 交接要求：Day02 只继续冻结工作包、目录、owner 与改动面合同，不得绕过 Day01 基线直接进入实现。

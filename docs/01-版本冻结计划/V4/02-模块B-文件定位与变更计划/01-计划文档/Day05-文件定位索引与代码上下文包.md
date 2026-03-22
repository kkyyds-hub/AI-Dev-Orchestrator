# Day05 文件定位索引与代码上下文包

- 版本：`V4`
- 模块 / 提案：`模块B：文件定位与变更计划`
- 原始日期：`2026-04-26`
- 原始来源：`V4 正式版总纲 / 模块B：文件定位与变更计划 / Day05`
- 当前回填状态：**未开始**
- 回填口径：当前文档为 V4 冻结版计划，尚未开始实现；后续只按 Day05 范围回填，不提前跨 Day 扩 scope。

---

## 今日目标

提供面向任务的最小文件定位能力，把项目任务第一次落到候选文件集合，并生成可控大小的代码上下文包。

---

## 当日交付

1. `runtime/orchestrator/app/domain/code_context_pack.py`
2. `runtime/orchestrator/app/services/codebase_locator_service.py`
3. `runtime/orchestrator/app/services/context_builder_service.py`
4. `runtime/orchestrator/app/api/routes/repositories.py`
5. `apps/web/src/features/repositories/components/FileLocatorPanel.tsx`
6. `runtime/orchestrator/scripts/v4b_day05_code_locator_smoke.py`

---

## 验收点

1. 可以按任务关键词、路径前缀、模块名或文件类型生成候选文件列表
2. 选中的候选文件可以被打包成有大小上限的 `CodeContextPack`
3. 任务或规划入口可以读取文件定位结果，为后续变更计划提供输入
4. 定位逻辑默认排除大体积噪声目录和明显无关文件
5. Day05 只提供定位与上下文包，不提前输出具体代码改动方案

---

## 回填记录

- 当前结论：**未开始**
- 回填说明：当前仅完成 Day05 冻结版计划建档，尚未进入实现；开始开发时需严格以今日目标、当日交付和验收点为回填边界。
- 回填证据：
1. 已建立本文档，冻结 Day05 的目标、交付和验收范围
2. 已建立对应测试验证骨架文件，待后续按真实实现回填
3. 后续启动开发后，再以实际代码、页面、脚本和烟测结果替换当前占位说明

---

## 关键产物路径

1. `runtime/orchestrator/app/domain/code_context_pack.py`
2. `runtime/orchestrator/app/services/codebase_locator_service.py`
3. `runtime/orchestrator/app/services/context_builder_service.py`
4. `runtime/orchestrator/app/api/routes/repositories.py`
5. `apps/web/src/features/repositories/components/FileLocatorPanel.tsx`
6. `runtime/orchestrator/scripts/v4b_day05_code_locator_smoke.py`

---

## 上下游衔接

- 前一日：Day04 仓库首页与项目入口整合
- 后一日：Day06 仓库任务映射与变更计划草案
- 对应测试文档：`docs/01-版本冻结计划/V4/02-模块B-文件定位与变更计划/02-测试验证/Day05-文件定位索引与代码上下文包-测试.md`

---

## 顺延与备注

### 顺延项
1. 暂无；如 Day05 启动时发现上游能力未就绪，只在本 Day 文档内记录缺口，不提前并入下一天范围。

### 备注
1. Day05 的重点是“知道该看哪些文件”，不提前进入 Day06 的变更计划草案。

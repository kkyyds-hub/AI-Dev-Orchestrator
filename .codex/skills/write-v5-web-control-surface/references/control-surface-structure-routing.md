# V5 控制面实现 vs 结构治理分流规则

## 1. 目的

把 `write-v5-web-control-surface` 与 `govern-v5-web-structure` 的边界写成可执行的分流规则，避免两个 skill 抢 owner，或者谁都不愿意接“别再写歪”这件事。

## 2. 一句话分工

- `write-v5-web-control-surface`：把一个真实控制面切片做出来。
- `govern-v5-web-structure`：把承接这个切片的前端结构先收口，不让入口页和 feature 边界继续失控。

## 3. 默认判定表

### 用 `write-v5-web-control-surface`

当主问题是：

- 新增按钮、抽屉、面板、表单、视图区
- 补真实接口接入与状态反馈
- 对齐 hooks / api / types / page 的合同
- 给某个既有 feature 增加一个明确的 V5 控制面切片

### 用 `govern-v5-web-structure`

当主问题是：

- 判断代码到底该落在哪
- 聚合页太胖，需要先拆 section / hooks / lib
- 新增 feature 的 owner 边界不清
- 验证路径太脆，需要先补稳定锚点
- 先控制结构风险，再谈继续落功能

## 4. 写控制面时必须立即让位的硬信号

出现任一条，就先停下并交给 `govern-v5-web-structure`：

1. `App.tsx` 或 `ProjectOverviewPage.tsx` 需要继续塞一整块新实现，而不是最小入口挂载。
2. 单个页面为了接这次需求，需要同时新增大段 JSX、复杂状态逻辑、字段转换与请求逻辑。
3. 你发现自己真正纠结的是 section / component / hook / api / lib 的落位，而不是控制面行为本身。
4. 你需要先补 `data-testid`、稳住 smoke / 浏览器证据脚本，才能安全继续。
5. 你准备新增新 feature，但还说不清它和 `projects / roles / strategy / skills / budget / console` 的 owner 边界。

## 5. 两个 skill 的接力顺序

当一个工作包同时含有“功能要落地”和“结构已失控”时：

1. 先由 `govern-v5-web-structure` 给出落位与边界
2. 再由 `write-v5-web-control-surface` 在既定边界内交付功能切片
3. 如仍需验证或回填，再交给 `verify` / `docs` / `review` 等 skill

## 6. 交接时至少说清楚什么

### 从 write 交给 govern

至少说明：

- 当前想做的控制面切片是什么
- 哪个聚合页或 feature 已经承压
- 为什么这已不是单纯的控制面实现问题
- 希望 govern 先收口什么：入口页、落位、拆分、锚点、owner

### 从 govern 交回 write

至少说明：

- 结构落位已经如何收口
- 哪些文件 / section / hooks 可以承接控制面
- 哪些行为和入口路径必须保持不变
- 接下来 write 应落哪个最小控制面切片

## 7. 一句话纪律

**write 有结构守门义务，但没有结构治理 owner 权；govern 有边界裁定权，但不替 write 交付控制面结果。**

# V5 前端结构治理真实作用面

## 1. 目的

把 `govern-v5-web-structure` 绑定到仓库里真实存在、且当前最需要治理的前端入口与聚合面，避免线程一上来就脱离现实发明“前端大改”。

这个参考文件回答四个问题：

1. 当前最需要治理的前端入口文件是谁
2. 哪些目录天然适合作为拆分落点
3. 哪些改动属于低风险结构减债
4. 哪些改动已经越过边界，变成整站翻修

## 2. 当前已确认的主要治理对象

### 顶层入口
- `apps/web/src/app/App.tsx`

当前已确认：
- 它承担了首页聚合、手动执行结果区、任务列表、预算和侧栏总览等多块职责。
- 它容易继续变胖。
- 因此 V5 期间应尽量只让它负责顶层拼装、状态协同和最小事件转发。

### 项目总览聚合页
- `apps/web/src/features/projects/ProjectOverviewPage.tsx`

当前已确认：
- 它已经挂了项目详情、timeline、deliverable、approval、roles、skills、memory、repository、strategy 等多类区块。
- 它是当前最容易出现“一个文件承载过多 feature owner”的位置。
- V5 期间应把它治理成“项目工作区聚合页”，而不是继续让它承担更多具体实现。

## 3. 默认优先的拆分落点

### app 级 section
适合承接：
- 首页大区块
- 只在首页聚合层使用的结果区或统计区

建议目录：
- `apps/web/src/app/sections/`

### feature 级 section / component
适合承接：
- 某个业务域下的大块区块
- 某个 feature 专属的视图区

建议目录：
- `apps/web/src/features/<domain>/sections/`
- `apps/web/src/features/<domain>/components/`

### hooks / types / api
适合承接：
- 请求
- 状态
- 合同映射
- 类型定义

建议目录：
- `apps/web/src/features/<domain>/hooks.ts`
- `apps/web/src/features/<domain>/types.ts`
- `apps/web/src/features/<domain>/api.ts`

### lib
适合承接：
- 纯工具
- 字段格式化
- 通用映射
- 纯函数

建议目录：
- `apps/web/src/lib/`

## 4. 当前默认不应直接纳入的事项

以下事项默认不属于本 skill 的治理范围：

- 全站导航重做
- 新页面体系全面建立
- 全局视觉统一和重新设计
- 路由关系大改
- 跨阶段的 UI 美化工程

## 5. 一句话纪律

V5 期间的前端结构治理，优先处理“已经失控的聚合层”，而不是趁机重建整站。

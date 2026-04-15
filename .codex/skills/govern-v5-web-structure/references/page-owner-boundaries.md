# 页面 owner 边界规则

## 1. 目的

明确 V5 期间前端聚合页、feature 页和共享层的职责边界，避免页面 owner 失控。

## 2. `App.tsx` 的边界

### 允许
- 顶层 hooks 注入
- section 顺序编排
- 最小级别的状态协调
- 最小级别的事件转发

### 不允许
- 长期承载完整 feature 实现
- 继续堆新的大型渲染区
- 混入大量字段转换
- 混入与某个 domain 强绑定的复杂逻辑

## 3. `ProjectOverviewPage.tsx` 的边界

### 允许
- 选中项目状态
- drilldown 上下文
- 项目级区块挂载
- 跨区块导航协调

### 不允许
- 继续承担多个 feature 的具体实现
- 大量新增表格区 / 结果区 / 详情区而不拆分
- 长期承载应归属独立 section / panel 的逻辑

## 4. feature 目录的边界

`features/<domain>/` 应优先承接：
- 该 domain 的主视图区
- 该 domain 的 hooks / api / types
- 该 domain 的 section / component

默认不要把属于某个具体 domain 的实现继续放在顶层入口页。

## 5. shared 层的边界

### `components/`
适合：
- 多处复用的纯视图组件

### `lib/`
适合：
- 纯函数
- 通用格式化
- 映射工具

shared 层不应承接强 domain 逻辑。

## 6. 一句话纪律

入口页负责“挂载和协调”，feature 负责“具体实现”，shared 负责“纯复用”。

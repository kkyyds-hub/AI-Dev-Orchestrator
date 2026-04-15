# V5 前端控制面交付 playbook

## 1. 目标

把一个 V5 前端工作包收敛成**一个真实控制面切片**，并在实现过程中主动防止前端结构继续长歪。

本 playbook 不是“前端随便做点页面”的操作手册，而是：

- 先判 owner
- 再判落位
- 再判合同与状态
- 最后才动代码

## 2. 标准执行顺序

### 第 1 步：判定主 owner

先回答：

1. 这次主目标是新增 / 补完控制能力，还是先治理结构风险
2. 现有 feature owner 是否明确
3. 直接做会不会把 `App.tsx` / `ProjectOverviewPage.tsx` 或某个聚合页继续做胖

如果主问题偏向结构治理，立刻转 `govern-v5-web-structure`，不要硬做。

### 第 2 步：把请求翻译成一个控制面切片

至少写清：

- 对应的 V5 Phase / 工作包
- 本轮只做哪一个页面 / 面板 / 抽屉 / 表单 / 观察区
- 依赖哪些后端字段 / 接口 / 动作
- 本轮明确不做什么

### 第 3 步：锁定安全落位

优先选择现有 feature：

- `projects`
- `roles`
- `strategy`
- `skills`
- `budget`
- `console`
- `console-metrics`
- `run-log`

若现有 feature 明显装不下：

- 先解释为什么装不下
- 再判断 owner 是否清楚
- 如果 owner 仍不清楚，转 `govern-v5-web-structure`

### 第 4 步：完成状态面与合同检查

动手前至少确认：

- loading / empty / error / disabled / submit feedback
- hooks / api / types / page 是否同步
- 文案是否夸大真实状态
- 是否存在后端合同缺口

### 第 5 步：实现控制面切片

实现时遵守：

- 先复用已有 feature 边界
- 不把大段实现继续塞进聚合页
- 不把复杂字段转换散落在大页面
- 不拿静态假数据伪装“已接入”
- 对依赖前提做诚实说明

### 第 6 步：做最小验证

最低建议：

- 能跑就跑 `npm run build`
- 说明手工验证路径
- 说明未验证项与原因
- 说明是否触发了 `govern-v5-web-structure` 的后续接力

### 第 7 步：明确交接路线

至少回答：

- 这次谁是 owner
- 下一棒是谁
- 需要 backend / verify / review / docs / acceptance 哪一类接力
- 如果结构已承压，是否应先交给 `govern-v5-web-structure`

## 3. 交付最小清单

一轮合格的控制面交付，至少应包含：

- 一个明确的控制面切片
- 明确的 feature owner 与落位说明
- 真实状态反馈
- 合同与文案口径自检
- 最小验证或缺证说明
- 下一线程交接建议

## 4. 失败信号

出现下面情况，说明这轮还不合格：

- 做的是静态页，不是真实控制面
- 只有 happy path，没有失败态 / 禁用态
- 把后端未提供的东西假装成已接入
- 明显应该先做结构治理，却仍在硬塞实现
- 没有写清下一线程该接给谁

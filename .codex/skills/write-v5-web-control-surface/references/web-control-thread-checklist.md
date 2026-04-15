# V5 前端控制面线程检查清单

## 开始前

- 已确认当前任务属于 V5 哪个 Phase / 工作包
- 已判断主 owner 仍是 `write-v5-web-control-surface`
- 已检查是否触发 `govern-v5-web-structure` 的前置信号
- 已锁定本轮控制面切片对应的 feature
- 已最小读取相关 page / hooks / types / api / `src/lib/http.ts`

## 动手前

- 已明确用户能看见什么
- 已明确用户能改什么
- 已明确会触发哪个接口 / 动作
- 已明确 loading / empty / error / disabled / submit feedback 怎么表现
- 已明确是否存在后端合同缺口
- 已明确这次不会把聚合页继续写胖；若会，已暂停并转 govern

## 实现时

- 优先扩展现有 feature，而不是乱开新岛
- 页面字段、枚举、文案与后端 / 母本口径一致
- 没有用静态假数据冒充“已接入”
- 没有把复杂合同映射继续散落到聚合页
- 如新增关键交互或关键结果区，已评估是否需要 testid / 结构治理接力

## 交付前

- 已说明本轮改了哪些文件
- 已说明哪些页面 / 状态 / 动作真实可用
- 已说明哪些部分仍依赖后端或未验证
- 已执行最小验证，或明确说明缺证原因
- 已给出下一线程建议 owner：`govern` / `backend` / `verify` / `review` / `docs` / `acceptance`

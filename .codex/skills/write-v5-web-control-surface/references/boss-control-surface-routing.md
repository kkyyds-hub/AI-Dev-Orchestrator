# V5 老板控制面路由图

## 1. 目的

V5 的前端控制面并不是单个页面，而是一组围绕老板控制位展开的入口集合。

这个参考文件回答两个问题：

1. 不同 V5 工作包优先挂到哪个前端 feature
2. 什么时候应该先扩旧页面，什么时候才新增新 feature

## 2. 工作包到 feature 的推荐映射

### role-model-policy-v1

优先挂载：

- `apps/web/src/features/roles/`
- `apps/web/src/features/strategy/`
- 必要时从 `ProjectOverviewPage` 增加入口

适合承载：

- 每角色模型强度
- 角色最大允许 tier
- 升级 / 降级条件
- 是否允许 fallback

### team-assembly-control / team-control-center

优先挂载顺序：

1. 先扩 `projects / roles / strategy`
2. 若结构明显过重，再新增 `apps/web/src/features/agent-teams/`

适合承载：

- 角色启停
- 角色参与策略
- 角色预算
- 最大并发
- 审批阈值

### token-cost-governance / cost dashboard

优先挂载：

- `apps/web/src/features/budget/`
- `apps/web/src/features/console-metrics/`
- `apps/web/src/features/projects/`

适合承载：

- usage 拆账
- 预算压力
- 成本趋势
- top token consumers
- 模型升级触发统计

### memory-governance / checkpoint / thread recovery

优先挂载：

- `apps/web/src/features/projects/`
- `apps/web/src/features/run-log/`
- `apps/web/src/features/console/`

必要时新增：

- `apps/web/src/features/memory-governance/`
- `apps/web/src/features/agents/`

适合承载：

- memory recall 记录
- checkpoint 时间线
- bad context 检测结果
- reset / rehydrate 动作入口

### prompt-registry-builder / prompt-optimization-runtime

优先挂载：

- 先评估 `skills` 是否能承载 prompt 资产入口
- 如果 prompt 资产成为独立 owner 面，再新增 `apps/web/src/features/prompts/`

适合承载：

- 模板列表
- 版本
- diff
- render preview
- 绑定关系

## 3. 一个安全的扩展顺序

如果用户没有明确指定，建议按下面顺序扩前端：

1. 先增强 `ProjectOverviewPage` 等现有老板入口
2. 再增强 `roles / strategy / skills / budget`
3. 只有在控制面变成稳定独立域时，才新增 `agent-teams / prompts / costs / memory-governance`

这样做的原因是：

- 现有页面已经有访问路径和上下文
- 可以减少新入口过多导致的导航碎片化
- 更容易和当前 V1-V4 的控制台风格保持连续

## 4. 线程结束前至少回答

- 这次控制面挂在哪个 feature
- 为什么不放到别的 feature
- 依赖哪些后端字段 / 接口
- 当前是否已可交互
- 下一线程是接 `backend`、`verify`、`review` 还是 `docs`

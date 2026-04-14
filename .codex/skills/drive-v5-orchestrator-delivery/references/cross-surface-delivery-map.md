# V5 跨层交付地图

## 1. 目的

把 `drive-v5-orchestrator-delivery` 绑定到 V5 里最常见的跨层工作包，避免线程一上来就泛化成“全部一起做”。

这个参考文件回答四个问题：

1. 哪些任务最容易跨 backend / web / docs / verify
2. 哪些任务应优先锁定为最小跨层切片
3. 哪些任务其实应该降级给单一 owner skill
4. 总控线程通常该怎样切入

## 2. 最常见的跨层工作包

### Provider / Prompt / Token 基座

最容易跨：

- backend：provider / token / prompt runtime 落地
- web：观察面、配置面、状态展示
- verify：build / API / run / usage 证据
- docs：当前可用程度和未完成项回填

### Memory recall / checkpoint / context 治理

最容易跨：

- backend：worker、context builder、memory / checkpoint 持久化
- web：memory 面板、checkpoint 时间线、恢复入口
- verify：主链 recall / checkpoint 证据
- docs：当前只到切片完成还是已具备阶段推进条件

### Team control / role policy / boss intervention

最容易跨：

- backend：role policy、budget、权限与路由
- web：团队控制面板、策略面板、项目总览入口
- verify：页面、API、提交流程与回显
- review / docs：权限边界、状态口径、遗留项

## 3. 适合降级给单一 owner 的任务

出现以下情况时，不应继续由总控 skill 接管：

- 只改后端一条 service / worker / schema 子链
- 只改前端一个 feature 且合同明确
- 只做 verify
- 只做文档回填
- 只做风险审查

如果不是跨层，就不要滥用总控。

## 4. 推荐切片方式

优先切成：

- 一个 runtime 能力 + 一个前端入口 + 一层 verify
- 一个工作包的“实现 + 验证 + 回填准备”
- 一个明显阻塞推进的跨层缺口闭环

不要切成：

- “把整个 Phase 2 全做了”
- “把所有老板控制面一次补齐”

## 5. 推荐切入顺序

建议顺序：

1. 确认工作包
2. 确认跨层面
3. 锁最小切片
4. 决定先动哪一面
5. 预留 verify 与 handoff

如果还没锁定切片，就不要先开大范围实现。

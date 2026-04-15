# V5 skill-pack 路由矩阵

## 1. 用途

当线程出现“到底该修 skill，还是该直接推进业务 owner”时，用这张矩阵先做路由判断。

## 2. 主问题 → 主 owner

| 当前主问题 | 应优先调用的 skill | `build-v5-skill-pack` 在其中的角色 | 本 skill 不能替代的事 |
| --- | --- | --- | --- |
| 某个 V5 skill 本身不可读、乱码、缺章、prompt 失真 | `build-v5-skill-pack` | 直接 owner | 不能顺势去做业务实现 |
| 要把 V5 前端控制面真实做到 `apps/web` | `write-v5-web-control-surface` | 仅在该 skill 本身失真时先修它 | 不能代做页面 / 交互实现 |
| 要给 `apps/web` 做结构治理、大文件瘦身、稳测试锚点 | `govern-v5-web-structure` | 仅在结构治理 skill 本身失真时先修它 | 不能代做前端结构改造 |
| 要跨 backend / web / docs / verify 推一个工作包 | `drive-v5-orchestrator-delivery` | 仅在总控 skill 路由失真时先修它 | 不能代做跨层推进 |
| 要查运行事实、build、API、页面或回归事实 | `verify-v5-runtime-and-regression` | 仅在 verify skill 本身缺证据规则时先修它 | 不能代做真实验证 |

## 3. 什么时候应该先调用 `build-v5-skill-pack`

优先先调本 skill 的典型信号：

- 目标 skill 的 `SKILL.md`、prompt、references、playbook、template 明显坏掉
- 同一个问题在多个线程里反复被错误路由
- 大家都在问“这个到底该叫哪个 skill”，而根因是 skill 自己没写清
- 目标 skill 只剩能力口号，不能直接指导下一线程开工
- 正在准备继续修别的 skill，但你已经不信任它当前的 owner 描述

## 4. 不该先调用 `build-v5-skill-pack` 的信号

- 当前 owner 已经清楚，主问题就是业务落地
- 当前 owner 已经清楚，主问题就是结构治理
- 当前 owner 已经清楚，主问题就是运行验证
- 当前 owner 已经清楚，主问题就是跨层交付
- skill 文档虽然还能优化，但并没有妨碍本轮业务线程稳定推进

## 5. 一句话判断法

**如果不先修 skill，本轮和下一轮都会继续选错 owner，就先调 `build-v5-skill-pack`；否则直接去正确的业务 skill。**
# V5 前端控制面状态与契约检查清单

## 1. 目的

V5 前端线程最容易出问题的地方，不是“不会写组件”，而是：

- 页面做出来了，但没有真实状态反馈
- 字段和后端对不上
- 明明依赖后端，却拿静态假数据伪装完成
- 文案把“可观察”写成“已完成”
- 明明已经触发结构风险，却还硬往聚合页里堆

本清单用于在动手前和交付前快速自检。

## 2. 先做 owner 与结构自检

在改代码前，至少回答：

- 这次主目标是新增 / 补完控制能力，还是先做结构治理
- 当前 feature owner 是否明确
- 这次改动会不会让 `App.tsx` / `ProjectOverviewPage.tsx` 或某个聚合页继续变胖
- 是否需要先抽 section / hook / api / type / lib 才能安全落地
- 是否需要先补 `data-testid` 才能稳住验证路径

如果上面任何一项的答案指向“主问题已经是结构治理”，先让位给 `govern-v5-web-structure`。

## 3. 合同与数据流检查

如果你要接接口、改字段或新增动作，至少确认：

- 页面依赖的字段是什么
- `hooks.ts`、`types.ts`、`api.ts` 是否都同步
- 请求是否走现有 `src/lib/http.ts` 的 `requestJson`
- 后端是否真的提供了对应字段 / 动作
- 枚举值、状态名、标签名是否与后端一致

### 当前已知要特别小心的点

- `apps/web` 当前已有大量 feature 内部 `hooks / types / api` 分工，别把字段转换散落到页面大组件里。
- `requestJson` 默认期望普通 JSON 响应；若后端响应格式变化，先核对再改，不要想当然。
- 聚合页只适合挂入口，不适合承接越来越多的合同映射与状态分支。

## 4. 状态面检查

每个前端控制面至少确认：

- loading 是否可见
- empty 是否可见
- error 是否可见
- disabled 是否可见
- submit pending 是否可见
- success / failure feedback 是否可见

如果只做 happy path，就不算 V5 控制面完成。

## 5. 文案与口径检查

页面上所有关键词都要诚实：

- “已完成”
- “已接入”
- “推荐”
- “可用”
- “默认”
- “已启用”

这些词必须基于真实后端与真实状态，不要为了页面好看而夸大。

## 6. 新增 feature 检查

如果你想新增 `agent-teams`、`prompts`、`costs` 等 feature，至少确认：

- 现有 feature 真的装不下
- 入口从哪里进入
- 是否需要在 `ProjectOverviewPage` 暴露入口
- 是否会让目录结构变得更碎
- 是否应该先由 `govern-v5-web-structure` 判断落位与 owner

## 7. 验证检查

交付前至少回答：

- 我做了什么最小验证
- 是否运行了 `npm run build`
- 哪些页面路径需要手工检查
- 哪些依赖后端的部分仍未验证
- 本线程有没有触发结构治理信号
- 下一线程该先接 `govern-v5-web-structure`、`backend`、`verify`、`review` 还是 `docs`

如果这些问题答不上来，就不要把状态写成“控制面已完成”。

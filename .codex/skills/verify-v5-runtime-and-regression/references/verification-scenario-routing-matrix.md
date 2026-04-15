# V5 验证场景与接棒路由矩阵

## 1. 目的

把 verify 的高频验证场景、最小验证层级、最小回归动作和兄弟 skill 接棒边界写成一张可直接执行的矩阵，减少线程在“到底先查什么、查到哪算够、失败后交给谁”上的摇摆。

## 2. 场景矩阵

| 场景 | 先读什么 | 最小验证层级 | 最小回归动作 | 强证据优先 | 不要越权做什么 |
| --- | --- | --- | --- | --- | --- |
| 后端启动 / API / worker 最小事实确认 | `README.md`、`main.py`、`health.py`、`workers.py`、`runs.py`、`events.py`、相关 `*_smoke.py` | 启动层 / 接口层 / 脚本层 | 至少复核一条 health、worker、run log 旧链路 | 启动输出、API 响应、run log、脚本输出 | 不替 backend 补实现 |
| 前端 build / 页面入口 / 关键交互最小事实确认 | `package.json`、`App.tsx`、`main.tsx`、相关 feature 页面、`hooks.ts` / `types.ts` / `api.ts` | build 层 / 页面层 | 至少复核 build 或旧入口中的一项 | build 输出、页面访问结果、交互结果 | 不替 web 补页面 |
| 前端结构治理后的联调影响确认 | `App.tsx`、`ProjectOverviewPage.tsx`、本轮拆分文件、相关脚本与入口 | build 层 / 页面层 / 回归层 | 至少复核入口、挂载、旧脚本或旧页面中的一项 | build 输出、入口访问结果、脚本结果 | 不替 structure 决定拆分方案 |
| 测试锚点变更后的最小同步验证 | 受影响 `data-testid`、相关页面、`apps/web/scripts/*.spec.mjs` | 静态层 / 脚本层 / 页面层 | 至少复核一个受影响脚本或页面观察面 | 脚本结果、页面观察结果、锚点核对结果 | 不把仅代码核对写成已验证通过 |

## 3. 兄弟 skill 接棒矩阵

| 上游来源 | verify 接棒时先收什么 | verify 第一刀先查什么 | 如果暴露问题，通常交回谁 |
| --- | --- | --- | --- |
| `write-v5-web-control-surface` | 页面入口、页面交互说明、相关 API 契约、上游自述的“已完成”点 | `npm run build` + 页面入口 / 一条关键交互 | 页面实现缺口回 `write-v5-web-control-surface`；后端合同缺口回 `write-v5-runtime-backend` |
| `govern-v5-web-structure` | 入口页改动、拆分文件、`data-testid` 变更、受影响脚本 | build + 入口挂载 + 一条旧链路 / 脚本 / 锚点同步确认 | 结构 / 锚点治理缺口回 `govern-v5-web-structure` |
| `drive-v5-orchestrator-delivery` | 工作包切片、跨层依赖、上游分层完成说明 | 先压成一个最小闭环事实，再补一条最小回归 | 后端 / 前端 / 文档 / 跨层问题分别回对应 owner；跨层收口问题回 `drive-v5-orchestrator-delivery` |
| `build-v5-skill-pack` | 与本次运行验证有关的 handoff 说明 | 先确认这次要验证的是运行对象，不是 skill 文件本身 | 如果实际问题仍是 skill 包维护，回 `build-v5-skill-pack`；如果已是运行事实，就继续 verify |

## 4. 快速路由规则

- 主问题是“查事实 / 查回归” → 留在 verify
- 主问题是“补页面 / 补接口 / 补 worker” → 回实现 owner
- 主问题是“结构怎么拆 / 锚点怎么治理” → 回 `govern-v5-web-structure`
- 主问题是“跨层怎么编排 / 状态怎么收口” → 回 `drive-v5-orchestrator-delivery`
- 主问题是“skill 包本身写坏了” → 回 `build-v5-skill-pack`

## 5. 使用纪律

- 每轮先选一个主场景，不要四类场景一起铺开。
- 每轮先确认一个上游来源，不要把多个 owner 的产物混成一个模糊结论。
- 每轮至少产出一种强证据和一种最小回归判断。

---
name: verify-v5-runtime-and-regression
description: 将 AI-Dev-Orchestrator V5 母本中的运行验证、构建验证、接口核对、页面验证与最小回归检查收敛成中文事实确认型 skill。用于确认后端是否可启动、worker/API 是否真的通、前端是否真的能 build 和打开，以及当前线程宣称的“已接入 / 已完成 / 已可用”是否有运行证据支撑。
---

# verify-v5-runtime-and-regression

## 使命与 owner

把 V5 线程里的“实现声明”收敛成 **可运行、可观察、可复现、可引用的事实结论**。

这个 skill 的 owner 职责只有一个：

> **负责确认真实运行事实与最小回归事实，不负责替实现线程补实现、不负责替结构治理线程做重构决策、不负责替验收线程做最终裁定。**

它重点负责：

- 后端启动、导入、脚本、worker、API 的最小运行验证
- 前端 build、页面入口、关键交互路径的最小验证
- 前端结构治理后的联调影响确认：入口页、挂载关系、页面可达性、关键脚本与最小回归
- 测试锚点变更后的最小同步验证：`data-testid`、脚本选择器、页面观察面是否仍可对齐
- 证据采集：命令输出、错误信息、日志路径、接口响应、页面状态、脚本结果
- 给兄弟 skill 留下清晰的“可说到哪一步”的事实结论与下一棒建议

它不应该把线程带偏成：

- 明明缺实现，却让 verify 去代替实现
- 明明主问题是结构治理，却让 verify 去决定如何拆页或如何重构
- 明明是在修 skill 包，却把 verify 当成 skill 维护 owner
- 只写推测，不跑任何最小验证
- 看见失败就回避失败，不记录失败事实
- 越权宣布阶段通过或产品能力已验收
- 把“理论上应该可以”写成“已验证通过”

## 强绑定的权威输入

优先级从高到低如下：

1. `C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. `docs/README.md`
3. `C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
4. `C:\Users\Administrator\Desktop\ai-skills草案\verify-v5-runtime-and-regression-skill-草案.md`
5. `references/runtime-verification-surface-map.md`
6. `references/evidence-grading-and-regression-checklist.md`
7. `references/smoke-entrypoints.md`
8. `references/runtime-verification-thread-checklist.md`
9. `references/verification-scenario-routing-matrix.md`
10. 当前线程声称已完成的代码、页面、文档与输出证据

如果这些输入之间冲突，**以 V5 母本 + 仓库真实运行结果为准**，不要让草案或乐观描述覆盖运行事实。

## V5 母本绑定原则

这个 skill 必须明确绑定到 V5 母本，不允许脱离主背景去做无关验证。

默认优先验证以下 V5 关键结论：

### Phase 1 最小闭环相关

- Provider 抽象层是否真的有最小运行链路
- Prompt registry / token accounting 是否真的有可见回执
- Worker 是否默认接入 `project memory recall`
- Role model policy 的最小前后端链路是否真实可用

### Phase 2 相关

- checkpoint / summary / rehydrate 是否至少有最小可跑链路
- memory governance 是否真的有运行痕迹或观察入口

### Phase 3 / 4 相关

- agent session / review-rework 是否真能形成最小线程
- team control center / cost dashboard 是否不只是静态页面

如果用户没有明确说明验证层级，默认先做：

1. 最小可运行验证
2. 最接近当前改动面的最小回归验证
3. 证据可引用的事实总结

## 特别适配的验证场景

### 1. 后端启动 / API / worker 的最小事实确认

适合验证：

- 服务能否启动
- `health` 是否可达
- `workers` / `runs` / `events` 是否有最小观察面
- worker 是否留下 run log、JSONL 或结构化事件证据

最低要求：

- 至少给出启动、接口、脚本或日志中的一种强证据
- 至少说明一条受影响旧链路是否被回归影响

### 2. 前端 build / 页面入口 / 关键交互的最小事实确认

适合验证：

- `npm run build` 是否通过
- 页面入口是否存在且可达
- 与当前改动直接相关的关键交互是否至少走通一条最小路径

最低要求：

- 不把“页面代码存在”写成“页面可用”
- 不把“静态截图可见”写成“关键交互已验证”

### 3. 前端结构治理后的联调影响确认

适合验证：

- `App.tsx` / `ProjectOverviewPage.tsx` 瘦身后入口是否仍可挂载
- 拆分后的 section / panel / hook / api 路径是否仍能支撑原入口
- 结构治理是否把旧页面入口、联调脚本或依赖接口打坏

最低要求：

- 至少确认 build、入口、相关页面或脚本中的一层事实
- 明确记录本轮只确认“影响是否可见”，而不是替治理线程判断“结构方案是否最优”

### 4. 测试锚点变更后的最小同步验证

适合验证：

- `data-testid` 或脚本选择器改名后，页面观察面是否还可用
- `apps/web/scripts/*.spec.mjs` 是否仍能找到目标元素或至少需要同步更新
- 锚点变化是否只影响测试/脚本，还是已经影响页面真实交互

最低要求：

- 明确写出受影响锚点、受影响脚本、受影响页面
- 至少做一层最小同步确认；如果没跑脚本，也要记录为“仅代码核对，未实际运行”

## 技能边界

### 什么时候使用

在下列场景使用本 skill：

- “帮我确认这个功能到底通没通”
- “先查事实，不要先写代码”
- “做一轮最小回归，看有没有把旧链路打坏”
- “验证后端/API/worker 是否可启动、可调用、可落日志”
- “验证前端 build、页面入口、关键交互是否可达”
- “结构治理后先帮我确认联调有没有受影响”
- “测试锚点改了，先确认页面和脚本最小同步情况”
- “我要证据，不要推测”
- “`write-v5-web-control-surface` / `govern-v5-web-structure` / `drive-v5-orchestrator-delivery` 已交出产物，现在需要 verify 接棒确认事实”

### 不要使用

出现下列主任务时，不要继续停留在本 skill：

- 主要目标是补后端实现：转 `write-v5-runtime-backend`
- 主要目标是补前端页面或控制面：转 `write-v5-web-control-surface`
- 主要目标是做前端结构治理、大文件瘦身、锚点规范方案：转 `govern-v5-web-structure`
- 主要目标是整理计划、冻结文档、进度口径：转 `manage-v5-plan-and-freeze-docs`
- 主要目标是跨 backend / web / docs / verify 整链推进：转 `drive-v5-orchestrator-delivery`
- 主要目标是做实现质量、schema 或边界风险审查：转 `review-v5-code-and-risk`
- 主要目标是宣布阶段通过、部分通过或阻塞：转 `accept-v5-milestone-gate`
- 主要目标是修 verify skill 包本身、修乱码、补模板、收口 skill 路由：转 `build-v5-skill-pack`

一句话：**本 skill 管运行事实与回归事实，不接管实现、结构治理、整链编排、skill 包维护或阶段裁定。**

## 正式落盘边界

### 本 skill 的主要输出形式

- 命令级验证结果
- 构建 / 启动 / 脚本输出摘要
- API 请求结果摘要
- 页面访问 / 页面状态摘要
- 日志路径、错误信息、阻塞点说明
- “已验证通过 / 部分通过 / 未验证 / 失败 / 环境阻塞”的分级结论
- 下一棒 owner 与交接建议

### 默认会触达的目录

- `runtime/orchestrator/`
- `runtime/orchestrator/scripts/`
- `apps/web/`
- `apps/web/scripts/`
- 当前线程涉及到的代码文件和说明文件

### 默认不越权的面

- 不负责直接补实现，发现缺口后交回实现 skill
- 不负责修改冻结状态，交给 `manage-v5-plan-and-freeze-docs`
- 不负责最终 pass/block 裁定，交给 `accept-v5-milestone-gate`
- 不负责决定前端拆分策略、目录治理策略或锚点命名策略，交给 `govern-v5-web-structure`
- 不负责维护 skill 包自身，交给 `build-v5-skill-pack`

## 开始入口

每次接手 V5 验证任务时，先按下面顺序读取，且只读最小集合：

1. 打开 V5 母本：`C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. 打开 skill map：`C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
3. 打开本 skill 自带参考：
   - `references/runtime-verification-surface-map.md`
   - `references/evidence-grading-and-regression-checklist.md`
   - `references/smoke-entrypoints.md`
   - `references/runtime-verification-thread-checklist.md`
   - `references/verification-scenario-routing-matrix.md`
4. 打开上游 handoff 材料：来自 `write-v5-web-control-surface`、`govern-v5-web-structure`、`drive-v5-orchestrator-delivery` 或其他线程的交接说明
5. 打开本次被声称已完成的实现说明、页面说明或文档结论
6. 再按验证对象只打开最相关的代码入口

### 最小必读代码入口

- `runtime/orchestrator/README.md`
- `runtime/orchestrator/app/main.py`
- `runtime/orchestrator/app/api/routes/health.py`
- `runtime/orchestrator/app/api/routes/workers.py`
- `runtime/orchestrator/app/api/routes/runs.py`
- `runtime/orchestrator/app/api/routes/events.py`
- `runtime/orchestrator/app/workers/task_worker.py`
- `runtime/orchestrator/app/services/verifier_service.py`
- `runtime/orchestrator/app/services/run_logging_service.py`
- `apps/web/package.json`
- `apps/web/src/app/App.tsx`
- `apps/web/src/app/main.tsx`
- `apps/web/src/features/projects/ProjectOverviewPage.tsx`

### 按验证对象补读

#### 后端启动 / API / worker 类

- `runtime/orchestrator/app/services/*.py`
- `runtime/orchestrator/app/api/routes/*.py`
- `runtime/orchestrator/scripts/*_smoke.py`

#### 前端页面 / 控制面类

- `apps/web/src/features/...`
- 对应 `hooks.ts` / `types.ts` / `api.ts`
- `apps/web/package.json`

#### 前端结构治理 / 测试锚点类

- `apps/web/src/app/App.tsx`
- `apps/web/src/features/projects/ProjectOverviewPage.tsx`
- 本轮被拆分、挪动或重命名的 `sections/*`、`panel/*`、`hooks.ts`、`types.ts`、`api.ts`
- `apps/web/scripts/*.spec.mjs`
- 当前改动涉及的 `data-testid` 所在文件

#### 口径核对 / 上游接棒类

- 当前线程写的交付说明
- 相关 skill 的完成定义与非完成定义
- 上游线程明确声称“已完成 / 已接入 / 已可用”的具体点位

## 如何处理模糊请求

遇到“帮我验证一下”“看看现在到底行不行”“先查事实再说”这类模糊请求时：

1. 先把请求翻译成 **一个验证范围 + 一个验证层级 + 一个上游来源**。
2. 默认优先做最小冒烟，而不是一上来做全量联调。
3. 明确说出你要验证什么、不验证什么。
4. 如果环境本身阻塞，也要把阻塞当成结论的一部分写出来。

例如：

- “验证 provider 接没接上” → 先查执行链、运行记录、usage 字段与日志痕迹
- “验证 memory 是否进主链” → 先查 worker 调用、context/log 输出和最小 run 结果
- “验证团队控制中心可不可用” → 先看页面 build、入口、关键表单、提交回显和依赖接口
- “结构治理后有没有打坏入口页” → 先看 build、入口页挂载、关键脚本与一条旧链路回归
- “锚点改了会不会影响验证脚本” → 先定位受影响 `data-testid`、受影响脚本和最小页面观察面

## 核心工作流

### 1. 先判 owner 是否正确

先回答：

- 当前问题是“查事实”还是“补实现 / 做治理 / 修 skill 包 / 做验收裁定”？
- 当前来源是 `write-v5-web-control-surface`、`govern-v5-web-structure`、`drive-v5-orchestrator-delivery` 还是普通实现线程？
- 如果现在不做 verify，而去做实现或治理，是否会混淆事实结论？

如果主问题已经不是事实确认，立刻切 owner，不要硬留在 verify。

### 2. 把“宣称”翻译成可验证点

例如：

- “provider 已接入” → 是否能真实走到 provider 链路、是否有 usage / log / run 痕迹
- “memory 已接主链” → worker 执行时是否带 recall，日志或结果里是否能看到痕迹
- “checkpoint 已可恢复” → 是否存在创建、读取、恢复的最小链路
- “team control center 已可用” → 页面是否可打开、配置是否可提交、状态是否回显
- “结构治理已完成且不影响联调” → build 是否通过、入口页是否仍可达、原脚本或原锚点是否仍可用
- “测试锚点已同步” → 相关 `data-testid`、脚本选择器和页面观察点是否一致

如果一个宣称拆不成可验证点，就还不能下结论。

### 3. 选择最合适的验证层级

常用层级：

1. 静态层：导入验证、类型检查、脚本可执行性、锚点/路径核对
2. 构建层：前端 build、后端启动
3. 接口层：请求 API，检查状态码与返回结构
4. 页面层：打开页面，走关键交互
5. 联调层：前后端跑通一个最小用例
6. 回归层：确认既有链路没明显被打坏

不要每次都默认做最大层级；优先做最小足够层级。

### 4. 针对场景补最小回归

- 后端场景：至少看一条旧的 health / worker / run log 观察面是否仍可用
- 前端控制面场景：至少看 build 或旧入口是否仍可达
- 结构治理场景：至少看入口、挂载关系、原脚本或原锚点中的一项是否仍可用
- 锚点变更场景：至少看受影响脚本、受影响页面、受影响选择器中的一项是否已经同步

如果完全没做回归，就不要把结论写成“稳定可用”。

### 5. 记录失败事实，不要回避失败

如果失败，要记录：

- 失败发生在哪一步
- 直接报错、异常输出或症状是什么
- 推测根因是什么
- 它阻断了哪一个 V5 结论
- 应该退回哪个实现 / 治理 / 编排 skill 去继续修

失败本身也是高价值事实。

### 6. 明确证据等级

优先使用下列证据，从强到弱：

1. 实际命令输出 / build 输出 / 启动日志
2. API 响应与状态码
3. 运行日志文件与结构化事件
4. 页面打开和交互结果
5. 代码阅读后的合理推断

如果只是代码阅读推断，必须明确写“未实际运行验证”。

### 7. 给出分级结论与下一棒

结论最好分为：

- 已验证通过
- 已部分验证通过
- 已实现但当前环境未验证
- 验证失败
- 环境阻塞无法验证

并且明确下一棒：

- 后端缺口 → `write-v5-runtime-backend`
- 前端控制面缺口 → `write-v5-web-control-surface`
- 前端结构 / 锚点治理缺口 → `govern-v5-web-structure`
- 跨层收口缺口 → `drive-v5-orchestrator-delivery`
- 文档口径回填 → `manage-v5-plan-and-freeze-docs`
- 风险审查 → `review-v5-code-and-risk`
- 阶段裁定 → `accept-v5-milestone-gate`

## 与兄弟 skill 的协作契约

- 本 skill 负责：**运行事实确认、最小回归、证据采集、分级结论、交接建议**
- `write-v5-runtime-backend` 负责：**后端实现修复与落地**
- `write-v5-web-control-surface` 负责：**前端控制面实现修复与落地**
- `govern-v5-web-structure` 负责：**前端结构治理、联调影响控制、测试锚点规范**
- `drive-v5-orchestrator-delivery` 负责：**跨 backend / web / docs / verify 的整链推进**
- `build-v5-skill-pack` 负责：**skill 包体检、修复、补强与路由收口**
- `manage-v5-plan-and-freeze-docs` 负责：**文档冻结、状态回填与交接治理**
- `review-v5-code-and-risk` 负责：**实现质量、边界与风险识别**
- `accept-v5-milestone-gate` 负责：**阶段裁定**

特别纪律：

- 接到 `write-v5-web-control-surface` 的产物时，verify 要盯住页面入口、关键交互、build 与最小回归，而不是继续替它写页面。
- 接到 `govern-v5-web-structure` 的产物时，verify 要盯住入口页、挂载关系、锚点/脚本同步和联调影响，而不是继续替它设计拆分方案。
- 接到 `drive-v5-orchestrator-delivery` 的产物时，verify 要把范围压回最小闭环事实，不要再把线程扩成总控。
- 接到 `build-v5-skill-pack` 的产物时，verify 只验证运行/构建/页面/回归事实，不验证 skill 文件本身是否“写得更好”。

## 推荐输出骨架

优先使用下面骨架汇报本轮验证：

```md
# 本轮运行验证

## 上游接棒
- 来源 skill：
- 来源线程 / 工作包：
- 上游声称已完成：

## 验证归属
- Phase：
- 工作包：
- 验证场景：
- 验证层级：
- 关联母本章节：

## 验证范围
- 本次验证：
- 本次未验证：

## 执行动作
- 命令：
- API：
- 页面：
- 脚本 / 锚点：

## 结果事实
- 成功：
- 失败：
- 阻塞：

## 证据摘要
- 关键输出：
- 日志路径：
- 报错要点：
- 仅代码推断部分：

## 回归判断
- 受影响旧链路：
- 最小回归动作：
- 是否发现回归：

## 结论与交接
- 结论分级：
- 建议下一线程：
- 如需 backend：
- 如需 web：
- 如需 structure：
- 如需 docs / review / accept：
```

## 非完成定义

出现以下情况时，不能算本 skill 工作合格完成：

- 没跑任何验证，就只靠猜测写结论
- 没区分“已验证”与“仅代码阅读推断”
- 发现失败却不记录失败事实
- 不写验证范围，导致结论被误解成全量通过
- 明显应该回退实现 / 治理 / skill 维护 owner，却只给空泛建议
- 接到结构治理或锚点变更产物，却没有覆盖联调影响或最小同步验证
- 直接替 `accept` 做阶段通过裁定

## 红线

1. 不要把“理论可行”写成“已验证通过”。
2. 不要为了看起来顺利而跳过失败事实。
3. 不要在没说明范围的情况下给出笼统“通过”。
4. 不要把验证线程变成实现线程、治理线程或 skill 维护线程。
5. 不要忽略回归影响，只验证新功能。
6. 不要在没有证据的情况下支持冻结或验收结论。

## Done checklist

- 已明确当前验证对应哪个 V5 Phase / 工作包。
- 已明确当前来源于哪个上游 skill 或线程。
- 已引用 V5 母本，而不是脱离母本自由发挥。
- 已明确本次验证范围与未验证范围。
- 已把宣称拆成可验证点，而不是直接复述实现说明。
- 已根据场景矩阵选择最小但足够的验证层级。
- 已记录命令、接口、页面、日志、脚本/锚点等至少一种强证据。
- 已明确区分“已验证”“部分验证”“未验证”“失败”“环境阻塞”。
- 已做至少一层最小回归判断，或明确说明缺证原因。
- 已给出下一线程应接的 owner skill。
- 已让后续新线程可以直接调用本 skill 接手同类验证任务。

## References

- `references/runtime-verification-surface-map.md`
- `references/evidence-grading-and-regression-checklist.md`
- `references/smoke-entrypoints.md`
- `references/runtime-verification-thread-checklist.md`
- `references/verification-scenario-routing-matrix.md`
- `playbooks/runtime-verification-playbook.md`
- `templates/verification-handoff-template.md`

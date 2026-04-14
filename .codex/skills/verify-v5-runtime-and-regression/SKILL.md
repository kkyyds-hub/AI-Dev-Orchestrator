---
name: verify-v5-runtime-and-regression
description: 将 AI-Dev-Orchestrator V5 母本中的运行验证、构建验证、接口核对、页面验证与最小回归检查收敛成中文事实确认型 skill。用于确认后端是否可启动、worker/API 是否真的通、前端是否真的能 build 和打开，以及当前线程宣称的“已接入 / 已完成 / 已可用”是否有运行证据支撑。
---

# verify-v5-runtime-and-regression

## 使命与 owner

把 V5 线程里的“实现声明”收敛成 **可运行、可观察、可复现、可引用的事实结论**。

这个 skill 的 owner 职责只有一个：

> **负责确认真实运行事实，不负责替实现线程补实现、不负责替验收线程做最终裁定。**

它重点负责：

- 后端启动、导入、脚本、worker、API 的最小运行验证
- 前端 build、页面入口、关键交互路径的最小验证
- 回归检查：确认新改动没有把现有关键链路明显打坏
- 证据采集：命令输出、错误信息、日志路径、接口响应、页面状态
- 给兄弟 skill 留下清晰的“可说到哪一步”的事实结论

它不应该把线程带偏成：

- 明明缺实现，却让 verify 去代替实现
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
8. 当前线程声称已完成的代码、页面、文档与输出证据

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

## 技能边界

### 什么时候使用

在下列场景使用本 skill：

- “帮我确认这个功能到底通没通”
- “先查事实，不要先写代码”
- “做一轮最小回归，看有没有把旧链路打坏”
- “验证后端/API/worker 是否可启动、可调用、可落日志”
- “验证前端 build、页面入口、关键交互是否可达”
- “我要证据，不要推测”

### 不要使用

出现下列主任务时，不要继续停留在本 skill：

- 主要目标是补后端实现：转 `write-v5-runtime-backend`
- 主要目标是补前端页面或控制面：转 `write-v5-web-control-surface`
- 主要目标是整理计划、冻结文档、进度口径：转 `manage-v5-plan-and-freeze-docs`
- 主要目标是跨 backend / web / docs / verify 整链推进：转 `drive-v5-orchestrator-delivery`
- 主要目标是做实现质量、schema 或边界风险审查：转 `review-v5-code-and-risk`
- 主要目标是宣布阶段通过、部分通过或阻塞：转 `accept-v5-milestone-gate`

## 正式落盘边界

### 本 skill 的主要输出形式

- 命令级验证结果
- 构建 / 启动 / 脚本输出摘要
- API 请求结果摘要
- 页面访问 / 页面状态摘要
- 日志路径、错误信息、阻塞点说明
- “已验证通过 / 部分通过 / 未验证 / 失败 / 环境阻塞”的分级结论

### 默认会触达的目录

- `runtime/orchestrator/`
- `runtime/orchestrator/scripts/`
- `apps/web/`
- 当前线程涉及到的代码文件和说明文件

### 默认不越权的面

- 不负责直接补实现，发现缺口后交回实现 skill
- 不负责修改冻结状态，交给 `manage-v5-plan-and-freeze-docs`
- 不负责最终 pass/block 裁定，交给 `accept-v5-milestone-gate`

## 开始入口

每次接手 V5 验证任务时，先按下面顺序读取，且只读最小集合：

1. 打开 V5 母本：`C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. 打开 skill map：`C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
3. 打开本 skill 自带参考：
   - `references/runtime-verification-surface-map.md`
   - `references/evidence-grading-and-regression-checklist.md`
   - `references/smoke-entrypoints.md`
4. 打开本次被声称已完成的实现说明、页面说明或文档结论
5. 再按验证对象只打开最相关的代码入口

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

### 按验证对象补读

#### 后端启动 / API / worker 类

- `runtime/orchestrator/app/services/*.py`
- `runtime/orchestrator/app/api/routes/*.py`
- `runtime/orchestrator/scripts/*_smoke.py`

#### 前端页面 / 控制面类

- `apps/web/src/features/...`
- 对应 `hooks.ts` / `types.ts` / `api.ts`

#### 口径核对类

- 当前线程写的交付说明
- 相关 skill 的完成定义与非完成定义

## 如何处理模糊请求

遇到“帮我验证一下”“看看现在到底行不行”“先查事实再说”这类模糊请求时：

1. 先把请求翻译成 **一个验证范围 + 一个验证层级**。
2. 默认优先做最小冒烟，而不是一上来做全量联调。
3. 明确说出你要验证什么、不验证什么。
4. 如果环境本身阻塞，也要把阻塞当成结论的一部分写出来。

例如：

- “验证 provider 接没接上” → 先查执行链、运行记录、usage 字段与日志痕迹
- “验证 memory 是否进主链” → 先查 worker 调用、context/log 输出和最小 run 结果
- “验证团队控制中心可不可用” → 先看页面 build、入口、关键表单、提交回显和依赖接口

## 核心工作流

### 1. 先界定验证范围

每次验证都要先说清：

- 这次验证的是后端、前端、联调还是回归
- 是验证新能力，还是确认旧能力没被打坏
- 是冒烟级、功能级，还是验收前检查

范围不清，结论就会特别虚。

### 2. 把“宣称”翻译成可验证点

例如：

- “provider 已接入” → 是否能真实走到 provider 链路、是否有 usage / log / run 痕迹
- “memory 已接主链” → worker 执行时是否带 recall，日志或结果里是否能看到痕迹
- “checkpoint 已可恢复” → 是否存在创建、读取、恢复的最小链路
- “team control center 已可用” → 页面是否可打开、配置是否可提交、状态是否回显

如果一个宣称拆不成可验证点，就还不能下结论。

### 3. 选择最合适的验证层级

常用层级：

1. 静态层：导入验证、类型检查、脚本可执行性
2. 构建层：前端 build、后端启动
3. 接口层：请求 API，检查状态码与返回结构
4. 页面层：打开页面，走关键交互
5. 联调层：前后端跑通一个最小用例
6. 回归层：确认既有链路没明显被打坏

不要每次都默认做最大层级；优先做最小足够层级。

### 4. 记录失败事实，不要回避失败

如果失败，要记录：

- 失败发生在哪一步
- 直接报错、异常输出或症状是什么
- 推测根因是什么
- 它阻断了哪一个 V5 结论
- 应该退回哪个实现 skill 去继续修

失败本身也是高价值事实。

### 5. 明确证据等级

优先使用下列证据，从强到弱：

1. 实际命令输出 / build 输出 / 启动日志
2. API 响应与状态码
3. 运行日志文件与结构化事件
4. 页面打开和交互结果
5. 代码阅读后的合理推断

如果只是代码阅读推断，必须明确写“未实际运行验证”。

### 6. 做最小回归，而不只是验证新功能

至少问自己：

- 这次改动有没有影响原来的 worker/API/页面入口
- 原有 smoke 脚本还能不能跑
- 原有 build 命令还能不能过
- 旧页面是否因为新字段变化而报错

如果没有做任何回归，就不要把结论写成“稳定可用”。

### 7. 给出分级结论

结论最好分为：

- 已验证通过
- 已部分验证通过
- 已实现但当前环境未验证
- 验证失败
- 环境阻塞无法验证

不要只给“通过 / 不通过”这种过粗的判断。

### 8. 明确交接路线

线程结束时必须明确下一棒是谁：

- 如果暴露后端实现缺口 → `write-v5-runtime-backend`
- 如果暴露前端控制面缺口 → `write-v5-web-control-surface`
- 如果暴露跨层错位 → `drive-v5-orchestrator-delivery`
- 如果需要把状态写回冻结文档 → `manage-v5-plan-and-freeze-docs`
- 如果需要做风险审查 → `review-v5-code-and-risk`
- 如果已经具备阶段裁定证据 → `accept-v5-milestone-gate`

## 与兄弟 skill 的协作契约

- 本 skill 负责：**运行事实确认、最小回归、证据采集、分级结论、交接建议**
- `write-v5-runtime-backend` 负责：**后端实现修复与落地**
- `write-v5-web-control-surface` 负责：**前端控制面实现修复与落地**
- `manage-v5-plan-and-freeze-docs` 负责：**文档冻结、状态回填与交接治理**
- `drive-v5-orchestrator-delivery` 负责：**跨 backend / web / docs / verify 整链推进**
- `review-v5-code-and-risk` 负责：**实现质量、边界与风险识别**
- `accept-v5-milestone-gate` 负责：**阶段裁定**

不要替兄弟 skill 越权补写“实现已完成”；本 skill 只对事实结论负责。

## 推荐输出骨架

优先使用下面骨架汇报本轮验证：

```md
# 本轮运行验证

## 验证归属
- Phase：
- 工作包：
- 验证层级：
- 关联母本章节：

## 验证范围
- 本次验证：
- 本次未验证：

## 执行动作
- 命令：
- API：
- 页面：
- 脚本：

## 结果事实
- 成功：
- 失败：
- 阻塞：

## 证据摘要
- 关键输出：
- 日志路径：
- 报错要点：

## 回归判断
- 受影响旧链路：
- 是否发现回归：

## 结论与交接
- 结论分级：
- 建议下一线程：
- 如需 backend：
- 如需 web：
- 如需 docs / accept：
```

## 非完成定义

出现以下情况时，不能算本 skill 工作合格完成：

- 没跑任何验证，就只靠猜测写结论
- 没区分“已验证”与“仅代码阅读推断”
- 发现失败却不记录失败事实
- 不写验证范围，导致结论被误解成全量通过
- 明显应该回退实现 skill，却只给空泛建议
- 直接替 `accept` 做阶段通过裁定

## 红线

1. 不要把“理论可行”写成“已验证通过”。
2. 不要为了看起来顺利而跳过失败事实。
3. 不要在没说明范围的情况下给出笼统“通过”。
4. 不要把验证线程变成实现线程。
5. 不要忽略回归影响，只验证新功能。
6. 不要在没有证据的情况下支持冻结或验收结论。

## Done checklist

- 已明确当前验证对应哪个 V5 Phase / 工作包。
- 已引用 V5 母本，而不是脱离母本自由发挥。
- 已明确本次验证范围与未验证范围。
- 已把宣称拆成可验证点，而不是直接复述实现说明。
- 已选择最小但足够的验证层级。
- 已记录命令、接口、页面、日志等至少一种强证据。
- 已明确区分“已验证”“部分验证”“未验证”“失败”“环境阻塞”。
- 已做至少一层最小回归判断，或明确说明缺证原因。
- 已给出下一线程应接的 owner skill。
- 已让后续新线程可以直接调用本 skill 接手同类验证任务。

## References

- `references/runtime-verification-surface-map.md`
- `references/evidence-grading-and-regression-checklist.md`
- `references/smoke-entrypoints.md`

- `playbooks/runtime-verification-playbook.md`
- `references/runtime-verification-thread-checklist.md`
- `templates/verification-handoff-template.md`
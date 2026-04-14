---
name: accept-v5-milestone-gate
description: 将 AI-Dev-Orchestrator V5 母本中的阶段裁定、工作包裁定、Pass/Partial/Blocked 分级与遗留项收口规则收敛成中文验收型 skill。用于在实现、审查、验证之后，对某个工作包、切片或阶段给出正式裁定，并明确已完成边界、未完成边界、阻塞原因与下一线程接力方向。
---

# accept-v5-milestone-gate

## 使命与 owner

把 V5 线程里的“现在差不多可以宣布完成了吧”收敛成 **诚实、分级、可追责、可继承** 的正式裁定。

这个 skill 的 owner 职责只有一个：

> **负责判断当前最多能宣布到哪一步，而不是继续实现、继续验证，或把 partial 硬写成 pass。**

它重点负责：

- 对工作包、单轮切片或阶段给出 `Pass / Partial / Blocked` 裁定
- 明确已完成边界、未完成边界、阻塞原因与遗留项
- 约束“最多能说到哪里”，避免夸大结论
- 让后续线程清楚知道：先补什么、由谁补、补完后才能进入下一阶段

它不应该把线程带偏成：

- 继续补实现或补验证
- 没有足够材料就直接乐观放行
- 把“核心切片完成”写成“整阶段完成”
- 不写遗留项，只给一个空泛 pass
- 越过 review / verify 直接拍板

## 强绑定的权威输入

优先级从高到低如下：

1. `C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. `docs/README.md`
3. `C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
4. `C:\Users\Administrator\Desktop\ai-skills草案\accept-v5-milestone-gate-skill-草案.md`
5. `references/milestone-gate-map.md`
6. `references/pass-partial-blocked-rules.md`
7. `references/evidence-requirements-and-rollup-checklist.md`
8. 当前工作包的计划文档、实现说明、review 结论、verify 结论与文档回填

如果这些输入之间冲突，**以 V5 母本 + 已验证事实 + 已审查风险结论为准**，不要让乐观叙述覆盖现实。

## V5 母本绑定原则

这个 skill 必须明确绑定到 V5 母本，不允许脱离 V5 的 Phase / 工作包 / 验收口径做泛化验收。

默认优先对照母本里的三类验收口径：

### 产品能力验收

关注：

- 老板是否真的能配置团队与控制角色
- 系统是否真的具备最小真实 provider / memory / prompt / token / multi-agent 能力
- 控制面是否只是展示，还是已经形成真实操作与回显闭环

### 工程验收

关注：

- 数据结构是否有迁移方案
- 关键路径是否有 smoke / integration tests
- Provider 是否有 mock 层或回退逻辑
- prompt render / memory recall / token accounting 是否可回放
- 关键页面是否 build 通过

### 成本验收

关注：

- token / cost 是否只是口号，还是有真实口径
- 成本优化是否有明确量化依据或至少具备追踪基础

如果用户没有指定验收对象，默认先收敛为：

1. 一个工作包或单轮切片
2. 不默认上升为整个 Phase
3. 只有当材料足够闭合时，才允许提升到阶段级裁定

## 技能边界

### 什么时候使用

在下列场景使用本 skill：

- 某个工作包已经过一轮实现、审查、验证，想做正式裁定
- 你想知道当前能否把状态从“进行中”改成“通过 / 部分通过 / 阻塞”
- 你需要形成明确的 pass / partial / blocked 结论给后续线程继承
- 你要阻止“做了一点就宣布阶段完成”的冲动

### 不要过早使用

出现下列情况时，不要继续停留在本 skill：

- 只有规划，没有实现
- 只有实现，没有最小验证
- review 还没做，重大风险未澄清
- 范围都没闭合，根本不知道在验什么
- 当前最需要的是继续实现：转 `write-v5-runtime-backend` / `write-v5-web-control-surface`
- 当前最需要的是继续验证：转 `verify-v5-runtime-and-regression`
- 当前最需要的是先做风险把关：转 `review-v5-code-and-risk`

## 正式落盘边界

### 本 skill 的主要输出形式

- `Pass / Partial / Blocked` 结论
- 已完成范围与不能确认完成范围
- 阻塞原因与遗留项
- 下一阶段 / 下一线程前置条件
- 推荐接力的 owner skill

### 默认会触达的材料

- 计划与冻结文档
- 实现说明与改动摘要
- review 结论
- verify 结论
- 必要的代码与页面现实核对

### 默认不越权的面

- 不代替实现 skill 修功能
- 不代替 verify 补运行事实
- 不代替 review 做结构风险识别

## 开始入口

每次接手 V5 验收任务时，先按下面顺序读取，且只读最小集合：

1. 打开 V5 母本：`C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. 打开 skill map：`C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
3. 打开本 skill 自带参考：
   - `references/milestone-gate-map.md`
   - `references/pass-partial-blocked-rules.md`
   - `references/evidence-requirements-and-rollup-checklist.md`
4. 打开当前工作包的计划 / 冻结 / 回填文档
5. 打开最近一轮 `review-v5-code-and-risk` 结论
6. 打开最近一轮 `verify-v5-runtime-and-regression` 结论
7. 只在必要时抽查最相关的代码或页面，确认结论没有脱离现实

### 最小必读材料

- 当前工作包或阶段的完成定义
- 最近一轮实现说明
- 最近一轮 review 结论
- 最近一轮 verify 结论
- 若已有 freeze 回填，则同步查看其状态口径

### 按验收对象补读

#### 工作包 / 切片级验收

- 该切片直接改动的代码
- 相关 verify 证据
- 相关 review 风险分级

#### 阶段级验收

- 该 Phase 下多个工作包的回填
- 相关 build / smoke / page / API 证据汇总
- 剩余缺口与前置条件清单

## 如何处理模糊请求

遇到“现在能不能算完成”“能不能过这阶段”“给个正式结论”这类模糊请求时：

1. 先把请求翻译成 **一个验收对象 + 一个裁定层级**。
2. 默认先验收工作包或切片，不默认直接验收整个 Phase。
3. 明确说出这次结论会影响哪个状态。
4. 如果材料不足，也要把“当前不能裁定 pass”当成结论的一部分写出来。

例如：

- “Phase 1 现在能过吗” → 先拆成 Provider / Prompt / Token / Role policy / Memory recall 各自是否闭合
- “这轮 runtime 改动能不能算完成” → 先按单轮后端切片做裁定，不直接上升到整个模块
- “这个团队控制中心能不能宣发” → 先看前端控制面、后端合同、verify 证据与遗留风险是否闭合

## 核心工作流

### 1. 先核对验收对象

先明确：

- 这次验收针对的是工作包、单轮切片，还是整个 Phase
- 结论会影响哪个状态口径
- 这次结论是否会被后续线程当作阶段基线

验收对象不清楚，结论就容易越界。

### 2. 拉齐三类材料

尽量同时看三类材料：

1. 计划与完成口径
2. 实现与风险审查材料
3. 验证与运行证据

少任意一类，结论都容易失真。

### 3. 判断“最多能说到哪里”

验收不是追求积极，而是追求准确。

如果当前只能说：

- “这个工作包的核心后端切片完成”

就不要写成：

- “整个 Phase 已完成”

这是本 skill 最重要的纪律之一。

### 4. 判断证据是否足够支撑结论

至少检查：

- 是否真的有实现
- 是否有 review 结论
- 是否有 verify 证据
- 文档口径是否与代码和验证一致
- 高风险是否已消化、隔离或诚实保留

没有这些条件，就不要轻易给 `Pass`。

### 5. 用 Pass / Partial / Blocked 分级

#### Pass

适用于：

- 范围明确且闭合
- 关键实现完成
- 最小必要验证通过
- 重大风险已消化或可接受
- 文档、实现、verify 口径一致

#### Partial

适用于：

- 核心部分完成，但仍有明显残留缺口
- 当前可算“切片完成”，不能算“整个阶段完成”
- 可继续推进，但必须保留未完成项与前置条件

#### Blocked

适用于：

- 关键实现未完成
- 缺最小验证
- 高风险未解决
- 文档与事实不一致，无法给可靠结论

### 6. 把未完成项写成正式遗留项

优秀的验收结果必须保留：

- 尚未完成内容
- 风险内容
- 进入下一阶段前必须补的前置条件
- 推荐先接手的 owner skill

没有遗留项的验收结论，通常不够可信。

### 7. 防止 partial 被误写成 pass

典型必须给 `Partial` 的情况：

- 后端完成了，但前端控制面还没做
- 前端做了，但联调或运行证据不够
- 接口存在，但 worker 主链还没全接通
- 文档写成阶段可用，但实际只有最小切片能跑

### 8. 明确交接路线

线程结束时必须明确下一棒是谁：

- 若完成定义不清 → `manage-v5-plan-and-freeze-docs`
- 若实现不够 → `write-v5-runtime-backend` / `write-v5-web-control-surface`
- 若缺验证 → `verify-v5-runtime-and-regression`
- 若高风险没澄清 → `review-v5-code-and-risk`
- 若本质是跨层整链问题 → `drive-v5-orchestrator-delivery`

## 与兄弟 skill 的协作契约

- 本 skill 负责：**阶段裁定、工作包裁定、分级结论、遗留项收口、下一棒指定**
- `manage-v5-plan-and-freeze-docs` 负责：**完成口径、冻结文档、状态回填与交接治理**
- `write-v5-runtime-backend` 负责：**后端实现补齐**
- `write-v5-web-control-surface` 负责：**前端控制面补齐**
- `verify-v5-runtime-and-regression` 负责：**运行事实、构建/API/页面验证与回归证据**
- `review-v5-code-and-risk` 负责：**结构、兼容性、主链、合同与风险把关**
- `drive-v5-orchestrator-delivery` 负责：**跨 backend / web / docs / verify 的整链收口**

不要替兄弟 skill 越权补实现或补证据；本 skill 只对裁定负责。

## 推荐输出骨架

优先使用下面骨架汇报本轮裁定：

```md
# 本轮里程碑裁定

## 验收归属
- Phase：
- 工作包：
- 验收对象：
- 关联母本章节：

## 依据材料
- 计划 / 完成定义：
- 实现说明：
- review 结论：
- verify 结论：

## 裁定
- 结论：Pass / Partial / Blocked
- 能确认完成的范围：
- 不能确认完成的范围：

## 遗留项
- 风险：
- 必补项：
- 进入下一阶段前前置条件：

## 交接路线
- 下一线程建议 skill：
- 第二顺位：
- 如需先补 verify：
- 如需先补 review：
```

## 非完成定义

出现以下情况时，不能算本 skill 工作合格完成：

- 验收对象不明确，就直接给笼统结论
- 没有 review / verify 仍然硬给 pass
- 明明是 partial，却写成 pass
- 不写遗留项和前置条件
- 把单轮切片完成夸大成整个 Phase 完成
- 验收结论让后续线程不知道该先补什么

## 红线

1. 不要跳过 review / verify 就做乐观验收。
2. 不要把 `Partial` 硬写成 `Pass`。
3. 不要不给遗留项。
4. 不要在结论里夸大当前可用程度。
5. 不要把切片完成误写成阶段完成。
6. 不要让后续线程不知道先补什么、由谁补。

## Done checklist

- 已明确当前验收对应哪个 V5 Phase / 工作包 / 切片。
- 已引用 V5 母本，而不是脱离母本自由发挥。
- 已同时查看完成口径、实现材料、review 结论、verify 证据。
- 已明确这次裁定最多能说到哪一步。
- 已使用 `Pass / Partial / Blocked` 做分级，而不是模糊表达。
- 已清楚写出能确认完成与不能确认完成的范围。
- 已把遗留项、风险、前置条件写成正式交接物。
- 已明确下一线程应接的 owner skill。
- 已避免把局部完成夸大为整阶段完成。
- 已让后续新线程可以直接调用本 skill 接手同类里程碑裁定任务。

## References

- `references/milestone-gate-map.md`
- `references/pass-partial-blocked-rules.md`
- `references/evidence-requirements-and-rollup-checklist.md`

- `playbooks/milestone-gate-playbook.md`
- `references/milestone-gate-thread-checklist.md`
- `templates/milestone-gate-decision-template.md`
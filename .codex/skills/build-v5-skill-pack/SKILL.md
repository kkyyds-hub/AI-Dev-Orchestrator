---
name: build-v5-skill-pack
description: 将 AI-Dev-Orchestrator V5 的 skill 草案新增、重写、补细节、拆分、转正式与 references/agents 配套建设收敛成中文技能体系维护型 skill。用于当任务目标是继续完善 V5 skill pack 本身，而不是直接推进某个业务工作包时，统一 owner 边界、协作链、风格、正式目录结构和可直接调用的 SKILL.md 质量。
---

# build-v5-skill-pack

## 使命与 owner

把 V5 的 skill 体系本身，从“桌面草案集合”持续推进成 **正式可用、边界清楚、风格统一、可直接接力** 的 `.codex/skills/` 技能库。

这个 skill 的 owner 职责只有一个：

> **负责维护 V5 skill pack 本身，而不是直接替业务线程做 backend / web / verify / accept 交付。**

它重点负责：

- 新增 V5 workflow skill 草案
- 修订已有草案的 owner、边界、工作流与交接规则
- 把抽象能力包改写成真正的 workflow owner 型 skill
- 把桌面草案转成正式 `SKILL.md + agents/openai.yaml + references/*`
- 统一整个 V5 skill pack 的写法、结构、协作链和质量门槛

它不应该把线程带偏成：

- 继续抽象讨论架构，不落正式 skill 文件
- 用 skill 维护线程替代真实业务交付线程
- 把能力主题词直接当成 skill 名，而不做 owner 化
- 把 skill 写回模块设计文档风格
- 一次性生成大量空 skill 骨架

## 强绑定的权威输入

优先级从高到低如下：

1. `C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. `C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
3. `C:\Users\Administrator\Desktop\ai-skills草案\build-v5-skill-pack-skill-草案.md`
4. 当前已正式落地的 `.codex/skills/*/SKILL.md`
5. `C:\Users\Administrator\\.codex\\skills\\.system\\skill-creator\\SKILL.md`
6. `references/skill-pack-governance-rules.md`
7. `references/workflow-owner-shaping-checklist.md`
8. `references/formalization-packaging-rules.md`

如果这些输入之间冲突，**以 V5 母本 + 当前已正式落地 skills 的稳定风格 + 仓库实际目录结构为准**，不要让草案覆盖已经稳定的正式技能库事实。

## V5 母本绑定原则

这个 skill 必须明确绑定到 V5 母本，不允许脱离 V5 主背景去“泛化写 skill 教程”。

默认优先维护下列内容：

- V5 workflow owner 型 skills
- V5 skill 之间的协作链
- 与 V5 Phase / 工作包 / 验证 / 验收口径直接相关的 references

默认不优先：

- 与 V5 无关的通用技能
- 只谈抽象能力分类、不形成实际 owner 边界的内容
- 不准备正式落到 `.codex/skills/` 的临时脑暴材料

## 技能边界

### 什么时候使用

在下列场景使用本 skill：

- “继续写 V5 skill 草案”
- “把这份草案改成更像 demo 的正式 skill”
- “把某个能力主题改写成 workflow owner”
- “整理 V5 skills 之间的协作链和边界”
- “把桌面草案转成正式 `SKILL.md`”
- “补 references / playbook / handoff 模板，让 skill 可直接调用”

### 不要使用

出现下列主任务时，不要继续停留在本 skill：

- 主要目标是推进某个真实 backend 工作包：转对应业务 skill
- 主要目标是推进某个真实 web 控制面：转对应业务 skill
- 主要目标是查运行事实、做回归、做验收：转 verify / review / accept
- 主要目标是做文档冻结或状态回填：转 `manage-v5-plan-and-freeze-docs`

一句话：**本 skill 管技能库，不管业务工作包本身。**

## 正式落盘边界

### 本 skill 的主要输出目录

- `.codex/skills/<skill-name>/SKILL.md`
- `.codex/skills/<skill-name>/agents/openai.yaml`
- `.codex/skills/<skill-name>/references/*`

### 默认可改动的面

- 新增 skill 目录
- 修订已有 skill 的 `SKILL.md`
- 修订已有 skill 的 `agents/openai.yaml`
- 增减最小必要的 `references/`

### 默认不建议做的事

- 一次性批量制造大量空 skill 目录
- 为每个 skill 都塞一堆不必要的 references
- 让正式 skill 和桌面草案同时维持两套不同口径

## 开始入口

每次接手 V5 技能体系维护任务时，先按下面顺序读取，且只读最小集合：

1. 打开 V5 母本：`C:\Users\Administrator\Desktop\AI-Dev-Orchestrator-V5-Plan.md`
2. 打开 suite map：`C:\Users\Administrator\Desktop\ai-skills草案\00-V5-skill-suite-map.md`
3. 打开本 skill 自带参考：
   - `references/skill-pack-governance-rules.md`
   - `references/workflow-owner-shaping-checklist.md`
   - `references/formalization-packaging-rules.md`
4. 打开 `skill-creator`：`C:\Users\Administrator\\.codex\\skills\\.system\\skill-creator\\SKILL.md`
5. 打开 1~2 个当前已正式落地的 V5 skill，保持风格连续
6. 再打开本次要新增 / 修订的草案

### 最小必读正式 skills

- `.codex/skills/manage-v5-plan-and-freeze-docs/SKILL.md`
- `.codex/skills/write-v5-runtime-backend/SKILL.md`
- `.codex/skills/drive-v5-orchestrator-delivery/SKILL.md`

### 按维护类型补读

#### 新增 skill

- 对应草案
- suite map 中该 skill 的定位
- 相关兄弟 skills 的边界说明

#### 修已有 skill

- 当前正式 `SKILL.md`
- 对应 references
- 与其最容易冲突的兄弟 skill

#### 转正式

- 桌面草案
- 目标正式目录
- 当前已落地 skill 的结构范式

## 如何处理模糊请求

遇到“继续补 V5 skills”“把这份草案改得更像 demo”“把这类能力整理成技能库”这类模糊请求时：

1. 先判断这次是**新增 skill**、**重写 skill**、**补细节**还是**转正式**。
2. 默认一次只处理一个 skill，不贪多。
3. 明确说出本次维护对象、目标状态和正式落点。
4. 如果任务其实是业务交付，就主动转给相应业务 skill，不要留在 skill-pack 线程里。

## 核心工作流

### 1. 先判断是“缺 skill”还是“现有 skill 写得不对”

常见情况有两种：

- 现有 skill 方向对，但写得太抽象、太短、太不接地气
- 当前确实缺一个新的 owner skill，需要正式新增

不要一上来就默认新增。

### 2. 先检查是不是误把“能力主题”当成 skill

每次写 skill 前先问：

- 这个名字描述的是“能力主题”，还是“workflow owner”
- 如果只是能力主题，是否应该收敛进某个已有 skill 的工作包映射
- 这个 skill 是否真的有独立 owner 边界和交接价值

如果没有 owner 边界，就不要硬立 skill。

### 3. 参考正式 skill，而不是退回方案文风

至少要对照这些骨架要素：

- front matter
- 使命与 owner
- 强绑定输入
- V5 母本绑定原则
- 技能边界
- 开始入口
- 核心工作流
- 兄弟 skill 协作契约
- done checklist
- references

V5 skill 不需要逐字复用，但结构要统一、可执行。

### 4. 把草案写到可直接调用级别

一个合格的正式 skill 至少要写清：

- 什么时候用
- 什么时候不用
- 必读文件
- 正式落盘边界
- 标准工作流
- 交接规则
- 什么算完成

否则新线程还是接不起来。

### 5. 统一整个 skill pack 的风格

建议持续统一：

- 全部中文详细版
- 全部强绑定 V5 母本
- 全部采用 owner / boundary / workflow 结构
- 全部明确兄弟 skill 交接规则
- 全部避免空洞能力宣传语

### 6. 只补最小必要 references

references 应该服务于可执行性，而不是为了看起来完整。

优先补：

- 能帮助判断边界的规则
- 能帮助路由到兄弟 skill 的规则
- 能帮助统一输出骨架与交接物的规则

不要为每个 skill 机械地塞一堆无关参考文件。

### 7. 转正式时同时补齐 packaging

正式 skill 至少包含：

- `SKILL.md`
- `agents/openai.yaml`
- 按需的 `references/`

如果只有 `SKILL.md` 没有 agent metadata，或 references 与正文完全脱节，正式度就不够完整。

## 与兄弟 skill 的协作契约

- 本 skill 负责：**skill 体系维护、草案 owner 化、正式化落地、风格统一、协作链修正**
- `manage-v5-plan-and-freeze-docs` 负责：**V5 文档治理**
- `write-v5-runtime-backend` 负责：**后端交付**
- `write-v5-web-control-surface` 负责：**前端控制面交付**
- `drive-v5-orchestrator-delivery` 负责：**跨层总控交付**
- `verify-v5-runtime-and-regression` 负责：**事实验证**
- `review-v5-code-and-risk` 负责：**风险审查**
- `accept-v5-milestone-gate` 负责：**里程碑裁定**

本 skill 不替代这些业务 owner，它只负责让这些 owner skills 本身更清楚、更可用、更能接力。

## 推荐输出骨架

优先使用下面骨架汇报本轮 skill 维护：

```md
# 本次 V5 skill 维护

## 维护对象
- skill 名称：
- 维护类型：新增 / 重写 / 补细节 / 转正式
- 对应草案：

## 本轮目标
- 要解决的问题：
- 参考依据：

## 结果
- 正式产物路径：
- 新增章节：
- 边界调整：
- 新增 references：

## 协作影响
- 与哪些兄弟 skill 关系更清楚了：
- 仍待补的缺口：

## 下一步建议
- 下一线程建议：
```

## 非完成定义

出现以下情况时，不能算本 skill 工作合格完成：

- 只讨论 skill 结构，不落正式文件
- 还是把 skill 写成模块设计说明
- 只有名字，没有 owner 边界和交接规则
- 与已有 skills 职责重叠严重却不澄清
- 一次性摊开太多 skill，导致没有一个真正写完

## 红线

1. 不要把 skill 维护线程写回抽象架构文档。
2. 不要把能力主题直接当成 workflow owner。
3. 不要脱离 V5 母本与 suite map 乱扩技能库。
4. 不要批量制造空 skill 骨架。
5. 不要让正式 skill 与草案长期保持两套不同口径。
6. 不要让 skill 之间职责重叠到无法协作。

## Done checklist

- 已明确当前维护对象是哪个 V5 skill。
- 已明确这次是新增 / 重写 / 补细节 / 转正式中的哪一种。
- 已引用 V5 母本、suite map 与当前正式 skills，而不是脱离体系自由发挥。
- 已确认目标对象是 workflow owner，而不是空洞能力主题。
- 已写清 owner、边界、开始入口、工作流、交接规则、done checklist。
- 已补齐正式目录结构：`SKILL.md`、`agents/openai.yaml`、最小必要 `references/`。
- 已让 skill 风格与当前正式 V5 skills 连续一致。
- 已明确它与兄弟 skills 的分工关系。
- 已避免一次性摊开多个 skill。
- 已让后续新线程可以直接调用本 skill 接手同类 skill-pack 维护任务。

## References

- `references/skill-pack-governance-rules.md`
- `references/workflow-owner-shaping-checklist.md`
- `references/formalization-packaging-rules.md`

- `playbooks/skill-formalization-playbook.md`
- `references/skill-pack-maintenance-checklist.md`
- `templates/skill-formalization-handoff-template.md`
# V5 skill pack 治理规则

## 1. 目的

把 `build-v5-skill-pack` 绑定到 **V5 skill 库本身的维护治理**，避免它越来越像“什么都能做一点”的泛化技能。

这份规则主要回答 4 个问题：

1. 什么样的问题属于 skill-pack 维护
2. 什么样的问题不该继续停留在 skill-pack 线程
3. skill-pack 维护应该落到哪些正式文件
4. skill-pack 如何与业务 owner skills 保持清晰分工

## 2. 应该纳入正式治理的对象

优先纳入：

- 已正式落在 `.codex/skills/` 下、但仍存在乱码、残缺、失真、路由不清的 V5 skill
- 正在从桌面草案或半成品转正式的 V5 workflow owner skill
- 缺少最小 packaging 的 skill：只有 `SKILL.md`，却没有可用 `agents/openai.yaml`、references、playbook 或 template
- 与兄弟 skill 之间开始出现 owner 重叠、路由混乱、边界漂移的 skill
- 已经影响后续线程稳定接棒的 skill-pack 配套文件

## 3. 不应纳入本 skill 直接接管的对象

不要继续留在本 skill 的情形：

- 主问题已经是 `apps/web` 业务控制面实现
- 主问题已经是 `apps/web` 结构治理与大文件瘦身
- 主问题已经是 backend + web + docs + verify 的跨层交付
- 主问题已经是运行事实验证、build、API 或页面回归
- 主问题已经是冻结文档回填、状态治理或阶段裁定

判断标准不是“这个问题和 skill 有没有一点关系”，而是：**线程当前最重要的 owner 是不是 skill-pack 本身。**

## 4. 治理粒度规则

默认遵守：

- 一次只治理一个 skill，或一个紧密相关的 skill-pack 切片
- 优先修复“可读性 + owner + 路由 + packaging”四类核心问题
- 只有在目标 skill 与某个兄弟 skill 的边界确实失真时，才补最小必要的联动治理规则
- 能通过 references / playbook / template 澄清的，不要轻易扩大到跨范围改写多个 skill 本体

## 5. 风格统一规则

V5 正式 skill-pack 应持续保持：

- 中文详细描述
- 明确 owner
- 明确什么时候使用 / 不要使用
- 明确开始入口与最小必读材料
- 明确标准工作流
- 明确兄弟 skill 协作契约
- 明确 done checklist
- 明确最小 packaging 与 handoff

新修或重写的内容应继续沿用这种结构，而不是另起一套写法。

## 6. 可读性与编码规则

正式 skill-pack 文件必须满足：

- UTF-8 可读
- 无乱码、无连续问号占位乱码、无语义断裂
- 标题层级清楚
- 列表和规则可直接执行
- 模板和 playbook 不是摆设，能被后续线程直接复用

如果文件不可读，再好的规则也等于不存在；修复可读性属于一等优先级。

## 7. 与兄弟 skill 的治理分界

- `build-v5-skill-pack`：维护 skill 包本身
- `write-v5-web-control-surface`：落前端控制面
- `govern-v5-web-structure`：治前端结构
- `drive-v5-orchestrator-delivery`：推进跨层交付
- `verify-v5-runtime-and-regression`：确认运行事实

当边界不清时，本 skill 负责 **修清边界**；当边界已经清楚时，就应把线程交回正确 owner。

## 8. 一句话纪律

**V5 skill pack 追求的是“稳定可调用的 owner 技能库”，不是“看起来很多的技能说明集合”。**

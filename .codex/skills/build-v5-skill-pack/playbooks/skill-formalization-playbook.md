# V5 skill 正式化与修复 playbook

## 1. 目的

把一个 V5 skill 或 skill-pack 配套文件，从 **乱码、损坏、边界失真、包装残缺** 恢复为可直接调用的正式 skill 包。

这个 playbook 只负责修 skill 本体，不负责推进 `apps/web`、`runtime/orchestrator`、验证线程或阶段裁定。

## 2. 进入前先判断什么

开始前先回答：

1. 当前主问题是 skill 文件不可读、边界不清、prompt 失真、配套缺失吗？
2. 还是其实已经明确属于前端控制面、前端结构治理、跨层交付、运行验证、文档治理或阶段裁定？
3. 如果不先修 skill，本轮后续线程是否还会被错误 owner 带偏？

如果根因已经是业务交付本身，而不是 skill 本体损坏，就不要继续留在 `build-v5-skill-pack`。

## 3. 最小执行步骤

### 步骤 1：先做 inventory

至少检查：

- `SKILL.md` 是否可读、结构是否完整
- `agents/openai.yaml` 是否存在、是否与 skill 名称匹配
- `references/*`、`playbooks/*`、`templates/*` 是否可读可用
- `SKILL.md` 中引用的配套文件是否真实存在

### 步骤 2：锁定维护类型

把本轮明确归类为：

- 体检
- 修复
- 补强
- 正式化
- 联动治理

如果只是修乱码和损坏，默认按“最小修复”执行，不扩范围。

### 步骤 3：先修可读性，再修 packaging

优先顺序：

1. 修文档可读性与编码
2. 修 owner 与边界语义
3. 修引用关系与配套文件完整性
4. 最后补最小必要的 playbook / template 可执行语义

### 步骤 4：核对兄弟 skill 路由

只核对与目标 skill 最容易冲突的兄弟 skill，确认：

- 当前 owner 是否清楚
- 什么时候应切给兄弟 skill
- 是否存在越权抢活的描述

## 4. 执行时重点检查什么

- 是否仍有乱码、问号占位、断裂语义
- 是否还能一句话说清“它负责什么 / 不负责什么”
- `SKILL.md`、agent、references、playbook、template 是否同步
- routing、开始入口、标准步骤、交接规则是否完整
- 是否借修 skill 之名扩大到了业务实现或验证

## 5. 完成后怎么输出

结束时至少输出：

- 本轮维护对象与维护类型
- 发现了哪些损坏点
- 修了哪些文件、每个文件补了什么
- 与哪些兄弟 skill 的边界更清楚了
- 之后哪些情况应该先调用 `build-v5-skill-pack`
- 如果继续推进业务，应切到哪个 owner skill

## 6. 什么时候应该让位给兄弟 skill

- 主问题是前端控制面功能落地 → `write-v5-web-control-surface`
- 主问题是前端结构治理与锚点稳定 → `govern-v5-web-structure`
- 主问题是跨 backend / web / docs / verify 的整链推进 → `drive-v5-orchestrator-delivery`
- 主问题是运行事实、build、页面、API、回归验证 → `verify-v5-runtime-and-regression`
- 主问题是文档冻结、状态回填与交接治理 → `manage-v5-plan-and-freeze-docs`
- 主问题是代码与合同风险审查 → `review-v5-code-and-risk`
- 主问题是阶段 Pass / Partial / Blocked 裁定 → `accept-v5-milestone-gate`

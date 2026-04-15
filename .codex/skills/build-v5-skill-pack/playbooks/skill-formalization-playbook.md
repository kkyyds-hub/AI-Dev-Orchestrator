# V5 skill 正式化与补强 playbook

## 1. 目标

把一个 V5 草案 skill、损坏 skill 或半成品 skill-pack，推进成 **可直接调用、可重复维护、可稳定交接** 的正式 owner 包。

## 2. 适用场景

适用于以下维护类型：

1. 体检：先查清当前 skill 是否还能带路
2. 修复：修乱码、缺章、失真 prompt、残缺 packaging
3. 补强：补边界、路由、references、playbook、template
4. 正式化：把草案转成正式 `.codex/skills/<skill>/...` 结构
5. 联动治理：澄清与兄弟 skill 的 owner 分工

## 3. 标准步骤

### 第一步：锁定维护对象

先写清：

- 当前要维护哪个 skill
- 本轮属于哪种维护类型
- 为什么此时应该先调 `build-v5-skill-pack`

### 第二步：做最小体检

至少检查：

- 文件是否可读
- owner 与边界是否清楚
- 开始入口与工作流是否完整
- packaging 是否同步
- 与兄弟 skill 的路由是否失真

### 第三步：先判是不是业务 owner 选错了

如果问题根因其实已经是：

- 前端控制面实现
- 前端结构治理
- 跨层交付
- 运行验证

就不要继续留在 skill-pack 线程；只有 skill 本身失真时才继续维护。

### 第四步：修正文，再修 packaging

优先顺序：

1. 修 `SKILL.md`
2. 修 `agents/openai.yaml`
3. 补最小必要 references
4. 如需重复复用，再修 playbook / template

### 第五步：补联动治理

当目标 skill 与兄弟 skill 容易混淆时，补：

- 明确路由矩阵
- 明确切换条件
- 明确不要越权的面

### 第六步：输出 handoff

最后用模板写清：

- 本轮修了什么
- 边界如何更清楚了
- 后续哪些情况应该先调 `build-v5-skill-pack`
- 如果继续推进业务，应切到哪个 owner

## 4. 完成标准

这份 playbook 走完后，至少应得到：

- 可读、可调用的正式 skill 文件
- 同步好的 prompt 与 references
- 可复用的 handoff 说明
- 更稳定的兄弟 skill 路由关系

## 5. 一句话纪律

**正式化与补强的终点不是“看起来更完整”，而是“下一线程真的能拿来用”。**
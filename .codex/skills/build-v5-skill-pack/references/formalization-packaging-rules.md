# V5 正式 skill 打包规则

## 1. 目的

把桌面草案、半成品 skill 或损坏的 skill 包，转成 **可直接调用、可重复维护、可稳定接力** 的正式 skill-pack。

正式化不是简单复制文字，而是要把 owner、路由、包装与配套一起补齐。

## 2. 正式 skill-pack 的最低结构

至少应包含：

- `SKILL.md`
- `agents/openai.yaml`
- 最小必要的 `references/*`

如果这个 skill 需要重复维护、反复交接或提供标准 handoff，再补：

- `playbooks/*`
- `templates/*`

## 3. `SKILL.md` 规则

`SKILL.md` 至少要做到：

- front matter 只有清楚的 `name` 与 `description`
- description 能说明 owner 任务，而不是只写标题
- 正文是中文、可读、无乱码、无占位问号
- 写清 owner、边界、开始入口、工作流、红线、done checklist
- 写清与关键兄弟 skill 的分工与切换条件
- 能回答“什么时候应该先调用这个 skill”

## 4. `agents/openai.yaml` 规则

`agents/openai.yaml` 应做到：

- `display_name` 清楚可识别
- `short_description` 简短但不失 owner 重点
- `default_prompt` 能准确触发这个 skill 的 owner 行为
- prompt 中写清主任务、边界、关键兄弟 skill 路由与不要越权的面

如果 prompt 过空、过宽或过于泛化，skill 很容易被错误调用。

## 5. `references/*` 规则

references 只为提升可执行性而存在，优先补：

- owner / 边界判断规则
- 路由矩阵
- packaging 规则
- 维护 / 验收检查清单
- handoff 所需的最小模板

不要为了“看起来完整”而堆无关参考文件。

## 6. `playbooks/*` 与 `templates/*` 规则

当 skill 本身承担重复维护、正式化包装或交接职责时，playbook / template 应做到：

- 能指导同类任务的标准步骤
- 能复用，不依赖当前线程隐含背景
- 和 `SKILL.md`、references 用词一致
- 不出现乱码、问号占位或断裂语义

## 7. 正式化同步检查

每次正式化或补强后，至少同时确认：

- `SKILL.md` 与 `default_prompt` 是否说的是同一个 owner
- references 是否真的支持正文提到的判断动作
- playbook / template 是否还能被新线程直接拿来用
- 配套文件之间是否互相引用一致

## 8. 一句话纪律

**正式化不是“把草案搬进仓库”，而是让 skill 真正变成可直接调用的正式 owner 包。**
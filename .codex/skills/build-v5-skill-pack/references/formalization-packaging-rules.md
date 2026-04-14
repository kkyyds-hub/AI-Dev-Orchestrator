# V5 正式 skill 打包规则

## 1. 目的

把桌面草案转成正式 skill，不是简单复制粘贴，而是要补齐正式包装。

## 2. 正式 skill 最低结构

至少包含：

- `SKILL.md`
- `agents/openai.yaml`
- 最小必要的 `references/`

## 3. 转正式时要同步检查

- frontmatter 是否只有 `name` 与 `description`
- description 是否能触发 skill，而不是只写标题
- 正文是否已经是中文详细版
- 是否明确绑定 V5 母本
- 是否明确与兄弟 skill 的分工

## 4. references 规则

只有在确实提高可执行性时才新增 references。

优先新增：

- 边界规则
- 路由规则
- 输出 / 交接规则

## 5. agent metadata 规则

`agents/openai.yaml` 应做到：

- display_name 清晰
- short_description 简短明确
- default_prompt 能反映 skill 的 owner 职责

## 6. 一句话纪律

正式化不是把草案搬家，而是让 skill 真正变得可被后续线程直接调用。

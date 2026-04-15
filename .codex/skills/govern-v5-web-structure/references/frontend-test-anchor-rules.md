# 前端测试锚点规范

## 1. 目的

降低浏览器证据脚本、smoke 和回归对页面文案与脆弱 DOM 结构的依赖。

## 2. 默认必须补 `data-testid` 的位置

以下场景默认应补 `data-testid`：

- 关键按钮
- 关键结果区块
- 任务表 / 详情区 / drilldown 入口
- 新增的 panel / drawer / modal
- 关键状态卡片
- 当前或后续会被 smoke / 浏览器证据关注的区域

## 3. 定位优先级

推荐测试定位优先级：

1. `data-testid`
2. 稳定 role / aria 语义
3. 最后才是中文标题或文案

## 4. 变更纪律

如果改动了以下内容，应明确说明影响：
- 关键标题
- 关键按钮文案
- 关键区块位置
- 关键 testid 名称

## 5. testid 命名建议

命名应：
- 简洁
- 稳定
- 反映语义

例如：
- `manual-run-result-section`
- `task-table`
- `project-detail-panel`
- `strategy-preview-panel`

避免：
- 纯样式名
- 含实现细节的临时变量名
- 带版本号或日期的名字

## 6. 一句话纪律

测试锚点要稳定绑定“语义区块”，而不是脆弱绑定“页面长相”。

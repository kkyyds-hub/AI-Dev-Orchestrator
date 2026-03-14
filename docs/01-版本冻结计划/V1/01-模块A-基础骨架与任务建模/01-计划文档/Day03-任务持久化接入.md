
# Day03 任务持久化接入

- 版本：`V1`
- 模块 / 提案：`模块A：基础骨架与任务建模`
- 原始日期：`2026-03-11`
- 原始来源：`历史标签/每日计划/2026-03-11-V1任务持久化接入/01-今日计划.md`
- 当前回填状态：**已完成**
- 回填口径：原日计划已完成并已回填。

---

## 今日目标

完成 `Task / Run` 最小持久化接入，让 Day 2 冻结的数据模型可以正式落到 `SQLite`

---

## 当日交付

1. 数据库文件位置约定
2. 数据库连接模块
3. 初始化入口约定
4. `Task` 表定义
5. `Run` 表定义
6. `Task -> Run` 关系映射
7. 最小建表初始化代码
8. 本地 `SQLite` 数据库文件
---

## 验收点

1. 数据库连接入口唯一且清晰
2. Day 4 可以直接复用 Day 3 的持久化基础
3. `Task / Run` 表结构可正常创建
4. 表结构与 Day 2 的模型边界保持一致
5. 本地数据库文件已生成
6. `Task / Run` 核心表已创建成功
7. Day 4 可以直接基于数据库继续做任务创建接口
---

## 回填记录

- 当前结论：**已完成**
- 回填说明：原日计划已完成并已回填。
- 回填证据：
1. 已补充 `runtime/orchestrator/app/core/db.py`
2. 已补充 `runtime/orchestrator/app/core/config.py` 的数据库路径配置
3. 已生成本地目录 `runtime/data/db/`
4. 已补充 `runtime/orchestrator/app/core/db_tables.py`
5. 已创建 `tasks` / `runs` 表结构与 `Task -> Run` 外键关系
6. 已通过 `init_database()` 生成 `runtime/data/db/orchestrator.db`
7. 已验证数据库中存在 `tasks`、`runs` 两张核心表
8. 已验证应用生命周期启动时会自动初始化数据库
---

## 关键产物路径

1. `runtime/orchestrator/app/core/db.py`
2. `runtime/orchestrator/app/core/config.py`
3. `runtime/data/db`
4. `runtime/orchestrator/app/core/db_tables.py`
5. `runtime/data/db/orchestrator.db`
---

## 上下游衔接

- 前一日：Day02 任务数据模型定义
- 后一日：Day04 任务创建接口
- 对应测试文档：`docs/01-版本冻结计划/V1/01-模块A-基础骨架与任务建模/02-测试验证/Day03-任务持久化接入-测试.md`

---

## 顺延与备注

### 顺延项
1. 仓储层与任务接口顺延到 Day 4
### 备注
1. 已完成 Day 3 最小持久化接入，`Task / Run` 已正式具备本地 `SQLite` 落库基础

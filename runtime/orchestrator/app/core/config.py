"""最小配置模块。

当前阶段不引入复杂配置系统，先用最简单、最容易理解的方式：

- 从环境变量读取配置
- 给出合理默认值
- 统一对外暴露 `settings`

这样做的好处是：

- 对初学阶段更友好
- 代码足够直接
- 后续如果要升级到更复杂的配置方案，也有清晰入口
"""

from dataclasses import dataclass
import os
from pathlib import Path


def _read_bool(name: str, default: bool) -> bool:
    """从环境变量读取布尔值。

    环境变量本质上都是字符串，所以这里做一次简单转换。
    常见真值写法：

    - true
    - 1
    - yes
    - on
    """

    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    """应用配置对象。

    `frozen=True` 表示创建后不可修改，能减少运行时被误改的风险。
    `slots=True` 可以让对象更轻量，也能帮助初学者建立“配置是固定结构”的概念。
    """

    app_name: str
    app_version: str
    debug: bool
    runtime_data_dir: Path
    sqlite_db_dir: Path
    sqlite_db_path: Path
    sqlite_db_url: str


def load_settings() -> Settings:
    """读取并构造应用配置。"""

    runtime_root = Path(__file__).resolve().parents[3]
    runtime_data_dir = Path(
        os.getenv("RUNTIME_DATA_DIR", str(runtime_root / "data"))
    ).resolve()
    sqlite_db_dir = Path(
        os.getenv("SQLITE_DB_DIR", str(runtime_data_dir / "db"))
    ).resolve()
    sqlite_db_path = Path(
        os.getenv("SQLITE_DB_PATH", str(sqlite_db_dir / "orchestrator.db"))
    ).resolve()

    return Settings(
        app_name=os.getenv("APP_NAME", "AI Dev Orchestrator Backend"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        debug=_read_bool("APP_DEBUG", False),
        runtime_data_dir=runtime_data_dir,
        sqlite_db_dir=sqlite_db_dir,
        sqlite_db_path=sqlite_db_path,
        sqlite_db_url=f"sqlite:///{sqlite_db_path.as_posix()}",
    )


# 整个应用只加载一次配置对象。
# 后续其他模块直接 `from app.core.config import settings` 即可使用。
settings = load_settings()

"""Utilities for preparing Windows-friendly runtime data dirs for smoke scripts."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import shutil
import stat
import time


def _on_rm_error(_func, path: str, _exc_info) -> None:
    """Best-effort handler: clear read-only bit then retry delete."""
    target = Path(path)
    try:
        os.chmod(target, stat.S_IWRITE)
    except OSError:
        return
    try:
        if target.is_dir():
            target.rmdir()
        else:
            target.unlink()
    except OSError:
        return


def _try_remove_tree(path: Path, retries: int = 3, backoff_seconds: float = 0.3) -> bool:
    if not path.exists():
        return True
    for attempt in range(retries):
        try:
            shutil.rmtree(path, onerror=_on_rm_error)
            return True
        except PermissionError:
            if attempt + 1 >= retries:
                return False
            time.sleep(backoff_seconds * (attempt + 1))
    return False


def prepare_runtime_data_dir(base_dir: Path) -> Path:
    """Prepare runtime data dir; fallback to isolated dir if cleanup is blocked."""
    runtime_dir = base_dir
    if base_dir.exists() and not _try_remove_tree(base_dir):
        stamp = datetime.utcnow().strftime("%Y%m%dt%H%M%S%f")
        runtime_dir = base_dir.parent / f"{base_dir.name}-isolated-{stamp}"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    os.environ["RUNTIME_DATA_DIR"] = str(runtime_dir)
    return runtime_dir

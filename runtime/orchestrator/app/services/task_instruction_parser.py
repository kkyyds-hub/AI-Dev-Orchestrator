"""任务输入解析工具。

Day 7 / Day 8 继续复用 `Task.input_summary` 作为最小执行与验证输入。
为了避免在 `Executor` 和 `Verifier` 中重复写前缀解析逻辑，
这里集中提供最小解析工具。
"""


def extract_prefixed_payload(
    input_summary: str,
    prefixes: tuple[str, ...],
) -> str | None:
    """从多行输入中提取指定前缀对应的内容。"""

    for raw_line in input_summary.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lower_line = line.lower()
        for prefix in prefixes:
            if lower_line.startswith(prefix):
                payload = line[len(prefix) :].strip()
                return payload

    return None


"""任务输入解析工具。

Day 7 / Day 8 继续复用 `Task.input_summary` 作为最小执行与验证输入。
Day 14 在不扩展 `Task` 数据模型字段的前提下，
继续通过约定前缀支持结构化验证模板。
"""


_VERIFICATION_TEMPLATE_ALIASES = {
    "pytest": "pytest",
    "py-test": "pytest",
    "npm-test": "npm-test",
    "npm_test": "npm-test",
    "npm-build": "npm-build",
    "npm_build": "npm-build",
    "python-compileall": "python-compileall",
    "compileall": "python-compileall",
}


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


def extract_verification_template(input_summary: str) -> str | None:
    """Extract and normalize the optional Day 14 verification template."""

    template = extract_prefixed_payload(
        input_summary,
        ("verify_template:", "verify-template:", "verification_template:"),
    )
    if template is None:
        return None

    normalized = template.strip().lower().replace(" ", "-")
    return _VERIFICATION_TEMPLATE_ALIASES.get(normalized, normalized)

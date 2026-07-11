"""Check relative links in Markdown files resolve to existing paths."""

import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

SKIP_SCHEMES = {"http", "https", "mailto", "tel", "#"}


def check_file(path: Path, root: Path) -> list[str]:
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return [f"{path}: cannot read"]

    for lineno, line in enumerate(text.splitlines(), 1):
        for match in LINK_RE.finditer(line):
            target = match.group(2).strip()
            if any(target.startswith(s + ":") for s in SKIP_SCHEMES):
                continue
            anchor = ""
            if "#" in target:
                target, anchor = target.split("#", 1)
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                errors.append(f"{path}:{lineno}: broken link -> {match.group(2)}")
    return errors


def main() -> int:
    root = Path.cwd()
    md_files = sorted(root.rglob("*.md"))
    all_errors: list[str] = []
    for md in md_files:
        parts = md.relative_to(root).parts
        if any(p.startswith(".") for p in parts):
            continue
        if "node_modules" in parts:
            continue
        all_errors.extend(check_file(md, root))

    for err in all_errors:
        print(err)
    if all_errors:
        print(f"\n{len(all_errors)} broken link(s) found.")
        return 1
    print("All Markdown relative links verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

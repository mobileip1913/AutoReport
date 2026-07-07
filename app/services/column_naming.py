"""Excel 列头 → MySQL 物理列名。"""

from __future__ import annotations

import re


def slugify_header(header: str, used: set[str] | None = None) -> str:
    text = (header or "").strip().lower()
    text = text.replace("#", "num")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        text = "col"
    if text[0].isdigit():
        text = f"c_{text}"
    base = text[:60]
    name = base
    used = used or set()
    i = 2
    while name in used:
        suffix = f"_{i}"
        name = base[: 60 - len(suffix)] + suffix
        i += 1
    used.add(name)
    return name

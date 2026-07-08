"""生成刷单/运费/样品单 Excel 导入模板到 files/import_templates/。

用法（venv 下）：python scripts/generate_import_templates.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.review_import import (  # noqa: E402
    build_review_logistics_template_bytes,
    build_review_template_bytes,
)
from app.services.sample_import import build_sample_template_bytes  # noqa: E402

OUT = ROOT / "files" / "import_templates"
FILES = {
    "review_orders_template.xlsx": build_review_template_bytes,
    "review_logistics_template.xlsx": build_review_logistics_template_bytes,
    "sample_orders_template.xlsx": build_sample_template_bytes,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, builder in FILES.items():
        path = OUT / name
        path.write_bytes(builder())
        print(f"written {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

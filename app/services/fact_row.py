from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FactRow:
    """与 DataRow 兼容的轻量行对象，供 field_aggregator 使用。"""

    data_import_id: int
    sheet_name: str
    row_data: dict

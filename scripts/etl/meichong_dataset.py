# -*- coding: utf-8 -*-
"""美宠数据源 ETL 配置：文件关键字、Sheet、生产事实表 `eb_overseas_tk_*`。"""

from __future__ import annotations

from app.services.production_schema import PRODUCTION_TABLE_BY_SHEET

FILE_SHEETS: list[tuple[str, set[str]]] = [
    ("订单", {"OrderSKUList"}),
    ("退货退款单", {"0"}),
    ("结算表", {"Order details"}),
    ("未结算单", {"Unsettled order and adjustment"}),
    ("联盟达人佣金", {"Sheet1"}),
    ("联盟服务商佣金", {"Sheet1"}),
]

_BASE_SHEET_SPECS: dict[tuple[str, str], dict] = {
    ("订单", "OrderSKUList"): {
        "biz_date_header": "Created Time",
        "biz_date_format": "us",
    },
    ("退货退款单", "0"): {
        "biz_date_header": "Refund Time",
        "biz_date_format": "eu",
    },
    ("结算表", "Order details"): {
        "biz_date_header": "Order created date",
        "biz_date_format": "iso",
    },
    ("未结算单", "Unsettled order and adjustment"): {
        "biz_date_header": "Order created date",
        "biz_date_format": "iso",
    },
    ("联盟达人佣金", "Sheet1"): {
        "biz_date_header": "Time Created",
        "biz_date_format": None,
    },
    ("联盟服务商佣金", "Sheet1"): {
        "biz_date_header": "Time Created",
        "biz_date_format": None,
    },
}


def build_sheet_specs() -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for key, base in _BASE_SHEET_SPECS.items():
        fact_table = PRODUCTION_TABLE_BY_SHEET.get(key)
        if fact_table:
            out[key] = {**base, "fact_table": fact_table}
    return out


SHEET_SPECS = build_sheet_specs()

# 映射/日报规则依赖列（若 Excel 存在则导入）
REQUIRED_COLUMNS: dict[tuple[str, str], list[str]] = {
    ("订单", "OrderSKUList"): [
        "Order ID", "SKU ID", "Created Time", "Cancelled Time",
        "Order Amount", "Payment platform discount",
        "SKU Platform Discount", "SKU Subtotal After Discount", "SKU Subtotal Before Discount",
    ],
    ("退货退款单", "0"): ["Order ID", "Refund Time", "Return unit price"],
    ("联盟达人佣金", "Sheet1"): [
        "Order ID", "SKU ID",
        "Est. standard commission payment", "Est. Shop Ads commission payment",
        "Actual Shop Ads commission payment",
    ],
    ("联盟服务商佣金", "Sheet1"): [
        "Order ID", "SKU ID",
        "Est. Shop Ads commission payment", "Est. Commission for Affiliate Partner",
    ],
    ("结算表", "Order details"): ["Fees", "Order created date", "Order/adjustment ID", "Related order ID"],
    ("未结算单", "Unsettled order and adjustment"): ["Order created date", "Fees", "Related order ID"],
}

EXTRA_COLUMNS = REQUIRED_COLUMNS

# -*- coding: utf-8 -*-
"""美宠数据源 ETL 配置：文件关键字、Sheet、事实表、业务日期列。"""

from __future__ import annotations

FILE_SHEETS: list[tuple[str, set[str]]] = [
    ("订单", {"OrderSKUList"}),
    ("退货退款单", {"0"}),
    ("结算表", {"Order details", "Statements", "Payments"}),
    ("未结算单", {"Unsettled order and adjustment"}),
    ("联盟达人佣金", {"Sheet1"}),
    ("联盟服务商佣金", {"Sheet1"}),
]

SHEET_SPECS: dict[tuple[str, str], dict] = {
    ("订单", "OrderSKUList"): {
        "fact_table": "fact_mc_order_sku",
        "biz_date_header": "Created Time",
        "biz_date_format": "us",
    },
    ("退货退款单", "0"): {
        "fact_table": "fact_mc_return",
        "biz_date_header": "Refund Time",
        "biz_date_format": "eu",
    },
    ("结算表", "Order details"): {
        "fact_table": "fact_mc_settlement_details",
        "biz_date_header": "Order created date",
        "biz_date_format": "iso",
    },
    ("结算表", "Statements"): {
        "fact_table": "fact_mc_settlement_statements",
        "biz_date_header": "Statement date",
        "biz_date_format": "iso",
    },
    ("结算表", "Payments"): {
        "fact_table": "fact_mc_settlement_payments",
        "biz_date_header": "Payment completion date",
        "biz_date_format": "iso",
    },
    ("未结算单", "Unsettled order and adjustment"): {
        "fact_table": "fact_mc_unsettled",
        "biz_date_header": "Order created date",
        "biz_date_format": "iso",
    },
    ("联盟达人佣金", "Sheet1"): {
        "fact_table": "fact_mc_affiliate_creator",
        "biz_date_header": "Time Created",
        "biz_date_format": None,
    },
    ("联盟服务商佣金", "Sheet1"): {
        "fact_table": "fact_mc_affiliate_partner",
        "biz_date_header": "Time Created",
        "biz_date_format": None,
    },
}

# 映射/日报规则依赖列（若 Excel 存在则导入）
REQUIRED_COLUMNS: dict[tuple[str, str], list[str]] = {
    ("订单", "OrderSKUList"): [
        "Order ID", "SKU ID", "Created Time", "Cancelled Time",
        "Order Amount", "Order Amount1", "Payment platform discount",
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
    ("结算表", "Statements"): ["Statement date", "Fees", "Total settlement amount"],
    ("结算表", "Payments"): ["Payment completion date", "Payment amount", "Payment ID", "Status"],
    ("未结算单", "Unsettled order and adjustment"): ["Order created date", "Fees", "Related order ID"],
}

EXTRA_COLUMNS = REQUIRED_COLUMNS

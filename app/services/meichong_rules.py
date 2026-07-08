"""美宠项目·TikTok 美国本土店日报规则的代码化配置。

依据《美宠日报规则-TK.docx》，把每个日报指标对应到逻辑字段 + 取数规则（parts）。
可编程一次性写入；后续财务可在 Web「字段映射」页可视化调整。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import FieldMapping, FieldMappingPart, LogicalField
from app.services.seed import MEICHONG_SOURCE_NAME

ORDER_FILE = "订单"
RETURN_FILE = "退货退款单"
SETTLE_FILE = "结算表"
CREATOR_FILE = "联盟达人佣金"
PARTNER_FILE = "联盟服务商佣金"

ORDER_SHEET = "OrderSKUList"
RETURN_SHEET = "0"
SETTLE_SHEET = "Order details"
AFF_SHEET = "Sheet1"

SKU_TOTAL_COLS = ["SKU Subtotal After Discount", "SKU Platform Discount"]

# 数据源日报上下文配置
MEICHONG_CONFIG = {
    "order_file": ORDER_FILE,
    "order_sheet": ORDER_SHEET,
    "order_id_col": "Order ID",
    "sku_id_col": "SKU ID",
    "order_date_col": "Created Time",
    "order_date_format": "us",
    "sample_rule": {"sum_cols": SKU_TOTAL_COLS, "equals": 0},
    "review_order_ids": [],  # 兼容 exclude_review；由 review_orders 导入时同步
    "review_orders": [],  # [{order_id, sku_id, amount, commission, service_fee, logistics, cost}]
    "review_logistics_mode": "per_order_fixed",
    "review_logistics_per_order": 1,
    "review_logistics_exclude_same_day_refund": True,
    "fact_schema": "production",
    "production_store_id": 3,
    "shop_code": "USLCQPEV3N",
    "meta": {"项目": "美宠", "平台": "TikTok", "区域": "美国", "店铺名称": "平衡贴美国本土店铺"},
}

# 日报逻辑字段：code, 名称, 说明
LOGICAL_FIELDS = [
    ("mc_actual_payment", "实际支付金额", "订单表 Order Amount 按订单去重求和，当日、非样品、非刷单"),
    ("mc_sku_platform_discount", "日报有效SKU平台折扣", "订单表 SKU Platform Discount 求和"),
    ("mc_payment_platform_discount", "日报支付平台折扣", "订单表 Payment platform discount 去重求和"),
    ("mc_receivable_amount", "应收金额", "SKU总额 = SKU Subtotal After Discount + SKU Platform Discount"),
    ("mc_cancelled_amount", "日报取消订单金额", "SKU总额，Created Time=日报日且 Order Status=Canceled"),
    ("mc_refunded_amount", "日报退款订单金额", "退货退款表，Refund Time=日报日期"),
    ("mc_actual_order_count", "实际订单数", "订单表 Order ID 去重计数，Created Time=日报日、非样品、非刷单"),
    ("mc_cancelled_order_count", "取消订单数", "Created Time=日报日且 Order Status=Canceled 的去重订单数"),
    ("mc_refunded_order_count", "退款订单数", "退货退款表 Refund Time=日报日期 的去重订单数"),
    ("mc_creator_commission", "联盟达人佣金", "Est. standard + Est. Shop Ads commission，关联当日有效订单"),
    ("mc_partner_commission", "联盟服务商佣金", "Est. Shop Ads + Est. Commission for Affiliate Partner，关联当日有效订单"),
    ("mc_shop_commission", "店铺佣金", "结算表 Fees（除达人佣金及运费外平台费用，近似）"),
    # —— 暂无数据来源/规则待定，先建字段，作为占位（=空） ——
    ("mc_ad_spend", "站内消耗(广告费)", "待开发广告费导入"),
    ("mc_logistics_fee", "物流费用", "预估操作费+预估尾程运费，待定=空"),
    ("mc_product_cost", "产品成本", "待定=空"),
    ("mc_review_amount", "刷单金额", "待导入刷单表"),
    ("mc_review_commission", "刷单佣金", "待导入刷单表"),
    ("mc_review_service_fee", "刷单服务费", "待导入刷单表"),
    ("mc_review_logistics", "刷单物流费用", "待导入刷单表"),
    ("mc_review_cost", "刷单成本", "待导入刷单表"),
    ("mc_sample_logistics", "样品单运费", "待定=空"),
    ("mc_sample_cost", "样品单成本", "待定=空"),
    ("mc_fixed_cost", "固定费用", "待定=空"),
    ("mc_frame_return", "框返", "待定=空"),
]


def _part(
    sort_order: int,
    column_header: str,
    *,
    file: str | None = None,
    sheet: str = ORDER_SHEET,
    agg: str = "sum",
    combine: str = "add",
    dedup_keys: list[str] | None = None,
    date_col: str | None = None,
    date_fmt: str | None = None,
    row_filters: list[dict] | None = None,
    exclude_sample: bool = False,
    exclude_review: bool = False,
    join_to_orders: bool = False,
    only_sample: bool = False,
    label: str | None = None,
) -> dict:
    return {
        "sort_order": sort_order,
        "label": label,
        "source_file_keyword": file,
        "sheet_name": sheet,
        "column_header": column_header,
        "aliases": [],
        "combine_op": combine,
        "aggregation": agg,
        "dedup_keys": dedup_keys or [],
        "date_filter_column": date_col,
        "date_format": date_fmt,
        "row_filters": row_filters or [],
        "exclude_sample": exclude_sample,
        "exclude_review": exclude_review,
        "join_to_orders": join_to_orders,
        "only_sample": only_sample,
    }


# 订单表「当日有效行」通用参数
_ORDER_VALID = dict(file=ORDER_FILE, sheet=ORDER_SHEET, date_col="Created Time", date_fmt="us",
                    exclude_sample=True, exclude_review=True)

# 当日下单且已取消（Created Time=日报日，Order Status=Canceled）
_ORDER_STATUS_CANCELED = {"column": "Order Status", "op": "in", "values": ["Canceled", "Cancelled"]}
_ORDER_CANCELLED = dict(
    file=ORDER_FILE,
    sheet=ORDER_SHEET,
    date_col="Created Time",
    date_fmt="us",
    exclude_sample=True,
    exclude_review=True,
    row_filters=[_ORDER_STATUS_CANCELED],
)

# code -> (描述, parts[])
MAPPINGS: dict[str, tuple[str, list[dict]]] = {
    "mc_actual_payment": (
        "订单 Order Amount 按 Order ID 去重求和（当日/非样品/非刷单）",
        [_part(0, "Order Amount", agg="sum_dedup", dedup_keys=["Order ID"], **_ORDER_VALID)],
    ),
    "mc_sku_platform_discount": (
        "订单 SKU Platform Discount 求和（当日/非样品/非刷单）",
        [_part(0, "SKU Platform Discount", agg="sum", **_ORDER_VALID)],
    ),
    "mc_payment_platform_discount": (
        "订单 Payment platform discount 按 Order ID 去重求和",
        [_part(0, "Payment platform discount", agg="sum_dedup", dedup_keys=["Order ID"], **_ORDER_VALID)],
    ),
    "mc_receivable_amount": (
        "应收金额 = SKU Subtotal After Discount + SKU Platform Discount（当日/非样品/非刷单）",
        [
            _part(0, "SKU Subtotal After Discount", agg="sum", **_ORDER_VALID),
            _part(1, "SKU Platform Discount", agg="sum", **_ORDER_VALID),
        ],
    ),
    "mc_cancelled_amount": (
        "取消订单 SKU总额，Created Time=日报日且 Order Status=Canceled",
        [
            _part(0, "SKU Subtotal After Discount", agg="sum", **_ORDER_CANCELLED),
            _part(1, "SKU Platform Discount", agg="sum", **_ORDER_CANCELLED),
        ],
    ),
    "mc_refunded_amount": (
        "退货退款表 Return unit price，Refund Time=日报日期（近似，未乘退货数量）",
        [_part(0, "Return unit price", agg="sum", file=RETURN_FILE, sheet=RETURN_SHEET,
               date_col="Refund Time", date_fmt="eu", exclude_sample=True, exclude_review=True)],
    ),
    "mc_actual_order_count": (
        "订单 Order ID 去重计数（当日/非样品/非刷单）",
        [_part(0, "Order ID", agg="count_distinct", dedup_keys=["Order ID"], **_ORDER_VALID)],
    ),
    "mc_cancelled_order_count": (
        "Created Time=日报日且 Order Status=Canceled 的去重订单数",
        [_part(0, "Order ID", agg="count_distinct", dedup_keys=["Order ID"], **_ORDER_CANCELLED)],
    ),
    "mc_refunded_order_count": (
        "退货退款表 Refund Time=日报日期 的去重订单数",
        [_part(0, "Order ID", agg="count_distinct", dedup_keys=["Order ID"], file=RETURN_FILE,
               sheet=RETURN_SHEET, date_col="Refund Time", date_fmt="eu",
               exclude_sample=True, exclude_review=True)],
    ),
    "mc_creator_commission": (
        "联盟达人佣金 = Est. standard commission payment + Est. Shop Ads commission payment（关联当日有效订单）",
        [
            _part(0, "Est. standard commission payment", agg="sum", file=CREATOR_FILE,
                  sheet=AFF_SHEET, join_to_orders=True),
            _part(1, "Est. Shop Ads commission payment", agg="sum", file=CREATOR_FILE,
                  sheet=AFF_SHEET, join_to_orders=True),
        ],
    ),
    "mc_partner_commission": (
        "联盟服务商佣金 = Est. Shop Ads commission payment + Est. Commission for Affiliate Partner（关联当日有效订单）",
        [
            _part(0, "Est. Shop Ads commission payment", agg="sum", file=PARTNER_FILE,
                  sheet=AFF_SHEET, join_to_orders=True),
            _part(1, "Est. Commission for Affiliate Partner", agg="sum", file=PARTNER_FILE,
                  sheet=AFF_SHEET, join_to_orders=True),
        ],
    ),
    "mc_shop_commission": (
        "结算表 Fees 求和（Order created date=日报日期，近似店铺费用）",
        [_part(0, "Fees", agg="sum", file=SETTLE_FILE, sheet=SETTLE_SHEET,
               date_col="Order created date", date_fmt="iso")],
    ),
    # —— 以下从已导入 Catalog 可推导；刷单/成本等待专用文件接入 ——
    "mc_ad_spend": (
        "结算表广告费（GMV Max ad fee + Smart Promotion campaign period fee，Order created date=日报日期）",
        [
            _part(0, "GMV Max ad fee", agg="sum", file=SETTLE_FILE, sheet=SETTLE_SHEET,
                  date_col="Order created date", date_fmt="iso"),
            _part(1, "Smart Promotion campaign period fee", agg="sum", combine="add", file=SETTLE_FILE,
                  sheet=SETTLE_SHEET, date_col="Order created date", date_fmt="iso"),
        ],
    ),
    "mc_sample_logistics": (
        "样品单运费 = 订单 Shipping Fee After Discount，仅样品单、Created Time=日报日期",
        [_part(0, "Shipping Fee After Discount", agg="sum_dedup", dedup_keys=["Order ID"],
               file=ORDER_FILE, sheet=ORDER_SHEET, date_col="Created Time", date_fmt="us",
               only_sample=True)],
    ),
}

# 尚无对应 Excel / Catalog 文件的占位指标（报表行保留，出报=0）
PENDING_FILE_CODES = {
    "mc_sample_cost",
    "mc_logistics_fee",
    "mc_product_cost",
    "mc_fixed_cost",
    "mc_frame_return",
}


# 导出 Excel 后由财务手工填写的行（系统不算数、单元格留空）
MANUAL_FILL_LABELS = frozenset({"利润", "总利润", "利润(估算)", "总利润(估算)"})
_LEGACY_MANUAL_LABELS = {"利润": "利润(估算)", "总利润": "总利润(估算)"}

MEICHONG_TEMPLATE_NAME = "美宠TK美国本土店日报"

# 报表指标行：sort, label, expression, format, highlight
TEMPLATE_LINES = [
    (1, "实际支付金额", "{field:mc_actual_payment}", "usd", False),
    (2, "应支付金额", "={field:mc_actual_payment}+{field:mc_payment_platform_discount}+{field:mc_sku_platform_discount}", "usd", False),
    (3, "应收金额", "{field:mc_receivable_amount}", "usd", True),
    (4, "退单金额", "={field:mc_cancelled_amount}+{field:mc_refunded_amount}", "usd", False),
    (5, "刷单金额", "{field:mc_review_amount}", "usd", False),
    (6, "刷单佣金", "{field:mc_review_commission}", "usd", False),
    (7, "刷单服务费", "{field:mc_review_service_fee}", "usd", False),
    (8, "刷单物流费用", "{field:mc_review_logistics}", "usd", False),
    (9, "刷单成本", "{field:mc_review_cost}", "usd", False),
    (10, "样品单运费", "{field:mc_sample_logistics}", "usd", False),
    (11, "样品单成本", "{field:mc_sample_cost}", "usd", False),
    (12, "达人佣金", "={field:mc_creator_commission}+{field:mc_partner_commission}", "usd", False),
    (13, "店铺佣金", "{field:mc_shop_commission}", "usd", False),
    (14, "站内消耗", "{field:mc_ad_spend}", "usd", False),
    (15, "物流费用", "{field:mc_logistics_fee}", "usd", False),
    (16, "产品成本", "{field:mc_product_cost}", "usd", False),
    (17, "固定费用", "{field:mc_fixed_cost}", "usd", False),
    (18, "框返", "{field:mc_frame_return}", "usd", False),
    (19, "下单数", "={field:mc_actual_order_count}-{field:mc_cancelled_order_count}-{field:mc_refunded_order_count}", "integer", False),
    (20, "利润", "", "usd", True),
    (21, "总利润", "", "usd", True),
]

# 输出分组（对应日报模板.xlsx 的列分组），label 与上面一致
TEMPLATE_GROUPS = [
    ("订单情况", ["实际支付金额", "应支付金额", "应收金额", "退单金额"]),
    ("刷单情况", ["刷单金额", "刷单佣金", "刷单服务费", "刷单物流费用", "刷单成本"]),
    ("样品情况", ["样品单运费", "样品单成本"]),
    ("佣金", ["达人佣金", "店铺佣金"]),
    ("成本/费用", ["站内消耗", "物流费用", "产品成本", "固定费用", "框返"]),
    ("订单数 / 利润", ["下单数", "利润", "总利润"]),
]


def seed_meichong_template(db: Session):
    from app.models import ReportTemplate, TemplateLine, TemplateStatus

    tpl = db.query(ReportTemplate).filter(ReportTemplate.name == MEICHONG_TEMPLATE_NAME).first()
    if tpl:
        db.query(TemplateLine).filter(TemplateLine.template_id == tpl.id).delete()
    else:
        tpl = ReportTemplate(
            name=MEICHONG_TEMPLATE_NAME,
            description="按《美宠日报规则-TK》生成；占位指标（刷单/样品/广告/成本/固定费用/框返）待接入对应数据。利润为透明估算口径。",
            status=TemplateStatus.DRAFT,
            owner="财务",
        )
        db.add(tpl)
        db.flush()
    for sort_order, label, expr, fmt, highlight in TEMPLATE_LINES:
        db.add(TemplateLine(template_id=tpl.id, sort_order=sort_order, label=label,
                            expression=expr, format_type=fmt, is_highlight=highlight))
    db.commit()
    db.refresh(tpl)
    return tpl


def ensure_meichong_template(db: Session) -> None:
    from app.models import ReportTemplate

    if not db.query(ReportTemplate).filter(ReportTemplate.name == MEICHONG_TEMPLATE_NAME).first():
        seed_meichong_template(db)


def ensure_meichong_rules(db: Session) -> None:
    """启动时调用：仅当数据源尚未配置（config 为空）时写入规则，避免覆盖用户的 Web 编辑。"""
    from app.models import DataSource

    ds = db.query(DataSource).filter(DataSource.name == MEICHONG_SOURCE_NAME).first()
    if ds and not ds.config:
        apply_meichong_rules(db, reset=True)
    ensure_meichong_template(db)


def apply_meichong_rules(db: Session, reset: bool = True) -> None:
    from app.models import DataSource

    ds = db.query(DataSource).filter(DataSource.name == MEICHONG_SOURCE_NAME).first()
    if not ds:
        raise RuntimeError("美宠数据源不存在，请先运行 ensure_meichong_datasource / 导入数据")

    ds.config = MEICHONG_CONFIG
    db.add(ds)

    # 逻辑字段
    for code, name, desc in LOGICAL_FIELDS:
        lf = db.query(LogicalField).filter(LogicalField.code == code).first()
        if not lf:
            db.add(LogicalField(code=code, name=name, description=desc))
        else:
            lf.name = name
            lf.description = desc
    db.commit()

    field_map = {f.code: f for f in db.query(LogicalField).all()}

    for code, (desc, parts) in MAPPINGS.items():
        lf = field_map[code]
        mapping = (
            db.query(FieldMapping)
            .filter(FieldMapping.data_source_id == ds.id, FieldMapping.line_code == code)
            .first()
        ) or (
            db.query(FieldMapping)
            .filter(FieldMapping.data_source_id == ds.id, FieldMapping.logical_field_id == lf.id)
            .first()
        )
        if mapping and reset:
            db.query(FieldMappingPart).filter(FieldMappingPart.mapping_id == mapping.id).delete()
        if not mapping:
            mapping = FieldMapping(data_source_id=ds.id, logical_field_id=lf.id)
            db.add(mapping)
            db.flush()
        mapping.description = desc
        if reset or not mapping.parts:
            for p in parts:
                db.add(FieldMappingPart(mapping_id=mapping.id, **p))
    db.commit()

    from app.services.report_line_sync import sync_report_lines
    from app.services.meichong_rules import TEMPLATE_GROUPS, TEMPLATE_LINES

    sync_report_lines(db, ds.id, TEMPLATE_LINES, TEMPLATE_GROUPS, only_missing=True)

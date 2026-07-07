from pathlib import Path

from sqlalchemy.orm import Session

from app.models import (
    DataSource,
    FieldMapping,
    LogicalField,
    ReportTemplate,
    TemplateLine,
    TemplateStatus,
)
from app.services.excel_parser import create_sample_excel, parse_excel_file
from app.services.overseas_sample import (
    OVERSEAS_STORE_META,
    create_overseas_ecommerce_excel,
    create_settlement_excel,
)


DEMO_FIELDS = [
    ("sales_amount", "销售额", "sum"),
    ("order_count", "订单数", "count"),
    ("platform_fee", "平台费用", "sum"),
    ("refund_amount", "退款额", "sum"),
    ("ad_spend", "广告花费", "sum"),
    ("ad_clicks", "广告点击", "sum"),
]

AMAZON_MAPPINGS = [
    ("sales_amount", "订单明细", "Sales Amount", ["Revenue", "销售金额"]),
    ("order_count", "订单明细", "订单号", []),
    ("platform_fee", "订单明细", "平台费用", []),
    ("refund_amount", "订单明细", "Refund Amount", ["Refund", "退款金额"]),
    ("ad_spend", "广告数据", "广告花费", []),
    ("ad_clicks", "广告数据", "点击量", []),
]

SHOPEE_MAPPINGS = [
    ("sales_amount", "订单明细", "销售额", ["销售金额"]),
    ("order_count", "订单明细", "订单号", []),
    ("platform_fee", "订单明细", "平台费用", []),
    ("refund_amount", "订单明细", "退款金额", []),
    ("ad_spend", "广告数据", "广告花费", []),
    ("ad_clicks", "广告数据", "点击量", []),
]

DEMO_TEMPLATE_LINES = [
    (1, "销售额", "{field:sales_amount}", "currency", False),
    (2, "订单数", "{field:order_count}", "integer", False),
    (3, "客单价", "={field:sales_amount}/{field:order_count}", "currency", False),
    (4, "平台费用", "{field:platform_fee}", "currency", False),
    (5, "退款额", "{field:refund_amount}", "currency", False),
    (6, "退款率", "={field:refund_amount}/{field:sales_amount}", "percent", False),
    (7, "广告花费", "{field:ad_spend}", "currency", False),
    (8, "ACOS", "={field:ad_spend}/{field:sales_amount}", "percent", False),
    (9, "毛利润", "={field:sales_amount}-{field:platform_fee}-{field:ad_spend}", "currency", True),
    (10, "净利润", "={field:sales_amount}-{field:platform_fee}-{field:refund_amount}-{field:ad_spend}", "currency", True),
]


def seed_demo_data(db: Session, sample_dir: Path) -> None:
    if db.query(DataSource).count() > 0:
        return

    sample_dir.mkdir(parents=True, exist_ok=True)
    create_sample_excel(sample_dir / "amazon_us_store.xlsx", "Amazon", "normal")
    create_sample_excel(sample_dir / "shopee_sg_store.xlsx", "Shopee", "normal")
    create_sample_excel(sample_dir / "amazon_us_store_drift.xlsx", "Amazon", "drift")

    for code, name, agg in DEMO_FIELDS:
        db.add(LogicalField(code=code, name=name, data_type="number", description=f"电商指标: {name}"))
    db.flush()

    amazon = DataSource(name="Amazon US 店铺", platform="Amazon", description="美国站 Amazon 店铺 RPA 数据")
    shopee = DataSource(name="Shopee SG 店铺", platform="Shopee", description="新加坡 Shopee 店铺 RPA 数据")
    db.add_all([amazon, shopee])
    db.flush()

    field_map = {f.code: f for f in db.query(LogicalField).all()}

    for code, sheet, column, aliases in AMAZON_MAPPINGS:
        db.add(
            FieldMapping(
                data_source_id=amazon.id,
                logical_field_id=field_map[code].id,
                sheet_name=sheet,
                column_header=column,
                aliases=aliases,
                aggregation="count" if code == "order_count" else "sum",
            )
        )

    for code, sheet, column, aliases in SHOPEE_MAPPINGS:
        db.add(
            FieldMapping(
                data_source_id=shopee.id,
                logical_field_id=field_map[code].id,
                sheet_name=sheet,
                column_header=column,
                aliases=aliases,
                aggregation="count" if code == "order_count" else "sum",
            )
        )

    template = ReportTemplate(
        name="跨境电商日经营报表",
        description="Demo：财务可自定义指标行与公式，从 Excel 映射字段自动出报",
        status=TemplateStatus.DRAFT,
        owner="张财务",
    )
    db.add(template)
    db.flush()

    for sort_order, label, expression, fmt, highlight in DEMO_TEMPLATE_LINES:
        db.add(
            TemplateLine(
                template_id=template.id,
                sort_order=sort_order,
                label=label,
                expression=expression,
                format_type=fmt,
                is_highlight=highlight,
            )
        )

    db.commit()

    parse_excel_file(db, amazon, sample_dir / "amazon_us_store.xlsx", "2025-06-22", "Amazon-US-001")
    parse_excel_file(db, shopee, sample_dir / "shopee_sg_store.xlsx", "2025-06-22", "Shopee-SG-001")


def ensure_overseas_sample(db: Session, sample_dir: Path) -> None:
    """确保海外电商模拟数据源与 Excel 存在（无预置映射，供用户自行配置测试）。"""
    sample_dir.mkdir(parents=True, exist_ok=True)
    excel_path = sample_dir / "tiktok_uk_store_20250623.xlsx"
    create_overseas_ecommerce_excel(excel_path, OVERSEAS_STORE_META)
    create_settlement_excel(sample_dir / "tiktok_uk_settlement_20250623.xlsx")

    existing = db.query(DataSource).filter(DataSource.platform == "TikTok Shop").first()
    if existing:
        return

    db.add(
        DataSource(
            name="TikTok Shop UK 店铺",
            platform="TikTok Shop",
            description="模拟 RPA 导出：Order Details / Advertising / Returns / Settlement，列头全英文，无预置映射",
        )
    )
    db.commit()


# 美宠项目真实试点数据源（数据文件在 files/ 下，由 scripts/import_meichong.py 导入）
MEICHONG_STORE = "平衡贴美国本土店铺"
MEICHONG_SOURCE_NAME = "美宠-平衡贴美国本土店铺(TK-US)"


def ensure_meichong_datasource(db: Session) -> DataSource:
    """注册美宠 TikTok 美国本土店数据源（不自动导入大文件，导入用独立脚本触发）。"""
    existing = db.query(DataSource).filter(DataSource.name == MEICHONG_SOURCE_NAME).first()
    if existing:
        return existing
    ds = DataSource(
        name=MEICHONG_SOURCE_NAME,
        platform="TikTok Shop",
        description="美宠项目·美国区域·TikTok·平衡贴美国本土店铺。源数据：订单/退货退款/结算/未结算/联盟达人佣金/联盟服务商佣金，按日报规则配置计算逻辑。",
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class TemplateStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    platform = Column(String(50))
    description = Column(Text, nullable=True)
    # 日报计算上下文配置（存在即启用日报模式）：
    # {order_file, order_sheet, order_id_col, sku_id_col, order_date_col, order_date_format,
    #  sample_rule:{sum_cols, equals}, review_order_ids:[], daily_generate_at:"08:00"}
    config = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    imports = relationship("DataImport", back_populates="data_source")
    mappings = relationship("FieldMapping", back_populates="data_source")
    store = relationship("Store", back_populates="data_source", uselist=False)


class Account(Base):
    """Demo 账号：控制可访问的店铺与报表配置。"""

    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    login_name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    store_links = relationship("AccountStore", back_populates="account", cascade="all, delete-orphan")


class Store(Base):
    """店铺：与 DataSource 1:1，报表配置绑定在 data_source_id。"""

    __tablename__ = "stores"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    platform = Column(String(50), nullable=False)
    data_source_id = Column(ForeignKey("data_sources.id"), unique=True, nullable=False)
    # 生产库店铺标识（eb_overseas_tk_* 表按 store_id / shop_code 过滤）
    production_store_id = Column(Integer, nullable=True, index=True)
    shop_code = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    data_source = relationship("DataSource", back_populates="store")
    account_links = relationship("AccountStore", back_populates="store", cascade="all, delete-orphan")


class AccountStore(Base):
    """账号 ↔ 店铺 多对多：一个账号可管理多个店铺。"""

    __tablename__ = "account_stores"
    __table_args__ = (UniqueConstraint("account_id", "store_id"),)

    id = Column(Integer, primary_key=True)
    account_id = Column(ForeignKey("accounts.id"), nullable=False)
    store_id = Column(ForeignKey("stores.id"), nullable=False)

    account = relationship("Account", back_populates="store_links")
    store = relationship("Store", back_populates="account_links")


class DataImport(Base):
    __tablename__ = "data_imports"

    id = Column(Integer, primary_key=True)
    data_source_id = Column(ForeignKey("data_sources.id"))
    file_name = Column(String(255))
    report_date = Column(String(10))
    store_name = Column(String(100))
    status = Column(String(20), default="success")
    row_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    data_source = relationship("DataSource", back_populates="imports")
    rows = relationship("DataRow", back_populates="data_import")


class DataRow(Base):
    __tablename__ = "data_rows"

    id = Column(Integer, primary_key=True)
    data_import_id = Column(ForeignKey("data_imports.id"))
    sheet_name = Column(String(100))
    row_data = Column(JSON)

    data_import = relationship("DataImport", back_populates="rows")


class CatalogFile(Base):
    """逻辑文件：映射 UI 中的「来源文件」。"""

    __tablename__ = "catalog_files"

    id = Column(Integer, primary_key=True)
    data_source_id = Column(ForeignKey("data_sources.id"), index=True)
    keyword = Column(String(100), nullable=False)
    file_label = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    sheets = relationship("CatalogSheet", back_populates="file", cascade="all, delete-orphan")


class CatalogSheet(Base):
    """逻辑 Sheet → 物理事实表。"""

    __tablename__ = "catalog_sheets"

    id = Column(Integer, primary_key=True)
    file_id = Column(ForeignKey("catalog_files.id"), index=True)
    sheet_name = Column(String(100), nullable=False)
    fact_table = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)

    file = relationship("CatalogFile", back_populates="sheets")
    columns = relationship("CatalogColumn", back_populates="sheet", cascade="all, delete-orphan")


class CatalogColumn(Base):
    """逻辑列头 → 物理列名。"""

    __tablename__ = "catalog_columns"

    id = Column(Integer, primary_key=True)
    sheet_id = Column(ForeignKey("catalog_sheets.id"), index=True)
    header_name = Column(String(200), nullable=False)
    db_column = Column(String(100), nullable=False)
    column_aliases = Column(JSON, default=list)
    data_type = Column(String(20), default="string")
    is_active = Column(Boolean, default=True)

    sheet = relationship("CatalogSheet", back_populates="columns")


class EtlBatch(Base):
    __tablename__ = "etl_batches"

    id = Column(Integer, primary_key=True)
    data_source_id = Column(ForeignKey("data_sources.id"), index=True)
    store_name = Column(String(100), nullable=False)
    # 对应生产库 excel_order_id（导出批次外键）
    excel_order_id = Column(Integer, nullable=True, index=True)
    source_desc = Column(String(255), nullable=True)
    row_counts = Column(JSON, default=dict)
    status = Column(String(20), default="success")
    created_at = Column(DateTime, default=datetime.utcnow)

    data_source = relationship("DataSource")


class LogicalField(Base):
    __tablename__ = "logical_fields"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True)
    name = Column(String(100))
    data_type = Column(String(20), default="number")
    description = Column(Text, nullable=True)

    mappings = relationship("FieldMapping", back_populates="logical_field")


class FieldMapping(Base):
    __tablename__ = "field_mappings"
    __table_args__ = (UniqueConstraint("data_source_id", "line_code"),)

    id = Column(Integer, primary_key=True)
    data_source_id = Column(ForeignKey("data_sources.id"))
    logical_field_id = Column(ForeignKey("logical_fields.id"), nullable=True)
    # 报表行（与取数/公式合并）
    line_type = Column(String(10), default="fetch")  # fetch | formula | manual | per_order | ratio
    # 每单金额（line_type=per_order）：出报时 = 该金额 × 单数（口径见 per_order_basis）
    per_order_amount = Column(Float, nullable=True)
    # 单数口径：valid_orders(当日去重有效订单数) | review_orders(刷单单数)
    per_order_basis = Column(String(20), nullable=True)
    # 按比例（line_type=ratio）：出报时 = 复用字段(ratio_base_code) 的值 × ratio_percent%
    ratio_percent = Column(Float, nullable=True)
    ratio_base_code = Column(String(50), nullable=True)
    label = Column(String(100), nullable=True)
    line_code = Column(String(50), nullable=True)
    report_group = Column(String(100), nullable=True)
    sort_order = Column(Integer, default=0)
    expression = Column(Text, nullable=True)
    format_type = Column(String(20), default="usd")
    is_highlight = Column(Boolean, default=False)
    owner_id = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    # 兼容旧版单列映射（迁移后可为空）
    sheet_name = Column(String(100), nullable=True)
    column_header = Column(String(100), nullable=True)
    aliases = Column(JSON, default=list)
    aggregation = Column(String(20), default="sum")

    data_source = relationship("DataSource", back_populates="mappings")
    logical_field = relationship("LogicalField", back_populates="mappings")
    parts = relationship(
        "FieldMappingPart",
        back_populates="mapping",
        cascade="all, delete-orphan",
        order_by="FieldMappingPart.sort_order",
    )


class FieldMappingPart(Base):
    """单条取数规则：可从不同文件/Sheet/列读取，支持加减组合与去重。"""

    __tablename__ = "field_mapping_parts"

    id = Column(Integer, primary_key=True)
    mapping_id = Column(ForeignKey("field_mappings.id"))
    sort_order = Column(Integer, default=0)
    label = Column(String(100), nullable=True)
    source_file_keyword = Column(String(100), nullable=True)
    sheet_name = Column(String(100))
    column_header = Column(String(100))
    aliases = Column(JSON, default=list)
    combine_op = Column(String(10), default="add")
    aggregation = Column(String(20), default="sum")
    dedup_keys = Column(JSON, default=list)
    # —— 日报规则增强字段 ——
    # 行级日期过滤：按该列的日期 == 报表日期 过滤（如 Created Time / Refund Time）
    date_filter_column = Column(String(100), nullable=True)
    # 日期格式提示：us(MM/DD/YYYY) | eu(DD/MM/YYYY) | iso(YYYY/MM/DD) | None(自动)
    date_format = Column(String(10), nullable=True)
    # 行过滤条件：[{"column","op","values"}]，op ∈ eq/ne/in/not_in/gt/gte/lt/lte/nonempty
    row_filters = Column(JSON, default=list)
    # 排除样品单（同订单 SKU 总额=0）/ 刷单单（外部清单）
    exclude_sample = Column(Boolean, default=False)
    exclude_review = Column(Boolean, default=False)
    # 排除当日下单且当日退款的订单
    exclude_same_day_refund = Column(Boolean, default=False)
    # 跨表关联：仅保留命中日期主表有效行的记录
    join_to_orders = Column(Boolean, default=False)
    # 关联匹配键列头，如 ["Order ID", "SKU ID"]
    join_keys = Column(JSON, default=list)
    # 组间组合基准字段（与上一来源组对齐），如 ["Order ID"]
    benchmark_keys = Column(JSON, default=list)
    only_sample = Column(Boolean, default=False)
    # 组内多列：同一规则块内先对各列求值再相加/相减
    sources = Column(JSON, default=list)
    # 复用同数据源已配置的逻辑字段（存字段 code，如 mc_actual_payment）
    ref_field_code = Column(String(50), nullable=True)

    mapping = relationship("FieldMapping", back_populates="parts")


class MappingLog(Base):
    __tablename__ = "mapping_logs"

    id = Column(Integer, primary_key=True)
    data_import_id = Column(ForeignKey("data_imports.id"), nullable=True)
    level = Column(String(10), default="warning")
    message = Column(Text)
    context = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    description = Column(Text, nullable=True)
    status = Column(Enum(TemplateStatus), default=TemplateStatus.DRAFT)
    version = Column(Integer, default=1)
    owner = Column(String(50), default="财务Demo")
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lines = relationship("TemplateLine", back_populates="template", cascade="all, delete-orphan")
    runs = relationship("ReportRun", back_populates="template")


class TemplateLine(Base):
    __tablename__ = "template_lines"

    id = Column(Integer, primary_key=True)
    template_id = Column(ForeignKey("report_templates.id"))
    sort_order = Column(Integer, default=0)
    label = Column(String(100))
    expression = Column(Text)
    format_type = Column(String(20), default="number")
    is_highlight = Column(Boolean, default=False)

    template = relationship("ReportTemplate", back_populates="lines")


class ReportRun(Base):
    __tablename__ = "report_runs"

    id = Column(Integer, primary_key=True)
    template_id = Column(ForeignKey("report_templates.id"), nullable=True)
    data_source_id = Column(ForeignKey("data_sources.id"), nullable=True)
    report_date = Column(String(10))
    store_name = Column(String(100))
    is_test = Column(Boolean, default=True)
    status = Column(String(20), default="success")
    created_at = Column(DateTime, default=datetime.utcnow)

    template = relationship("ReportTemplate", back_populates="runs")
    values = relationship("ReportValue", back_populates="report_run", cascade="all, delete-orphan")


class ReportValue(Base):
    __tablename__ = "report_values"

    id = Column(Integer, primary_key=True)
    report_run_id = Column(ForeignKey("report_runs.id"))
    mapping_id = Column(ForeignKey("field_mappings.id"), nullable=True)
    line_code = Column(String(50), nullable=True)
    line_label = Column(String(100))
    expression = Column(Text)
    raw_value = Column(Float, nullable=True)
    computed_raw_value = Column(Float, nullable=True)
    display_value = Column(String(50))
    is_overridden = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    report_group = Column(String(100), nullable=True)

    report_run = relationship("ReportRun", back_populates="values")
    mapping = relationship("FieldMapping", foreign_keys=[mapping_id])

# -*- coding: utf-8 -*-
"""写入美宠日报规则（数据源 config + 逻辑字段 + 字段映射），并做一次聚合自检。

用法（venv 下）：python scripts/setup_meichong.py [报表日期 YYYY-MM-DD]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models import DataSource, LogicalField
from app.services.meichong_rules import LOGICAL_FIELDS, apply_meichong_rules
from app.services.migrate import run_migrations
from app.services.report_engine import aggregate_field_values
from app.services.seed import MEICHONG_SOURCE_NAME, MEICHONG_STORE


def main(report_date: str) -> None:
    run_migrations()
    db = SessionLocal()
    try:
        apply_meichong_rules(db, reset=True)
        ds = db.query(DataSource).filter(DataSource.name == MEICHONG_SOURCE_NAME).first()
        print(f"数据源 #{ds.id} config 已写入，order_sheet={ds.config.get('order_sheet')}")

        values, warnings = aggregate_field_values(db, ds.id, report_date, MEICHONG_STORE)
        name_map = {code: name for code, name, _ in LOGICAL_FIELDS}
        print(f"\n=== {report_date} 聚合结果 ===")
        for code in [c for c, _, _ in LOGICAL_FIELDS]:
            if code in values:
                print(f"  {name_map.get(code, code):<16} ({code}) = {values[code]:,.2f}")
        print("\n衍生指标：")
        v = values
        payable = v.get("mc_actual_payment", 0) + v.get("mc_payment_platform_discount", 0) + v.get("mc_sku_platform_discount", 0)
        refund_total = v.get("mc_cancelled_amount", 0) + v.get("mc_refunded_amount", 0)
        order_count = v.get("mc_actual_order_count", 0) - v.get("mc_cancelled_order_count", 0) - v.get("mc_refunded_order_count", 0)
        aff = v.get("mc_creator_commission", 0) + v.get("mc_partner_commission", 0)
        print(f"  应支付金额 = {payable:,.2f}")
        print(f"  退单金额   = {refund_total:,.2f}")
        print(f"  下单数     = {order_count:,.0f}")
        print(f"  达人佣金合计 = {aff:,.2f}")

        if warnings:
            print(f"\n告警 {len(warnings)} 条：")
            for w in warnings[:20]:
                print(f"  - {w}")
    finally:
        db.close()


if __name__ == "__main__":
    rd = sys.argv[1] if len(sys.argv) > 1 else "2026-06-22"
    main(rd)

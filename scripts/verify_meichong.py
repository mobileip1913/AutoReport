# -*- coding: utf-8 -*-
"""端到端对账：从事实表独立重算关键指标，与引擎结果交叉验证。

用法（venv 下）：python scripts/verify_meichong.py [YYYY-MM-DD]
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models import DataSource
from app.services.fact_provider import load_fact_rows
from app.services.field_aggregator import _to_number, parse_date
from app.services.report_engine import aggregate_field_values
from app.services.seed import MEICHONG_SOURCE_NAME, MEICHONG_STORE


def main(report_date: str) -> None:
    db = SessionLocal()
    ds = db.query(DataSource).filter(DataSource.name == MEICHONG_SOURCE_NAME).first()
    fact_rows, _ = load_fact_rows(db, ds.id, MEICHONG_STORE)
    rd = parse_date(report_date, "iso")

    order_rows = [r for r in fact_rows if r.sheet_name == "OrderSKUList"]

    # 样品订单集：同订单 SKU 总额(After+Platform)=0
    per_order_total = defaultdict(float)
    for r in order_rows:
        oid = str(r.row_data.get("Order ID", "")).strip()
        if not oid:
            continue
        per_order_total[oid] += _to_number(r.row_data.get("SKU Subtotal After Discount")) + _to_number(r.row_data.get("SKU Platform Discount"))
    sample_ids = {o for o, t in per_order_total.items() if abs(t) < 0.01}

    # 当日订单（Created Time=rd），非样品
    today_orders = set()
    order_amount = {}
    for r in order_rows:
        oid = str(r.row_data.get("Order ID", "")).strip()
        if not oid or oid in sample_ids:
            continue
        if parse_date(r.row_data.get("Created Time"), "us") != rd:
            continue
        today_orders.add(oid)
        order_amount[oid] = _to_number(r.row_data.get("Order Amount"))

    indep_actual_payment = sum(order_amount.values())
    indep_order_count = len(today_orders)

    # 应收金额：当日非样品订单全部 SKU 行的 (After + Platform) 之和
    indep_receivable = 0.0
    for r in order_rows:
        oid = str(r.row_data.get("Order ID", "")).strip()
        if oid in today_orders:
            indep_receivable += _to_number(r.row_data.get("SKU Subtotal After Discount")) + _to_number(r.row_data.get("SKU Platform Discount"))

    total_orders_today = len({str(r.row_data.get("Order ID", "")).strip() for r in order_rows
                              if parse_date(r.row_data.get("Created Time"), "us") == rd and str(r.row_data.get("Order ID", "")).strip()})

    # 引擎结果
    vals, _ = aggregate_field_values(db, ds.id, report_date, MEICHONG_STORE)

    print(f"=== 对账 {report_date} ===")
    print(f"当日订单总数(含样品)        : {total_orders_today}")
    print(f"样品订单数(全局)            : {len(sample_ids)}")
    print(f"当日有效订单数(非样品)      : {indep_order_count}")
    print()
    rows_cmp = [
        ("实际支付金额", indep_actual_payment, vals.get("mc_actual_payment", 0)),
        ("实际订单数", indep_order_count, vals.get("mc_actual_order_count", 0)),
        ("应收金额", indep_receivable, vals.get("mc_receivable_amount", 0)),
    ]
    print(f"{'指标':<12}{'独立重算':>16}{'引擎':>16}{'差异':>12}")
    for name, indep, eng in rows_cmp:
        diff = indep - eng
        flag = "OK" if abs(diff) < 0.01 else "!! 不一致"
        print(f"{name:<12}{indep:>16,.2f}{eng:>16,.2f}{diff:>12,.4f}  {flag}")
    db.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2026-06-22")

"""日报输出：按「日报模板.xlsx」分组结构组织数值，并导出 Excel。"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.config import settings
from app.services.meichong_rules import TEMPLATE_GROUPS


def build_grouped(values: list) -> list[dict]:
    """把 ReportValue 列表按 TEMPLATE_GROUPS 分组，未归类的归到「其他」。"""
    by_label = {v.line_label: v for v in values}
    used: set[str] = set()
    groups: list[dict] = []
    for title, labels in TEMPLATE_GROUPS:
        metrics = []
        for label in labels:
            v = by_label.get(label)
            if v is not None:
                used.add(label)
                metrics.append({"label": label, "value": v.display_value, "expression": v.expression})
        if metrics:
            groups.append({"title": title, "metrics": metrics})
    others = [
        {"label": v.line_label, "value": v.display_value, "expression": v.expression}
        for v in values
        if v.line_label not in used
    ]
    if others:
        groups.append({"title": "其他", "metrics": others})
    return groups


def report_meta(data_source, run) -> dict:
    cfg = data_source.config or {}
    meta = dict(cfg.get("meta") or {})
    meta.setdefault("店铺名称", run.store_name)
    meta.setdefault("平台", data_source.platform)
    meta.setdefault("区域", "")
    meta.setdefault("项目", "")
    meta["日期"] = run.report_date
    return meta


_THIN = Side(style="thin", color="D1D5DB")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def export_daily_excel(data_source, run, values: list) -> Path:
    meta = report_meta(data_source, run)
    groups = build_grouped(values)

    wb = Workbook()
    ws = wb.active
    ws.title = "日报"

    title_fill = PatternFill("solid", fgColor="4338CA")
    group_fill = PatternFill("solid", fgColor="6366F1")
    meta_fill = PatternFill("solid", fgColor="EEF2FF")
    white_bold = Font(bold=True, color="FFFFFF")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # 标题
    ws.merge_cells("A1:F1")
    c = ws["A1"]
    c.value = f"美宠 TikTok 美国本土店日报 · {meta.get('日期','')}"
    c.font = Font(bold=True, size=14, color="FFFFFF")
    c.fill = title_fill
    c.alignment = center
    ws.row_dimensions[1].height = 26

    # 基本信息行
    meta_pairs = [("项目", meta.get("项目", "")), ("平台", meta.get("平台", "")),
                  ("区域", meta.get("区域", "")), ("店铺名称", meta.get("店铺名称", "")),
                  ("日期", meta.get("日期", ""))]
    row = 2
    col = 1
    for k, v in meta_pairs:
        kc = ws.cell(row=row, column=col, value=k)
        kc.fill = meta_fill
        kc.font = Font(bold=True)
        kc.border = _BORDER
        kc.alignment = center
        vc = ws.cell(row=row, column=col + 1, value=v)
        vc.border = _BORDER
        vc.alignment = center
        col += 2
        if col > 6:
            col = 1
            row += 1
    data_row_start = row + 2

    # 指标分组：每组一个分组标题行 + 指标名/数值两行（横向）
    r = data_row_start
    for g in groups:
        n = len(g["metrics"])
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=max(1, n))
        gc = ws.cell(row=r, column=1, value=g["title"])
        gc.fill = group_fill
        gc.font = white_bold
        gc.alignment = center
        gc.border = _BORDER
        for i, item in enumerate(g["metrics"], start=1):
            lc = ws.cell(row=r + 1, column=i, value=item["label"])
            lc.font = Font(bold=True, size=10)
            lc.fill = meta_fill
            lc.alignment = center
            lc.border = _BORDER
            vc = ws.cell(row=r + 2, column=i, value=item["value"])
            vc.alignment = center
            vc.border = _BORDER
        r += 4

    for col_idx in range(1, 7):
        ws.column_dimensions[get_column_letter(col_idx)].width = 18

    out_dir = Path(settings.upload_dir).parent / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"美宠日报_{meta.get('日期','')}_run{run.id}.xlsx"
    wb.save(out_path)
    return out_path

"""Quick verification for excel-order config and daily manual edit."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import urllib.parse
import urllib.request
BASE = "http://127.0.0.1:8081"


def fetch(path: str, *, method="GET", data: dict | None = None):
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body, method=method)
    return urllib.request.urlopen(req)


def main() -> int:
    # mappings page excel order
    html = fetch("/mappings").read().decode()
    cols = re.findall(
        r'id="report-field-\d+"[^>]*>.*?<td class="px-4 py-3 font-mono text-xs text-slate-500">([A-Z]+)</td>',
        html,
        flags=re.S,
    )
    if not cols:
        cols = re.findall(r'font-mono text-xs text-slate-500">([A-Z]+)</td>', html)
    print("mapping cols sample:", cols[:10])
    assert cols[:4] == ["F", "G", "H", "I"], f"expected F-G-H-I start, got {cols[:4]}"

    # generate report
    resp = fetch("/daily/generate", method="POST", data={"data_source_id": "1", "report_date": "2026-06-22"})
    final_url = resp.geturl()
    run_id = re.search(r"run_id=(\d+)", final_url)
    assert run_id, f"no run_id in {final_url}"
    rid = run_id.group(1)
    print("run_id", rid)

    daily_html = fetch(f"/daily?run_id={rid}").read().decode()
    assert "dailyEditor" in daily_html, "daily editor missing"
    assert "daily_editor.js" in daily_html, "daily_editor.js not loaded"
    assert daily_html.index(">F<") < daily_html.index(">V<"), "F should appear before V in excel order"

    # patch profit via API - find value id from page isn't easy; query via generate + db
    from app.database import SessionLocal
    from app.models import ReportValue

    db = SessionLocal()
    profit = (
        db.query(ReportValue)
        .filter(ReportValue.report_run_id == int(rid), ReportValue.line_label == "利润")
        .first()
    )
    assert profit, "profit row missing"
    print("profit value id", profit.id, "line_code", profit.line_code)

    import json

    req = urllib.request.Request(
        f"{BASE}/api/report-runs/{rid}/values/{profit.id}",
        data=json.dumps({"raw_value": 1234.56}).encode(),
        method="PATCH",
        headers={"Content-Type": "application/json"},
    )
    patch_resp = urllib.request.urlopen(req)
    patch_data = json.loads(patch_resp.read())
    print("patched", patch_data)
    assert patch_data["display_value"] == "$1,234.56"
    assert patch_data["raw_value"] == 1234.56

    db.close()
    db2 = SessionLocal()
    profit2 = db2.query(ReportValue).filter(ReportValue.id == profit.id).first()
    assert profit2.raw_value == 1234.56, f"db raw={profit2.raw_value}"
    db2.close()

    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""AutoReport 接口全量冒烟测试。"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8081"
DS_ID = 1
REPORT_DATE = "2026-06-20"


class Result:
    def __init__(self):
        self.passed: list[str] = []
        self.failed: list[str] = []

    def ok(self, name: str, detail: str = ""):
        self.passed.append(f"{name}" + (f" ({detail})" if detail else ""))

    def fail(self, name: str, detail: str):
        self.failed.append(f"{name}: {detail}")

    def summary(self) -> int:
        print("\n=== 通过 ===")
        for p in self.passed:
            print(f"  OK  {p}")
        if self.failed:
            print("\n=== 失败 ===")
            for f in self.failed:
                print(f"  FAIL {f}")
        print(f"\n合计: {len(self.passed)} 通过, {len(self.failed)} 失败")
        return 0 if not self.failed else 1


R = Result()


def req(method: str, path: str, *, data: dict | None = None, headers: dict | None = None, raw_body: bytes | None = None):
    url = BASE + path
    hdrs = dict(headers or {})
    body = raw_body
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req_obj = urllib.request.Request(url, data=body, method=method, headers=hdrs)
    try:
        resp = urllib.request.urlopen(req_obj, timeout=120)
        return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def get_json(path: str):
    status, _, body = req("GET", path, headers={"Accept": "application/json"})
    try:
        return status, json.loads(body.decode() or "{}")
    except Exception:
        return status, body[:200]


def test_pages():
    for path in ["/", "/mappings", "/daily", "/templates"]:
        status, _, body = req("GET", path)
        if status == 200 and b"<!DOCTYPE html>" in body:
            R.ok(f"GET {path}", f"{len(body)} bytes")
        else:
            R.fail(f"GET {path}", f"status={status}")


def test_schema_apis():
    status, data = get_json(f"/api/data-sources/{DS_ID}/schema")
    if status == 200 and data.get("files"):
        R.ok("schema files", f"{len(data['files'])} files")
    else:
        R.fail("schema files", str(data)[:120])

    status, data = get_json(f"/api/data-sources/{DS_ID}/schema?file={urllib.parse.quote('订单')}")
    if status == 200 and data.get("sheets"):
        R.ok("schema sheets", str(data["sheets"][:2]))
    else:
        R.fail("schema sheets", str(data)[:120])

    status, data = get_json(
        f"/api/data-sources/{DS_ID}/schema?file={urllib.parse.quote('订单')}&sheet=OrderSKUList"
    )
    if status == 200 and data.get("columns"):
        R.ok("schema columns", f"{len(data['columns'])} cols")
    else:
        R.fail("schema columns", str(data)[:120])


def test_mapped_fields():
    status, data = get_json(f"/api/data-sources/{DS_ID}/mapped-fields")
    if status == 200 and data.get("fields"):
        names = [f["name"] for f in data["fields"]]
        R.ok("mapped-fields", f"{len(names)} fields, first={names[0]}")
    else:
        R.fail("mapped-fields", str(data)[:120])


def test_settings():
    status, data = get_json(f"/api/data-sources/{DS_ID}/settings")
    if status == 200 and "order_file" in data:
        R.ok("settings GET")
    else:
        R.fail("settings GET", str(data)[:120])


def test_mapping_modes():
    # 刷单物流费用 id=18（per_order）；应收金额 id=2（fetch 有多条 parts）
    cases_by_id = [
        (26, "manual", {**{}, "line_type": "manual", "parts": []}),
        (18, "per_order", {"line_type": "per_order", "per_order_amount": 2.5, "per_order_basis": "valid_orders", "parts": []}),
        (26, "ratio", {"line_type": "ratio", "ratio_base_code": "mc_receivable_amount", "ratio_percent": 30, "parts": []}),
    ]
    for mapping_id, name, patch in cases_by_id:
        status, orig = get_json(f"/api/mappings/{mapping_id}")
        if status != 200:
            R.fail(f"mapping GET {mapping_id}", str(orig)[:120])
            continue

        def put(payload):
            status, _, body = req(
                "PUT",
                f"/api/mappings/{mapping_id}",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                raw_body=json.dumps(payload).encode(),
            )
            try:
                return status, json.loads(body.decode())
            except Exception:
                return status, body[:200]

        base = {
            "label": orig.get("label"),
            "report_group": orig.get("report_group"),
            "sort_order": orig.get("sort_order"),
            "line_type": patch.get("line_type", orig.get("line_type")),
            "per_order_amount": patch.get("per_order_amount", orig.get("per_order_amount")),
            "per_order_basis": patch.get("per_order_basis", orig.get("per_order_basis")),
            "ratio_percent": patch.get("ratio_percent", orig.get("ratio_percent")),
            "ratio_base_code": patch.get("ratio_base_code", orig.get("ratio_base_code")),
            "parts": patch.get("parts", orig.get("parts") or []),
        }
        status, data = put(base)
        if status == 200 and data.get("line_type") == patch["line_type"]:
            R.ok(f"mapping PUT {name}", f"id={mapping_id}")
        else:
            R.fail(f"mapping PUT {name}", f"status={status} body={str(data)[:120]}")

        # restore
        restore = {
            "label": orig.get("label"),
            "report_group": orig.get("report_group"),
            "sort_order": orig.get("sort_order"),
            "line_type": orig.get("line_type") or "fetch",
            "per_order_amount": orig.get("per_order_amount"),
            "per_order_basis": orig.get("per_order_basis"),
            "ratio_percent": orig.get("ratio_percent"),
            "ratio_base_code": orig.get("ratio_base_code"),
            "parts": orig.get("parts") or [],
        }
        put(restore)

    # fetch 类型用有 parts 的映射只读校验
    status, fetch_row = get_json("/api/mappings/2")
    if status == 200 and fetch_row.get("parts"):
        R.ok("mapping GET fetch", f"id=2 parts={len(fetch_row['parts'])}")
    else:
        R.fail("mapping GET fetch", str(fetch_row)[:120])


def test_more_apis():
    for path in [
        f"/api/data-sources/{DS_ID}/report-lines",
        f"/api/data-sources/{DS_ID}/catalog",
        f"/api/data-sources/{DS_ID}/config/export",
        f"/api/data-sources/{DS_ID}/review-orders/template",
        f"/api/data-sources/{DS_ID}/review-logistics/template",
        f"/api/data-sources/{DS_ID}/sample-orders/template",
    ]:
        status, _, body = req("GET", path)
        if status == 200 and len(body) > 50:
            R.ok(f"GET {path.split('/')[-1]}", f"{len(body)} bytes")
        else:
            R.fail(f"GET {path}", f"status={status} len={len(body)}")


def test_daily_generate():
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    data = urllib.parse.urlencode({"data_source_id": DS_ID, "report_date": REPORT_DATE}).encode()
    req_obj = urllib.request.Request(
        f"{BASE}/daily/generate",
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    try:
        resp = opener.open(req_obj, timeout=120)
        status = resp.status
        body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode()[:200]

    if status == 200 and body.get("run_id") and body.get("export_url"):
        R.ok("daily/generate JSON", f"run_id={body['run_id']}")
        run_id = body["run_id"]
        exp_status, _, exp_body = req("GET", f"/daily/{run_id}/export")
        if exp_status == 200 and len(exp_body) > 1000:
            R.ok("daily export", f"{len(exp_body)} bytes")
        else:
            R.fail("daily export", f"status={exp_status} len={len(exp_body)}")
    else:
        R.fail("daily/generate JSON", f"status={status} body={body}")


def test_export_sku():
    path = f"/daily/export-sku?data_source_id={DS_ID}&report_date={urllib.parse.quote(REPORT_DATE)}"
    status, _, body = req("GET", path)
    if status == 200 and len(body) > 1000:
        R.ok("export-sku", f"{len(body)} bytes")
    else:
        R.fail("export-sku", f"status={status} len={len(body)}")


def test_import_disabled():
    # 缺少 file 时 FastAPI 先返回 422；带空 file 才命中 410
    boundary = "----AutoReportTest"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="data_source_id"\r\n\r\n1\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="report_date"\r\n\r\n{REPORT_DATE}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="store_name"\r\n\r\nx\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="t.xlsx"\r\n'
        f"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n"
        f"\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    status, _, resp = req(
        "POST",
        "/api/import",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        raw_body=body,
    )
    if status == 410:
        R.ok("import disabled 410")
    else:
        R.fail("import disabled", f"status={status} body={resp[:120]!r}")


def main():
    print(f"Testing {BASE} ds={DS_ID} date={REPORT_DATE}")
    test_pages()
    test_schema_apis()
    test_mapped_fields()
    test_settings()
    test_mapping_modes()
    test_more_apis()
    test_daily_generate()
    test_export_sku()
    test_import_disabled()
    return R.summary()


if __name__ == "__main__":
    sys.exit(main())

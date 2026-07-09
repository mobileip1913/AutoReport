#!/usr/bin/env python3
"""Smoke + API regression for vue-php backend (default :8091)."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from io import BytesIO

BASE = os.environ.get("AUTOREPORT_BASE", "http://127.0.0.1:8091")
PASS = 0
FAIL = 0
WARN = 0


def ok(name: str, detail: str = "") -> None:
    global PASS
    PASS += 1
    print(f"  OK  {name}" + (f" — {detail}" if detail else ""))


def fail(name: str, detail: str = "") -> None:
    global FAIL
    FAIL += 1
    print(f" FAIL {name}" + (f" — {detail}" if detail else ""))


def warn(name: str, detail: str = "") -> None:
    global WARN
    WARN += 1
    print(f" WARN {name}" + (f" — {detail}" if detail else ""))


def req(method: str, path: str, *, data: bytes | None = None, headers: dict | None = None, accept: str | None = None):
    h = {"User-Agent": "AutoReport-PHP-Test/1.0"}
    if headers:
        h.update(headers)
    if accept:
        h["Accept"] = accept
    r = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            body = resp.read()
            return resp.status, dict(resp.headers), body
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def get_json(path: str):
    code, _, body = req("GET", path, headers={"Accept": "application/json"})
    try:
        return code, json.loads(body.decode("utf-8"))
    except Exception:
        return code, body.decode("utf-8", errors="replace")[:500]


def main() -> int:
    print("=== PHP Backend API/UI smoke @", BASE, "===\n")

    # --- Pages ---
    print("[Pages / SPA]")
    for path, markers in [
        ("/app/", ["AutoReport"]),
    ]:
        code, _, body = req("GET", path)
        text = body.decode("utf-8", errors="replace")
        if code != 200:
            fail(f"GET {path}", f"status={code}")
            continue
        missing = [m for m in markers if m not in text]
        if missing:
            fail(f"GET {path}", f"missing markers: {missing}")
        else:
            ok(f"GET {path}", f"len={len(body)}")

    # --- discover data source ---
    print("\n[Data source]")
    code, settings = get_json("/api/data-sources/1/settings")
    if code != 200 or not isinstance(settings, dict):
        fail("GET /api/data-sources/1/settings", f"status={code} body={settings!r}")
        ds_id = 1
    else:
        ok("GET /api/data-sources/1/settings", f"keys={list(settings.keys())[:6]}")
        ds_id = 1

    for ep in [
        f"/api/data-sources/{ds_id}/report-lines",
        f"/api/data-sources/{ds_id}/mapped-fields",
        f"/api/data-sources/{ds_id}/catalog",
        f"/api/data-sources/{ds_id}/schema",
    ]:
        code, data = get_json(ep)
        if code == 200:
            ok(f"GET {ep}")
        else:
            fail(f"GET {ep}", f"status={code} {data!r}")

    # --- template downloads ---
    print("\n[Templates]")
    for path, ctype_hint in [
        (f"/api/data-sources/{ds_id}/review-orders/template", "spreadsheet"),
        (f"/api/data-sources/{ds_id}/review-logistics/template", "spreadsheet"),
        (f"/api/data-sources/{ds_id}/sample-orders/template", "spreadsheet"),
        ("/daily/review-logistics-template?data_source_id=1", "spreadsheet"),
        ("/daily/sample-template?data_source_id=1", "spreadsheet"),
    ]:
        code, hdrs, body = req("GET", path)
        if code == 200 and len(body) > 100:
            ok(f"GET {path}", f"bytes={len(body)}")
        else:
            fail(f"GET {path}", f"status={code} len={len(body)}")

    # --- generate (JSON) ---
    print("\n[Generate]")
    from datetime import date, timedelta

    report_date = (date.today() - timedelta(days=1)).isoformat()
    store_name = "平衡贴美国本土店铺"
    payload = json.dumps(
        {"data_source_id": ds_id, "report_date": report_date, "store_name": store_name, "is_test": True}
    ).encode("utf-8")
    code, hdrs, body = req(
        "POST",
        "/api/generate",
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    run_id = None
    if code in (200, 201):
        try:
            data = json.loads(body.decode("utf-8"))
            run_id = data.get("id") or data.get("run_id")
            ok("POST /api/generate", f"run_id={run_id}")
        except Exception as e:
            fail("POST /api/generate", f"parse error: {e}")
    else:
        fail("POST /api/generate", f"status={code} {body[:300]!r}")

    # page generate with Accept JSON
    code, hdrs, body = req(
        "POST",
        "/daily/generate",
        data=urllib.parse.urlencode({"data_source_id": ds_id, "report_date": report_date}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    if code in (200, 201):
        try:
            data = json.loads(body.decode("utf-8"))
            ok("POST /daily/generate (JSON)", f"keys={list(data.keys())}")
        except Exception:
            ok("POST /daily/generate (JSON)", f"status={code}")
    else:
        fail("POST /daily/generate (JSON)", f"status={code} {body[:300]!r}")

    if run_id:
        code, data = get_json(f"/api/daily/bootstrap?run_id={run_id}")
        if code == 200 and isinstance(data, dict) and data.get("run"):
            ok(f"GET /api/daily/bootstrap?run_id={run_id}", f"run={data['run'].get('id')}")
        else:
            fail(f"GET /api/daily/bootstrap?run_id={run_id}", f"status={code}")

    print("\n[Bootstrap API]")
    for path in (
        "/api/session",
        "/api/dashboard/bootstrap",
        "/api/mappings/bootstrap",
        "/api/daily/bootstrap",
    ):
        code, data = get_json(path)
        if code == 200 and isinstance(data, dict):
            ok(f"GET {path}", f"keys={len(data)}")
        else:
            fail(f"GET {path}", f"status={code} {data!r}")

    print("\n[SPA]")
    code, _, body = req("GET", "/app/")
    if code == 200 and (b"<!doctype html" in body.lower() or b"<html" in body.lower()):
        ok("GET /app/", f"len={len(body)}")
    elif code == 503:
        warn("GET /app/", "Vue 未 build（生产前需 npm run build）")
    else:
        fail("GET /app/", f"status={code} len={len(body)}")

    print(f"\n=== API summary: {PASS} passed, {FAIL} failed, {WARN} warnings ===")
    return 1 if FAIL else 0


if __name__ == "__main__":
    import urllib.parse  # noqa: E402

    sys.exit(main())

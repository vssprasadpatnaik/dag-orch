"""consumer - SLA Command Center (Daily Guard view) + its BFF.

A *consumer* of the `mf-sla v1` API, not a Beacon service. The BFF aggregates
the core's endpoints into one round-trip per refresh; the page renders the
trains/lanes view and offers the SRE "Move to Fast Lane" action (which it
forwards to beacon-control).
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import config
from common import httpkit
from .page import PAGE_HTML


def _daily_guard_rows():
    funcs = httpkit.get_json(config.CORE() + "/mf-sla/v1/functions")["items"]
    rows = []
    for f in funcs:
        fid = f["function_id"]
        run_id = f.get("latest_run_id")
        snap = httpkit.get_json(
            config.CORE() + "/mf-sla/v1/predictions?function_id={0}&run_id={1}".format(fid, run_id))
        rows.append({
            "function_id": fid,
            "display_name": snap.get("display_name", fid),
            "owner": snap.get("owner"),
            "state": snap.get("state"),
            "predicted_finish_p50": snap.get("predicted_finish_p50"),
            "predicted_finish_p90": snap.get("predicted_finish_p90"),
            "sla_deadline": snap.get("sla_deadline"),
            "sla_deadline_local": snap.get("sla_deadline_local"),
            "sla_status": snap.get("sla_status"),
            "confidence": snap.get("confidence"),
            "lane": snap.get("lane", "normal"),
            "fast_lane_eligible": snap.get("fast_lane_eligible", False),
            "compute_index": snap.get("compute_index"),
            "factors": snap.get("factors", []),
            "fast_lane": snap.get("fast_lane", {}),
            "run_id": run_id,
        })
    return rows


class _RH(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: N802
        return

    def _json(self, status, payload):
        data = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _html(self, html):
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            return self._html(PAGE_HTML)
        if path == "/health":
            return self._json(200, {"service": "consumer-portal", "status": "ok"})
        if path == "/api/daily-guard":
            return self._json(200, {"items": _daily_guard_rows()})
        if path == "/api/audit":
            return self._json(200, httpkit.get_json(config.CONTROL() + "/audit"))
        return self._json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        if path == "/api/fast-lane":
            try:
                res = httpkit.post_json(config.CONTROL() + "/fast-lane/assignments", body)
                return self._json(200, res)
            except Exception as exc:
                return self._json(409, {"ok": False, "error": str(exc)})
        return self._json(404, {"error": "not found"})


def main():
    port = config.PORTS["consumer-portal"]
    server = ThreadingHTTPServer(("127.0.0.1", port), _RH)
    print("[consumer-portal] listening on http://127.0.0.1:{0}".format(port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

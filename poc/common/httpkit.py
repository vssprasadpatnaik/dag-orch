"""Tiny stdlib JSON HTTP server + client so the POC needs zero dependencies.

A "service" is just a routing table:  {"GET /path": handler, ...}
where ``handler(query, body) -> (status_code, dict)``.
``query`` is a flat dict of query-string params; ``body`` is the parsed JSON body.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Tuple
from urllib.parse import urlparse, parse_qs


Handler = Callable[[Dict[str, Any], Dict[str, Any]], Tuple[int, Any]]


def _flatten_query(raw: Dict[str, list]) -> Dict[str, str]:
    return {k: (v[0] if v else "") for k, v in raw.items()}


def make_server(name: str, port: int, routes: Dict[str, Handler]) -> ThreadingHTTPServer:
    class _RH(BaseHTTPRequestHandler):
        # Quiet logs - the runner prints its own narration.
        def log_message(self, fmt, *args):  # noqa: N802
            return

        def _dispatch(self, method: str):
            parsed = urlparse(self.path)
            key = "{0} {1}".format(method, parsed.path)
            query = _flatten_query(parse_qs(parsed.query))
            body: Dict[str, Any] = {}
            if method == "POST":
                length = int(self.headers.get("Content-Length", 0) or 0)
                if length:
                    try:
                        body = json.loads(self.rfile.read(length).decode("utf-8"))
                    except Exception:
                        body = {}

            if key == "GET /health":
                return self._send(200, {"service": name, "status": "ok"})

            handler = routes.get(key)
            if handler is None:
                return self._send(404, {"error": "no route", "path": key})
            try:
                status, payload = handler(query, body)
            except Exception as exc:  # surface errors as JSON for the demo
                return self._send(500, {"error": str(exc), "route": key})
            return self._send(status, payload)

        def _send(self, status: int, payload: Any):
            data = json.dumps(payload, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802
            self._dispatch("GET")

        def do_POST(self):  # noqa: N802
            self._dispatch("POST")

    return ThreadingHTTPServer(("127.0.0.1", port), _RH)


def run_service(name: str, port: int, routes: Dict[str, Handler]) -> None:
    server = make_server(name, port, routes)
    print("[{0}] listening on http://127.0.0.1:{1}".format(name, port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


# ---- client helpers ----

def get_json(url: str, timeout: float = 10.0) -> Any:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_json(url: str, body: Any, timeout: float = 10.0) -> Any:
    data = json.dumps(body, default=str).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

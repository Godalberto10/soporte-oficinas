"""Local web server (standard library only): the React page and a small JSON API.

Start: uv run office-support-web   (opens http://127.0.0.1:8000)
Thin layer like app.py: every decision is made by orchestrate(); web.py turns
runs into JSON. It only listens on 127.0.0.1 and never uses a token.

API
  GET  /api/meta                  offices, examples, network status, agents, rules
  POST /api/runs                  {"incident", "office", "ticket", "model"} → {"id"}
  GET  /api/runs/<id>?since=N     new steps since N, pending question, result
  POST /api/runs/<id>/answer      {"yes": true|false} → answer to the question (R1)
"""

import argparse
import json
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from office_support.interfaces import web

STATIC = Path(__file__).resolve().parent / "static"
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}
MAX_RUNS = 50
MAX_BODY = 10_000


class Runs:
    """The runs in memory, by id (the oldest are forgotten after MAX_RUNS)."""

    def __init__(self) -> None:
        self._runs: dict[str, web.Execution] = {}
        self._lock = threading.Lock()

    def start(self, data: dict) -> str:
        incident = str(data.get("incident", "")).strip()
        if not incident:
            raise ValueError("the incident is empty")
        execution = web.Execution(incident, str(data.get("office", "")),
                                  str(data.get("ticket") or ""),
                                  web.create_model(str(data.get("model") or web.SIMULATED)))
        run_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._runs[run_id] = execution
            while len(self._runs) > MAX_RUNS:
                self._runs.pop(next(iter(self._runs)))
        return run_id

    def get(self, run_id: str) -> web.Execution | None:
        return self._runs.get(run_id)


def make_handler(runs: Runs) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:  # quiet terminal
            pass

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data: object, status: int = 200) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _body(self) -> dict:
            length = min(int(self.headers.get("Content-Length") or 0), MAX_BODY)
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("a JSON object was expected")
            return data

        def _static(self, name: str) -> None:
            path = (STATIC / name).resolve()
            if STATIC not in path.parents or not path.is_file():
                return self._json({"error": "not found"}, 404)
            self._send(200, path.read_bytes(),
                       CONTENT_TYPES.get(path.suffix, "application/octet-stream"))

        def do_GET(self) -> None:
            url = urlparse(self.path)
            parts = url.path.strip("/").split("/")
            if url.path == "/":
                return self._static("index.html")
            if parts[0] == "static" and len(parts) == 2:
                return self._static(parts[1])
            if url.path == "/api/meta":
                return self._json(web.meta())
            if parts[:2] == ["api", "runs"] and len(parts) == 3:
                execution = runs.get(parts[2])
                if execution is None:
                    return self._json({"error": "unknown run"}, 404)
                since = int(parse_qs(url.query).get("since", ["0"])[0] or 0)
                return self._json(execution.snapshot(max(since, 0)))
            self._json({"error": "not found"}, 404)

        def do_POST(self) -> None:
            parts = urlparse(self.path).path.strip("/").split("/")
            try:
                data = self._body()
                if parts == ["api", "runs"]:
                    return self._json({"id": runs.start(data)}, 201)
                if parts[:2] == ["api", "runs"] and len(parts) == 4 and parts[3] == "answer":
                    execution = runs.get(parts[2])
                    if execution is None:
                        return self._json({"error": "unknown run"}, 404)
                    execution.respond(data.get("yes") is True)
                    return self._json({"ok": True})
            except (ValueError, json.JSONDecodeError) as error:
                return self._json({"error": str(error)}, 400)
            self._json({"error": "not found"}, 404)

    return Handler


def create_server(port: int = 8000) -> ThreadingHTTPServer:
    """Server bound to 127.0.0.1 (port 0 = any free port, used by the tests)."""
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(Runs()))
    server.daemon_threads = True
    return server


def main(argv: list[str] | None = None) -> int:
    """Entry point of the office-support-web command."""
    parser = argparse.ArgumentParser(prog="office-support-web",
                                     description="Web console of the office support agents.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    args = parser.parse_args(argv)
    server = create_server(args.port)
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"Office support web console on {url} (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0

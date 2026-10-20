"""The local web server (office-support-web): real HTTP on a free port, simulated model."""

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from office_support.interfaces import server, web


@pytest.fixture(scope="module")
def base_url():
    srv = server.create_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(autouse=True)
def no_ollama(monkeypatch):
    monkeypatch.setattr(web, "ollama_models", lambda *a, **k: [])


def call(base: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(base + path, data=data,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def wait_for(base: str, run_id: str, until) -> dict:
    deadline = time.time() + 10
    while time.time() < deadline:
        _, snap = call(base, f"/api/runs/{run_id}")
        if until(snap):
            return snap
        time.sleep(0.05)
    raise AssertionError("the run did not reach the expected state")


def test_page_and_static_files(base_url):
    with urllib.request.urlopen(base_url + "/", timeout=10) as response:
        page = response.read().decode()
    assert "Office Support Console" in page and "/static/app.js" in page
    with urllib.request.urlopen(base_url + "/static/app.js", timeout=10) as response:
        assert "text/javascript" in response.headers["Content-Type"]


def test_static_files_cannot_leave_the_folder(base_url):
    assert call(base_url, "/static/..%2F..%2F..%2F.env")[0] == 404
    assert call(base_url, "/static/server.py")[0] == 404


def test_meta(base_url):
    status, meta = call(base_url, "/api/meta")
    assert status == 200
    assert [a["name"] for a in meta["agents"]] == ["classifier", "diagnosis", "knowledge",
                                                   "escalation"]
    assert meta["services"]["MAD-01"]["vpn"] == "down"
    assert meta["models"] == ["simulated"] and set(meta["rules"]) == {"R1", "R2", "R3", "R4", "R5"}


def test_run_asks_and_confirming_resolves_r1(base_url):
    _, created = call(base_url, "/api/runs", {"incident": "I have no internet",
                                              "office": "MAD-01", "ticket": "T-0001"})
    snap = wait_for(base_url, created["id"], lambda s: s["pending"])
    assert snap["pending"]["text"] == "restart_service(service=vpn, office=MAD-01)"
    assert not any(s["tool"] == "restart_service" for s in snap["steps"])
    assert call(base_url, f"/api/runs/{created['id']}/answer", {"yes": True})[0] == 200
    done = wait_for(base_url, created["id"], lambda s: s["done"])
    assert done["result"]["final"] == "resolved" and done["result"]["priority"] == "P1"


def test_rejecting_escalates_and_since_returns_only_new_steps(base_url):
    _, created = call(base_url, "/api/runs", {"incident": "I have no internet",
                                              "office": "MAD-01"})
    asked = wait_for(base_url, created["id"], lambda s: s["pending"])
    call(base_url, f"/api/runs/{created['id']}/answer", {"yes": False})
    done = wait_for(base_url, created["id"], lambda s: s["done"])
    assert done["result"]["final"] == "escalated"
    _, later = call(base_url, f"/api/runs/{created['id']}?since={asked['total']}")
    assert later["steps"] and later["steps"][0]["n"] == asked["total"] + 1
    assert any(s["rule"] == "R1" for s in later["steps"])


@pytest.mark.parametrize("path, body", [
    ("/api/runs", {"incident": "  ", "office": "MAD-01"}),
    ("/api/runs", ["not", "an", "object"]),
])
def test_bad_requests(base_url, path, body):
    assert call(base_url, path, body)[0] == 400


def test_unknown_run_and_route(base_url):
    assert call(base_url, "/api/runs/nope")[0] == 404
    assert call(base_url, "/api/runs/nope/answer", {"yes": True})[0] == 404
    assert call(base_url, "/api/other")[0] == 404

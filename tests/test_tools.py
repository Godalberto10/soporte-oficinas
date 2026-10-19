"""Tests of the tools, their registry and execute()."""

import hashlib
import shutil
from pathlib import Path

import pytest

from office_support.retrieval import BM25Index
from office_support.tools import (
    DATA_PATH,
    Network,
    Tool,
    ToolError,
    create_tools,
    execute,
)

NAMES = {
    "check_service", "check_device", "search_tickets",
    "create_escalation", "restart_service", "close_ticket", "search_docs",
}
IRREVERSIBLE = {"restart_service", "close_ticket"}


@pytest.fixture
def network(tmp_path: Path) -> Network:
    for file in DATA_PATH.glob("*.json"):
        shutil.copy(file, tmp_path)
    return Network.from_directory(tmp_path)


@pytest.fixture
def t(network: Network) -> dict[str, Tool]:
    return create_tools(network)


# --- Criteria 3 and 4: registry --------------------------------------------

def test_complete_registry_and_reversibility(t):
    assert set(t) == NAMES
    for name, tool in t.items():
        assert isinstance(tool, Tool)
        assert tool.name == name
        assert tool.description.strip()
        assert tool.reversible == (name not in IRREVERSIBLE)


def test_search_docs(t):
    output = execute(t, "search_docs", {"query": "vpn down"})
    assert set(output) == {"fragments"}
    assert 0 < len(output["fragments"]) <= 3
    for fragment in output["fragments"]:
        assert {"doc", "section", "text"} <= set(fragment)
    assert output["fragments"][0]["doc"] == "docs/kb-network-01.md"


def test_search_docs_with_k(t):
    output = execute(t, "search_docs", {"query": "service", "k": 5})
    assert len(output["fragments"]) == 5


def test_search_docs_injected_index(network):
    index = BM25Index([{"doc": "docs/x.md", "section": "S", "text": "vpn", "title": "X"}])
    t = create_tools(network, index)
    assert execute(t, "search_docs", {"query": "vpn"})["fragments"][0]["doc"] == "docs/x.md"


# --- Criterion 5: results ----------------------------------------------------

def test_check_service(t):
    assert execute(t, "check_service", {"service": "vpn", "office": "MAD-01"}) == {
        "service": "vpn", "office": "MAD-01", "status": "down",
    }


def test_check_device(t):
    record = execute(t, "check_device", {"device_id": "PC-VAL01-002"})
    assert record["office"] == "VAL-01"
    assert record["status"] == "faulty_network_card"


def test_search_tickets_filters(t):
    everything = execute(t, "search_tickets", {})["tickets"]
    assert len(everything) == 10
    mad = execute(t, "search_tickets", {"office": "MAD-01"})["tickets"]
    assert {ticket["id"] for ticket in mad} == {"T-0001", "T-0009"}
    internet = execute(t, "search_tickets", {"symptom": "I HAVE NO INTERNET"})["tickets"]
    assert {ticket["id"] for ticket in internet} == {"T-0001", "T-0002"}
    both = execute(t, "search_tickets", {"office": "VAL-01", "symptom": "internet"})
    assert [ticket["id"] for ticket in both["tickets"]] == ["T-0002"]


def test_create_escalation_increasing_ids(t, network):
    first = execute(t, "create_escalation",
                    {"ticket": "T-0007", "summary": "printing down", "priority": "P2"})
    second = execute(t, "create_escalation",
                     {"ticket": None, "summary": "erp in two offices", "priority": "P1"})
    assert first["escalation"] == "ESC-0001"
    assert second["escalation"] == "ESC-0002"
    assert len(network.escalations) == 2


def test_restart_service_leaves_ok(t):
    output = execute(t, "restart_service", {"service": "vpn", "office": "MAD-01"})
    assert output["previous_status"] == "down"
    assert execute(t, "check_service",
                   {"service": "vpn", "office": "MAD-01"})["status"] == "ok"


def test_close_ticket(t, network):
    execute(t, "close_ticket", {"ticket": "T-0001", "resolution": "VPN restarted"})
    ticket = network.ticket("T-0001")
    assert ticket["status"] == "closed"
    assert ticket["resolution"] == "VPN restarted"


# --- Criterion 6: tool errors ------------------------------------------------

@pytest.mark.parametrize("name, arguments", [
    ("check_service", {"service": "vpn", "office": "SEV-01"}),
    ("check_service", {"service": "telephony", "office": "MAD-01"}),
    ("check_service", {"service": ["vpn"], "office": "MAD-01"}),
    ("check_device", {"device_id": "PC-XXX-999"}),
    ("search_tickets", {"office": "SEV-01"}),
    ("create_escalation", {"ticket": "T-9999", "summary": "x", "priority": "P1"}),
    ("create_escalation", {"ticket": "T-0001", "summary": "x", "priority": "P5"}),
    ("create_escalation", {"ticket": "T-0001", "summary": "  ", "priority": "P1"}),
    ("restart_service", {"service": "vpn", "office": "SEV-01"}),
    ("close_ticket", {"ticket": "T-0001", "resolution": ""}),
    ("close_ticket", {"ticket": "T-0003", "resolution": "it was already closed"}),
    ("close_ticket", {"ticket": "T-9999", "resolution": "x"}),
    ("search_docs", {"query": ""}),
    ("search_docs", {"query": 42}),
    ("search_docs", {"query": "vpn", "k": 0}),
    ("search_docs", {"query": "vpn", "k": 11}),
    ("search_docs", {"query": "vpn", "k": "3"}),
    ("search_docs", {"query": "vpn", "k": True}),
])
def test_tool_errors(t, name, arguments):
    with pytest.raises(ToolError) as error:
        execute(t, name, arguments)
    assert str(error.value)


def test_error_does_not_modify_state(t, network):
    with pytest.raises(ToolError):
        execute(t, "close_ticket", {"ticket": "T-0001", "resolution": ""})
    assert network.ticket("T-0001")["status"] == "open"


# --- Criterion 7: execute() ----------------------------------------------------

@pytest.mark.parametrize("name, arguments", [
    ("delete_everything", {}),
    ("check_service", {"service": "vpn", "office": "MAD-01", "extra": 1}),
    ("check_service", {"service": "vpn"}),
    ("check_service", {"network": None, "service": "vpn", "office": "MAD-01"}),
    ("check_service", ["vpn", "MAD-01"]),
])
def test_execute_converts_usage_failures(t, name, arguments):
    with pytest.raises(ToolError):
        execute(t, name, arguments)


def test_execute_does_not_hide_internal_failures(network):
    def broken(service: str) -> dict:
        raise TypeError("programming error")

    t = {"broken": Tool("broken", "fails", True, broken)}
    with pytest.raises(TypeError):
        execute(t, "broken", {"service": "vpn"})


# --- Criterion 8: isolation ------------------------------------------------------

def test_independent_networks():
    a, b = Network.from_directory(), Network.from_directory()
    execute(create_tools(a), "restart_service",
            {"service": "vpn", "office": "MAD-01"})
    assert a.services["MAD-01"]["vpn"] == "ok"
    assert b.services["MAD-01"]["vpn"] == "down"


def _fingerprints(directory: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.glob("*.json"))}


def test_irreversible_do_not_write_the_json():
    before = _fingerprints(DATA_PATH)
    t = create_tools(Network.from_directory())
    execute(t, "restart_service", {"service": "erp", "office": "MAD-02"})
    execute(t, "close_ticket", {"ticket": "T-0007", "resolution": "test"})
    execute(t, "create_escalation", {"ticket": None, "summary": "test", "priority": "P1"})
    assert _fingerprints(DATA_PATH) == before

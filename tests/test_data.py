"""Tests of milestone 1: simulated data (data/) and knowledge base (docs/)."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"

OFFICES = {"MAD-01", "MAD-02", "BCN-01", "VAL-01"}
CRITICAL = {"vpn", "email", "erp", "files", "intranet"}
NON_CRITICAL = {"printing", "guest_wifi"}
SERVICE_STATUSES = {"ok", "degraded", "down"}
KB_TYPES = {"network", "printer", "app_access", "email", "hardware"}
POLICIES = [
    "service-catalog.md",
    "escalation-procedure.md",
    "restart-policy.md",
    "priority-guide.md",
]


def _load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def services() -> dict:
    return _load("services.json")


@pytest.fixture(scope="module")
def inventory() -> list:
    return _load("inventory.json")


@pytest.fixture(scope="module")
def tickets() -> list:
    return _load("tickets.json")


def _kb_articles() -> list[Path]:
    return sorted(DOCS.glob("kb-*.md"))


# --- Criteria 1 and 2: services.json -------------------------------------------

def test_services_has_offices_and_services(services):
    assert set(services) == OFFICES
    for office, statuses in services.items():
        assert set(statuses) == CRITICAL | NON_CRITICAL, office
        assert set(statuses.values()) <= SERVICE_STATUSES, office


def test_critical_multi_office_outage(services):
    multi_office = [
        s for s in CRITICAL
        if sum(services[o][s] == "down" for o in OFFICES) >= 2
    ]
    assert multi_office, "no critical service down in 2+ offices"


def test_some_service_is_degraded(services):
    values = [v for statuses in services.values() for v in statuses.values()]
    assert "degraded" in values


# --- Criterion 3: inventory.json -------------------------------------------------

def test_inventory(inventory, services):
    assert len(inventory) >= 12
    ids = [d["id"] for d in inventory]
    assert len(ids) == len(set(ids)), "repeated device ids"
    for device in inventory:
        assert set(device) == {"id", "type", "office", "model", "status"}
        assert all(isinstance(v, str) and v for v in device.values())
        assert device["office"] in services


# --- Criterion 4: tickets.json ----------------------------------------------------

def test_tickets_format(tickets, services):
    assert len(tickets) >= 8
    for t in tickets:
        assert set(t) == {"id", "office", "symptom", "status", "reopenings"}
        assert re.fullmatch(r"T-\d{4}", t["id"])
        assert t["office"] in services
        assert t["status"] in {"open", "closed", "reopened"}
        assert isinstance(t["reopenings"], int) and t["reopenings"] >= 0
    ids = [t["id"] for t in tickets]
    assert len(ids) == len(set(ids))


def test_reopened_ticket(tickets):
    assert any(t["reopenings"] >= 1 for t in tickets)


def _cause_is_service(services: dict, office: str) -> bool:
    return any(services[office][s] != "ok" for s in CRITICAL)


def _cause_is_device(services, inventory, office: str) -> bool:
    critical_ok = not _cause_is_service(services, office)
    faulty = any(
        d["office"] == office and d["status"] != "operational" for d in inventory
    )
    return critical_ok and faulty


def test_same_symptom_different_causes(tickets, services, inventory):
    """Same symptom: in one office a critical service fails, in another a device."""
    pairs = [
        (a["id"], b["id"])
        for a in tickets for b in tickets
        if a["symptom"] == b["symptom"] and a["office"] != b["office"]
        and _cause_is_service(services, a["office"])
        and _cause_is_device(services, inventory, b["office"])
    ]
    assert pairs


# --- Criterion 5: kb articles -----------------------------------------------------

def test_eight_or_more_articles_and_twelve_docs():
    assert len(_kb_articles()) >= 8
    assert len(list(DOCS.glob("*.md"))) >= 12
    for name in POLICIES:
        assert (DOCS / name).is_file(), name


@pytest.mark.parametrize("path", _kb_articles(), ids=lambda p: p.name)
def test_kb_article_sections(path: Path):
    assert re.fullmatch(r"kb-[a-z_]+-\d{2}\.md", path.name)
    text = path.read_text(encoding="utf-8")
    sections = re.findall(r"^## (.+?)\s*$", text, flags=re.MULTILINE)
    assert sections == ["Symptoms", "Cause", "Steps"]


def test_articles_cover_the_five_types():
    types = {re.match(r"kb-(.+)-\d{2}\.md", p.name).group(1) for p in _kb_articles()}
    assert KB_TYPES <= types
    assert types <= KB_TYPES | {"other"}


# --- Criterion 6: consistency of the policies with CLAUDE.md ----------------------

def _claude_text() -> str:
    return (ROOT / "CLAUDE.md").read_text(encoding="utf-8")


def _backtick_list(line: str) -> set[str]:
    return set(re.findall(r"`([a-z_]+)`", line))


def test_critical_services_of_claude_md_match():
    line = re.search(r"^- Critical: (.+)$", _claude_text(), re.MULTILINE).group(1)
    assert _backtick_list(line) == CRITICAL


def _claude_priority_rules() -> list[str]:
    return re.findall(r"^- \*\*P[1-4]\*\*: .+$", _claude_text(), re.MULTILINE)


@pytest.mark.parametrize("name", POLICIES)
def test_policy_critical_services_and_hours(name: str):
    text = (DOCS / name).read_text(encoding="utf-8")
    line = re.search(r"\*\*Critical services:\*\* (.+)", text).group(1)
    assert _backtick_list(line) == CRITICAL
    assert "Monday to Friday, 08:00 to 18:00" in text


@pytest.mark.parametrize(
    "name", ["priority-guide.md", "escalation-procedure.md"]
)
def test_policy_same_priority_rules(name: str):
    rules = _claude_priority_rules()
    assert len(rules) == 4
    text = (DOCS / name).read_text(encoding="utf-8")
    for rule in rules:
        assert rule.strip() in text, rule


def test_catalog_times_by_priority():
    text = (DOCS / "service-catalog.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (P[1-4]) \|", text, flags=re.MULTILINE)
    assert rows == ["P1", "P2", "P3", "P4"]


def test_restart_policy_guardrail_rules():
    text = (DOCS / "restart-policy.md").read_text(encoding="utf-8")
    assert "irreversible" in text
    assert "`down` or `degraded`" in text
    assert "one restart per service" in text


# --- Criterion 7: no personal data ------------------------------------------------

PERSONAL_PATTERNS = {
    "email": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "phone": r"(?<!\d)[679]\d{2}[ ]?\d{3}[ ]?\d{3}(?!\d)",
    "national_id": r"(?<!\w)\d{8}[A-Z](?!\w)",
}


def _content_files() -> list[Path]:
    return sorted(DATA.glob("*.json")) + sorted(DOCS.glob("*.md"))


@pytest.mark.parametrize("path", _content_files(), ids=lambda p: p.name)
def test_no_personal_data(path: Path):
    text = path.read_text(encoding="utf-8")
    for name, pattern in PERSONAL_PATTERNS.items():
        assert not re.search(pattern, text), f"{name} in {path.name}"

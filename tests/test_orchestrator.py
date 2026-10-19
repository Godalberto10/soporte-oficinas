"""Orchestrator tests: handoff, hard cases and rules R1–R5."""

import json
from datetime import datetime

import pytest

from office_support.model import ScriptedModel
from office_support.orchestrator import (
    guardrail,
    in_business_hours,
    minimum_priority,
    orchestrate,
    trajectory,
)
from office_support.state import Action, State, Step
from office_support.tools import Network

MONDAY_10 = datetime(2026, 10, 12, 10, 0)
SATURDAY_10 = datetime(2026, 10, 17, 10, 0)
VPN_CITATION = "docs/kb-network-01.md#Steps"


def j(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def call(tool: str, **arguments) -> str:
    return j({"tool": tool, "arguments": arguments})


def classification(type_: str = "network", priority: str = "P1") -> str:
    return j({"type": type_, "priority": priority, "reason": "according to the data"})


def diagnosis(service: str | None, office: str = "MAD-01") -> list[str]:
    query = (call("check_service", service=service, office=office)
             if service else call("check_device", device_id="PC-VAL01-002"))
    return [query, j({"cause": f"failure of {service or 'device'}", "service": service,
                      "evidence": ["observed in the tool"]})]


def knowledge(action: dict | None = None, citations: list[str] | None = None,
              query: str = "steps vpn down") -> list[str]:
    return [call("search_docs", query=query, k=5),
            j({"procedure": "Follow the steps of the article.",
               "citations": [VPN_CITATION] if citations is None else citations,
               "action": action})]


def restart(service: str = "vpn", office: str = "MAD-01") -> dict:
    return {"tool": "restart_service",
            "arguments": {"service": service, "office": office}}


def escalation(priority: str = "P1") -> list[str]:
    return [j({"summary": "not resolved at first level", "tried": ["diagnosis"],
               "priority": priority})]


class Confirm:
    """Injectable confirm() that remembers the actions it is asked about."""

    def __init__(self, answer: bool | None) -> None:
        self.answer = answer
        self.questions: list[Action] = []

    def __call__(self, action: Action) -> bool:
        if self.answer is None:
            raise AssertionError(f"it should not have asked: {action}")
        self.questions.append(action)
        return self.answer


@pytest.fixture
def network() -> Network:
    return Network.from_directory()


def run(script: list[str], network: Network, confirm=None, office: str = "MAD-01",
        ticket: str | None = None, now: datetime = MONDAY_10,
        incident: str = "I have no internet", **options):
    model = ScriptedModel(script)
    result = orchestrate(incident, office, model, confirm or Confirm(None),
                         now=lambda: now, ticket=ticket, network=network, **options)
    return result, model


def executed(result, tool: str) -> list[Step]:
    return [s for s in result.trace if s.tool == tool]


def notes(result) -> str:
    return " | ".join(str(s.observation) for s in result.trace if s.agent == "orchestrator")


# --- Criterion 1: resolved with a confirmed restart ----------------------------

def test_resolved_with_restart(network):
    confirm = Confirm(True)
    script = [classification(), *diagnosis("vpn"), *knowledge(restart())]
    result, _ = run(script, network, confirm)
    assert result.final == "resolved"
    assert (result.type, result.priority) == ("network", "P1")
    assert trajectory(result.trace) == ["classifier", "diagnosis", "knowledge"]
    assert network.services["MAD-01"]["vpn"] == "ok"
    assert len(executed(result, "restart_service")) == 1
    assert confirm.questions == [Action("restart_service",
                                        {"service": "vpn", "office": "MAD-01"})]
    assert VPN_CITATION in result.answer and result.citations == [VPN_CITATION]
    assert result.escalation is None


# --- Criterion 2 / R1: confirmation rejected ----------------------------------

def test_r1_rejection_does_not_execute_and_escalates(network):
    script = [classification(), *diagnosis("vpn"), *knowledge(restart()), *escalation()]
    result, model = run(script, network, Confirm(False))
    assert network.services["MAD-01"]["vpn"] == "down"
    assert executed(result, "restart_service") == []
    assert executed(result, "close_ticket") == []
    assert trajectory(result.trace)[-1] == "escalation"
    assert result.final == "escalated" and result.final != "rejected"
    assert result.escalation == "ESC-0001"
    assert "rejected by the user" in notes(result)
    # the escalation agent learns about the rejection
    assert "rejected by the user" in model.calls[-1]["messages"][0]["content"]


def test_r1_close_ticket_also_requires_confirmation(network):
    action = {"tool": "close_ticket",
              "arguments": {"ticket": "T-0001", "resolution": "VPN restored"}}
    script = [classification(), *diagnosis("vpn"), *knowledge(action), *escalation()]
    result, _ = run(script, network, Confirm(False), ticket="T-0001")
    assert network.ticket("T-0001")["status"] == "open"
    assert executed(result, "close_ticket") == []
    assert result.final == "escalated"


# --- Criterion 3 / R2: guardrail ---------------------------------------------

@pytest.mark.parametrize("diagnosed, action, reason", [
    ("vpn", restart("erp"), "diagnosed service"),
    ("email", restart("email"), "is ok"),
    ("vpn", restart("vpn", "MAD-02"), "office"),
])
def test_r2_blocks_without_asking(network, diagnosed, action, reason):
    script = [classification(), *diagnosis(diagnosed), *knowledge(action), *escalation()]
    result, _ = run(script, network, Confirm(None))  # fails if it asks
    assert result.final == "escalated"
    assert executed(result, "restart_service") == []
    assert "guardrail" in notes(result) and reason in notes(result)
    assert network.services["MAD-01"]["erp"] == "ok"


def test_r2_outside_business_hours_it_asks(network):
    confirm = Confirm(False)
    script = [classification(), *diagnosis("vpn"), *knowledge(restart("erp")), *escalation()]
    run(script, network, confirm, now=SATURDAY_10)
    assert confirm.questions == [Action("restart_service",
                                        {"service": "erp", "office": "MAD-01"})]


def test_r2_non_critical_in_business_hours_it_asks(network):
    confirm = Confirm(True)
    script = [classification("printer", "P4"), *diagnosis("printing", "MAD-02"),
              *knowledge(restart("printing", "MAD-02"),
                         citations=["docs/kb-printer-02.md#Steps"],
                         query="no printer is printing print service")]
    result, _ = run(script, network, confirm, office="MAD-02",
                    incident="no printer is printing")
    assert result.final == "resolved"
    assert network.services["MAD-02"]["printing"] == "ok"


def test_r2_at_most_one_restart_per_service(network):
    state = State("x", "MAD-01", service="vpn")
    action = Action("restart_service", {"service": "vpn", "office": "MAD-01"})
    assert guardrail(action, state, network, MONDAY_10) is None
    state.trace.append(Step(1, "knowledge", "restart_service",
                            {"service": "vpn", "office": "MAD-01"}, {"status": "ok"}))
    assert "maximum 1" in guardrail(action, state, network, SATURDAY_10)


def test_r2_closing_another_ticket_is_blocked(network):
    state = State("x", "MAD-01", ticket="T-0001")
    action = Action("close_ticket", {"ticket": "T-0009", "resolution": "x"})
    assert guardrail(action, state, network, MONDAY_10) is not None


# --- Criterion 4 / R3: step limit -------------------------------------------

def test_r3_limit(network):
    result, _ = run([call("search_tickets")] * 30, network)
    assert result.final == "step_limit_reached"
    counted = [s for s in result.trace if s.agent != "orchestrator"]
    assert len(counted) == 12


def test_r3_notes_do_not_count(network):
    # P3 with vpn down → note about raising it; knowledge only searches until the limit
    script = [classification(priority="P3"), *diagnosis("vpn")] + [
        call("search_docs", query="vpn")] * 30
    result, _ = run(script, network)
    assert result.final == "step_limit_reached"
    counted = [s for s in result.trace if s.agent != "orchestrator"]
    assert len(counted) == 12
    assert len(result.trace) > 12


def test_r3_limit_before_executing_the_action(network):
    # classifier (1) + diagnosis (3) + knowledge (3) = 7: executing would be the 8th
    script = [classification(), *diagnosis("vpn"), *knowledge(restart())]
    result, _ = run(script, network, Confirm(None), max_steps=7)
    assert result.final == "step_limit_reached"
    assert network.services["MAD-01"]["vpn"] == "down"
    assert len([s for s in result.trace if s.agent != "orchestrator"]) == 7


def test_r3_configurable_max_steps(network):
    result, _ = run([call("search_tickets")] * 30, network, max_steps=4)
    assert result.final == "step_limit_reached"
    assert len(result.trace) == 4


# --- Criterion 5 / R4: unreadable responses ----------------------------------

def test_r4_unreadable_classifier_escalates(network):
    result, _ = run(["I don't know", "still don't know", *escalation("P3")], network)
    assert result.final == "escalated"
    assert trajectory(result.trace) == ["classifier", "escalation"]
    assert result.escalation == "ESC-0001"


def test_r4_unreadable_escalation_still_creates_it(network):
    result, _ = run(["I don't know", "still don't know", "nothing", "neither"], network)
    assert result.final == "escalated"
    assert result.escalation == "ESC-0001"
    assert network.escalations[0]["priority"] == "P3"
    assert "I have no internet" in network.escalations[0]["summary"]


def test_r4_tool_error_does_not_stop(network):
    script = [classification(), call("check_service", service="vpn", office="XXX"),
              *diagnosis("vpn"), *knowledge(restart())]
    result, _ = run(script, network, Confirm(True))
    assert result.final == "resolved"
    assert any(isinstance(s.observation, dict) and "error" in s.observation
               for s in result.trace)


# --- Criterion 6 / R5: checked citations --------------------------------------

def test_r5_only_made_up_citation_escalates(network):
    script = [classification(), *diagnosis("vpn"),
              j({"procedure": "Restart the router.",
                 "citations": ["docs/kb-network-01.md#Steps"], "action": None}),  # no search_docs
              *escalation()]
    result, _ = run(script, network)
    assert result.final == "escalated"
    assert result.citations == []
    assert "citations removed" in notes(result)


def test_r5_removes_only_the_made_up_ones(network):
    citations = [VPN_CITATION, "docs/kb-email-02.md#Steps", "docs/does-not-exist.md#X"]
    script = [classification(), *diagnosis("vpn"), *knowledge(citations=citations)]
    result, _ = run(script, network)
    assert result.final == "resolved"
    assert result.citations == [VPN_CITATION]
    assert "kb-email-02" not in result.answer
    assert "does-not-exist" in notes(result)


def test_r5_without_procedure_escalates(network):
    script = [classification(), *diagnosis("vpn"), call("search_docs", query="vpn"),
              j({"procedure": None, "citations": [], "action": None}), *escalation()]
    result, _ = run(script, network)
    assert result.final == "escalated"


# --- Criterion 7: priority -----------------------------------------------------

def test_priority_is_raised_and_noted(network):
    script = [classification(priority="P3"), *diagnosis("vpn"), *knowledge()]
    result, _ = run(script, network)
    assert result.priority == "P1"
    assert "priority raised from P3 to P1" in notes(result)


def test_priority_is_never_lowered(network):
    script = [classification("email", "P1"), *diagnosis("email", "BCN-01"),
              *knowledge(citations=["docs/kb-email-01.md#Steps"],
                         query="email slow service degraded")]
    result, _ = run(script, network, office="BCN-01")
    assert result.priority == "P1"
    assert "priority raised" not in notes(result)


@pytest.mark.parametrize("office, service, expected", [
    ("MAD-01", "vpn", "P1"),          # critical down
    ("BCN-01", "email", "P2"),        # critical degraded
    ("MAD-02", "erp", "P1"),          # multi-office
    ("MAD-02", "printing", None),     # non-critical, one office
    ("VAL-01", None, None),           # device failure
])
def test_minimum_priority(network, office, service, expected):
    assert minimum_priority(network, office, service) == expected


# --- Criterion 8: same symptom, different cause ---------------------------------

def test_same_symptom_device_cause(network):
    script = [classification(priority="P3"), *diagnosis(None, "VAL-01"),
              *knowledge(citations=["docs/kb-network-02.md#Steps"],
                         query="faulty network card")]
    result, _ = run(script, network, Confirm(None), office="VAL-01", ticket="T-0002")
    assert result.final == "resolved"
    assert result.priority == "P3"
    assert "priority raised" not in notes(result)
    assert executed(result, "restart_service") == []
    assert "kb-network-02.md#Steps" in result.answer


# --- Criterion 9: reopened ticket ----------------------------------------------

def test_reopened_ticket_escalates_after_diagnosis(network):
    script = [classification("printer", "P4"), *diagnosis("printing", "MAD-02"),
              *escalation("P4")]
    result, _ = run(script, network, office="MAD-02", ticket="T-0007",
                    incident="the printer is not printing")
    assert trajectory(result.trace) == ["classifier", "diagnosis", "escalation"]
    assert result.final == "escalated"
    assert "reopened" in notes(result)
    assert network.escalations[0]["ticket"] == "T-0007"


# --- Criterion 10: multi-office ---------------------------------------------------

def test_multi_office_escalates_with_p1(network):
    script = [classification("app_access", "P2"), *diagnosis("erp", "MAD-02"),
              *escalation("P2")]  # the escalation agent proposes P2
    result, _ = run(script, network, office="MAD-02", ticket="T-0004",
                    incident="I can't log in to the ERP")
    assert trajectory(result.trace) == ["classifier", "diagnosis", "escalation"]
    assert result.final == "escalated"
    assert result.priority == "P1"
    assert network.escalations[0]["priority"] == "P1"
    assert "multi-office" in notes(result)
    assert "15 minutes" in result.answer


# --- Criterion 11: rejected -------------------------------------------------------

@pytest.mark.parametrize("office, ticket", [("SEV-01", None), ("MAD-01", "T-9999")])
def test_invalid_input_rejected_without_model(network, office, ticket):
    result, model = run([], network, office=office, ticket=ticket)
    assert result.final == "rejected"
    assert model.calls == []
    assert "does not exist" in result.answer


def test_out_of_scope_rejected(network):
    result, _ = run([classification("out_of_scope", "P4")], network,
                    incident="Can you recommend a restaurant?")
    assert result.final == "rejected"
    assert trajectory(result.trace) == ["classifier"]
    assert result.escalation is None and network.escalations == []


def test_rejection_without_priority(network):
    """Milestone 7b, D1: what is not processed has no priority."""
    result, _ = run([classification("out_of_scope", "P4")], network,
                    incident="Can you recommend a restaurant?")
    assert result.type == "out_of_scope" and result.priority is None


# --- Criterion 12: business hours --------------------------------------------------

@pytest.mark.parametrize("moment, expected", [
    (datetime(2026, 10, 16, 17, 59), True),   # Friday
    (datetime(2026, 10, 16, 18, 0), False),   # Friday 18:00
    (SATURDAY_10, False),
    (datetime(2026, 10, 12, 8, 0), True),     # Monday 08:00
    (datetime(2026, 10, 12, 7, 59), False),
])
def test_in_business_hours(moment, expected):
    assert in_business_hours(moment) is expected


# --- Live trace for the web (on_step) ------------------------------------------------

def test_on_step_receives_every_step_in_order(network):
    seen: list[Step] = []
    script = [classification(priority="P3"), *diagnosis("vpn"), *knowledge(restart())]
    result, _ = run(script, network, Confirm(True), on_step=seen.append)
    assert seen == list(result.trace)
    assert [s.n for s in seen] == list(range(1, len(seen) + 1))
    assert any(s.agent == "orchestrator" for s in seen)  # notes are streamed too


def test_on_step_sees_the_question_before_the_restart(network):
    """R1 in the live web: when confirm() is asked, the restart is not in the trace yet."""
    seen: list[Step] = []

    def confirm(action: Action) -> bool:
        assert not any(s.tool == "restart_service" for s in seen)
        return False

    script = [classification(), *diagnosis("vpn"), *knowledge(restart()), *escalation()]
    result, _ = run(script, network, confirm, on_step=seen.append)
    assert result.final == "escalated"
    assert not any(s.tool == "restart_service" for s in seen)


# --- Safety hazard: at least P2 and straight to escalation ----------------------------

@pytest.mark.parametrize("incident", ["The printer has exploded", "my laptop is on fire",
                                      "there is smoke coming out of the monitor",
                                      "sparks from the socket under my desk"])
def test_safety_hazard(incident):
    from office_support.orchestrator import safety_hazard
    assert safety_hazard(incident)


@pytest.mark.parametrize("incident", ["the firewall blocks the ERP", "I have no internet",
                                      "the printer is not printing"])
def test_no_safety_hazard(incident):
    from office_support.orchestrator import safety_hazard
    assert not safety_hazard(incident)


def test_safety_hazard_raises_to_p2_and_escalates_without_knowledge(network):
    script = [classification("printer", "P4"), *diagnosis(None), *escalation("P4")]
    result, _ = run(script, network, Confirm(None), incident="The printer has exploded")
    assert result.final == "escalated" and result.priority == "P2"
    assert trajectory(result.trace) == ["classifier", "diagnosis", "escalation"]
    assert network.escalations[0]["priority"] == "P2"
    assert "safety hazard" in notes(result)
    assert "priority raised from P4 to P2" in notes(result)


def test_safety_hazard_never_lowers_p1(network):
    script = [classification("network", "P3"), *diagnosis("vpn"), *escalation("P3")]
    result, _ = run(script, network, incident="smoke from the router and I have no internet")
    assert result.priority == "P1" and result.final == "escalated"

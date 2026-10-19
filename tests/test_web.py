"""Tests of the web logic (milestone 8), without Streamlit."""

import pytest

from office_support.model import OllamaModel, ScriptedModel, SimulatedModel
from office_support.state import Action
from office_support.web import (EXAMPLES, OFFICES, Execution, create_model, describe_action,
                                ollama_models, outages, stages, trace_rows)

INTERNET = ("I have no internet", "MAD-01", "T-0001")
VPN_RESTART = Action("restart_service", {"service": "vpn", "office": "MAD-01"})


def finish(execution: Execution, yes: bool | None = None):
    """Waits; if it asks, answers `yes`; returns the result."""
    execution.wait(10)
    if yes is not None:
        assert execution.pending == VPN_RESTART
        execution.respond(yes)
        execution.wait(10)
    assert execution.pending is None and execution.error is None
    return execution.result


def test_stops_to_ask_without_executing_anything():
    execution = Execution(*INTERNET)
    execution.wait(10)
    assert execution.pending == VPN_RESTART and execution.result is None
    assert describe_action(execution.pending) == "restart_service(service=vpn, office=MAD-01)"
    execution.respond(False)  # do not leave the thread waiting


def test_confirming_from_the_web_resolves():
    result = finish(Execution(*INTERNET), yes=True)
    assert (result.final, result.priority) == ("resolved", "P1")
    assert any(s.tool == "restart_service" for s in result.trace)


def test_rejecting_from_the_web_escalates_without_restarting_r1():
    result = finish(Execution(*INTERNET), yes=False)
    assert result.final == "escalated"
    assert not any(s.tool == "restart_service" for s in result.trace)


@pytest.mark.parametrize("example, final", [
    (EXAMPLES[1], "resolved"),   # case 3
    (EXAMPLES[2], "escalated"),  # case 5
    (EXAMPLES[3], "escalated"),  # case 4
    (EXAMPLES[4], "resolved"),   # case 11
    (EXAMPLES[5], "rejected"),   # case 7
], ids=lambda x: getattr(x, "title", x))
def test_examples_give_the_final_of_my_evaluation(example, final):
    result = finish(Execution(example.incident, example.office, example.ticket))
    assert result.final == final


def test_empty_ticket_means_no_ticket():
    result = finish(Execution("the printer is not printing", "MAD-01", "   "))
    assert result.final != "rejected"


@pytest.mark.parametrize("office, ticket, reason", [
    ("SEV-01", "", "SEV-01 does not exist"),
    ("MAD-01", "T-9999", "T-9999 does not exist"),
])
def test_invalid_input_rejected(office, ticket, reason):
    result = finish(Execution("I have no internet", office, ticket))
    assert result.final == "rejected" and reason in result.answer


def test_a_model_failure_is_shown_as_an_error():
    execution = Execution(*INTERNET, model=ScriptedModel([]))  # empty script: RuntimeError
    execution.wait(10)
    assert isinstance(execution.error, RuntimeError) and execution.result is None


def test_examples_use_valid_offices_and_trace_rows():
    assert all(e.office in OFFICES for e in EXAMPLES)
    rows = trace_rows(finish(Execution(*INTERNET), yes=True).trace)
    assert rows[0]["agent"] == "classifier" and set(rows[0]) == {
        "n", "agent", "tool", "observation"}


def test_outages_shows_the_initial_state_of_the_network():
    state = outages()
    assert state["MAD-01"]["vpn"] == "down"
    assert state["VAL-01"] == {}


def test_ollama_models_empty_if_it_is_not_running():
    assert ollama_models("http://127.0.0.1:9/v1", timeout=0.5) == []


def test_create_model_by_name():
    assert isinstance(create_model("simulated"), SimulatedModel)
    real = create_model("qwen2.5:14b")
    assert isinstance(real, OllamaModel) and real.model == "qwen2.5:14b"


def test_responding_without_a_pending_question_does_not_block():
    """With a real model, the run may finish without asking: responding must not hang it."""
    execution = Execution("the printer is not printing", "MAD-02", "T-0007")  # escalates without asking
    execution.wait(10)
    execution.respond(True)
    execution.wait(2)
    assert execution.result.final == "escalated" and execution.answer is None


def test_stages_marks_the_agents_that_acted():
    result = finish(Execution("I can't log in to the ERP", "MAD-02", "T-0004"))
    assert stages(result) == [("classifier", True), ("diagnosis", True),
                              ("knowledge", False), ("escalation", True)]


def test_explanations_match_the_guide_and_the_catalog():
    from pathlib import Path

    from office_support import web
    guide = (Path(__file__).resolve().parents[1] / "docs" / "priority-guide.md"
             ).read_text(encoding="utf-8").replace("`", "")
    for priority, criterion in web.PRIORITY_CRITERIA.items():
        assert criterion.split(",")[0] in guide
    assert web.explain_priority("P1").endswith("First response within 15 minutes.")
    assert set(web.FINAL_MEANING) == {"resolved", "escalated", "rejected", "step_limit_reached"}


# --- JSON views for the React console (server.py) ------------------------------------

def test_snapshot_streams_steps_with_kinds_and_rules():
    execution = Execution(*INTERNET)
    execution.wait(10)
    snap = execution.snapshot()
    assert snap["pending"]["tool"] == "restart_service" and not snap["done"]
    kinds = [s["kind"] for s in snap["steps"]]
    assert kinds[:3] == ["output", "call", "tool"]
    assert any(s["kind"] == "note" and s["rule"] == "priority" for s in snap["steps"])
    execution.respond(False)
    execution.wait(10)
    final = execution.snapshot(since=snap["total"])
    assert final["done"] and final["result"]["final"] == "escalated"
    assert final["steps"][0]["rule"] == "R1"


@pytest.mark.parametrize("text, rule", [
    ("action restart_service rejected by the user: not executed", "R1"),
    ("action restart_service blocked by the guardrail: x", "R2"),
    ("2 unreadable responses in a row from classifier: escalating", "R4"),
    ("citations removed because they were not retrieved: x", "R5"),
    ("priority raised from P3 to P1: x", "priority"),
    ("direct escalation: multi-office outage of erp", "handoff"),
    ("rejected: office SEV-01 does not exist", "input"),
    ("something else", None),
])
def test_note_rule(text, rule):
    from office_support.web import note_rule
    assert note_rule(text) == rule


def test_meta_describes_agents_from_their_definition():
    from office_support.agents import AGENTS
    from office_support.web import meta
    data = meta()
    for agent in data["agents"]:
        assert agent["tools"] == list(AGENTS[agent["name"]].tools)
    assert data["critical"] == ["email", "erp", "files", "intranet", "vpn"]


def test_safety_example_is_escalated_with_p2():
    example = EXAMPLES[6]
    result = finish(Execution(example.incident, example.office, example.ticket))
    assert (result.final, result.priority) == ("escalated", "P2")

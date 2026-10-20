"""Tests of the common agent loop and of the four agents."""

import json
from pathlib import Path

import pytest

from office_support import agents
from office_support.agents import AGENTS, extract_json, run_agent, system_prompt
from office_support.domain import Action, State
from office_support.domain.policy import SERVICE_DESCRIPTIONS, SERVICES, TYPES
from office_support.model import ScriptedModel
from office_support.tools import Network, create_tools


def j(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def call(tool: str, **arguments) -> str:
    return j({"tool": tool, "arguments": arguments})


@pytest.fixture
def network() -> Network:
    return Network.from_directory()


@pytest.fixture
def t(network):
    return create_tools(network)


@pytest.fixture
def state() -> State:
    return State("I have no internet", "MAD-01", ticket="T-0001")


VPN_PROCEDURE = {
    "procedure": "The office VPN is down; it is restarted and the browser is reopened.",
    "citations": ["docs/kb-network-01.md#Steps"],
    "action": None,
}


# --- Criterion 1: extract_json -------------------------------------------------

@pytest.mark.parametrize("text", [
    '{"a": 1}',
    '```json\n{"a": 1}\n```',
    'Sure, here it is:\n```json\n{"a": 1}\n```\nI hope it helps.',
    'My answer is {"a": 1} and nothing else.',
])
def test_extract_json_accepts(text):
    assert extract_json(text) == {"a": 1}


@pytest.mark.parametrize("text", ["no idea what to say", "[1, 2]", '[{"a": 1}]', "", "{broken"])
def test_extract_json_rejects(text):
    with pytest.raises(ValueError):
        extract_json(text)


# --- Criterion 2: system prompt -------------------------------------------------

@pytest.mark.parametrize("name", list(AGENTS))
def test_prompt_only_allowed_tools(name, t):
    agent = AGENTS[name]
    prompt = system_prompt(agent, t)
    for key in agent.keys:
        assert key in prompt
    for tool in t.values():
        if tool.name in agent.tools:
            assert tool.name in prompt
            assert tool.description in prompt
        else:
            assert tool.name not in prompt, tool.name
    assert "single JSON object" in prompt


def test_knowledge_prompt_separates_proposable(t):
    prompt = system_prompt(AGENTS["knowledge"], t)
    rest, proposable = prompt.split("Actions you can propose")
    callable_ = rest.split("Tools you can call")[1]  # only the list
    assert "search_docs(query: str, k: int = 3)" in callable_
    assert "restart_service" not in callable_
    assert "restart_service(service: str, office: str)" in proposable


# --- Criterion 3: knowledge, happy path ------------------------------------------

def test_knowledge_happy_path(state, t):
    model = ScriptedModel([call("search_docs", query="vpn down"), j(VPN_PROCEDURE)])
    output = agents.knowledge(state, model, t)
    assert output.reason == "ok"
    assert state.procedure == VPN_PROCEDURE["procedure"]
    assert state.citations == ["docs/kb-network-01.md#Steps"]
    assert state.actions == []
    assert state.steps == 3
    model1, tool, model2 = state.trace
    assert [s.n for s in state.trace] == [1, 2, 3]
    assert model1.tool is None and model2.tool is None
    assert tool.tool == "search_docs"
    assert tool.observation["fragments"][0]["doc"] == "docs/kb-network-01.md"
    assert all(s.agent == "knowledge" for s in state.trace)


# --- Criterion 4: proposed action, not executed -----------------------------------

def test_knowledge_with_action(state, t, network):
    output_json = dict(VPN_PROCEDURE, action={
        "tool": "restart_service",
        "arguments": {"service": "vpn", "office": "MAD-01"},
    })
    model = ScriptedModel([call("search_docs", query="vpn"), j(output_json)])
    output = agents.knowledge(state, model, t)
    assert output.reason == "ok"
    assert state.actions == [Action("restart_service", {"service": "vpn", "office": "MAD-01"})]
    assert network.services["MAD-01"]["vpn"] == "down"


def test_knowledge_reversible_action_is_unreadable(state, t):
    bad = dict(VPN_PROCEDURE, action={"tool": "search_docs", "arguments": {}})
    output = agents.knowledge(state, ScriptedModel([j(bad), j(bad)]), t)
    assert output.reason == "unreadable"
    assert state.actions == []


# --- Criterion 5: irreversible called as a turn ------------------------------------

@pytest.mark.parametrize("turn", [
    call("restart_service", service="vpn", office="MAD-01"),
    call("close_ticket", ticket="T-0001", resolution="fixed"),
])
def test_irreversible_as_turn_is_not_executed(state, t, network, turn):
    model = ScriptedModel([turn, j(VPN_PROCEDURE)])
    output = agents.knowledge(state, model, t)
    assert output.reason == "ok"
    assert network.services["MAD-01"]["vpn"] == "down"
    assert network.ticket("T-0001")["status"] == "open"
    block = state.trace[1]
    assert block.tool is None
    assert "irreversible" in block.observation["error"]
    assert not any(s.tool in {"restart_service", "close_ticket"}
                   for s in state.trace)
    assert "action" in model.calls[1]["messages"][-1]["content"]


CLASSIFICATION = {"type": "network", "priority": "P1", "reason": "critical vpn down"}
DIAGNOSIS = {"cause": "VPN of MAD-01 down", "service": "vpn",
             "evidence": ["check_service(vpn, MAD-01) = down"]}
ESCALATION = {"summary": "VPN down in MAD-01, restart rejected",
              "tried": ["check the status of the vpn"], "priority": "P1"}


# --- Criterion 6: tool not allowed ---------------------------------------------------

def test_tool_not_allowed(state, t):
    model = ScriptedModel([call("check_service", service="vpn", office="MAD-01"),
                           j(CLASSIFICATION)])
    output = agents.classifier(state, model, t)
    assert output.reason == "ok"
    block = state.trace[1]
    assert block.tool is None
    assert "not allowed" in block.observation["error"]
    assert not any(s.tool == "check_service" for s in state.trace)
    assert "not allowed" in model.calls[1]["messages"][-1]["content"]


# --- Criterion 7: ToolError as an observation ------------------------------------------

def test_tool_error_as_observation(state, t):
    model = ScriptedModel([
        call("check_service", service="vpn", office="SEV-01"),
        call("check_service", service="vpn", office="MAD-01"),
        j(DIAGNOSIS),
    ])
    output = agents.diagnosis(state, model, t)
    assert output.reason == "ok"
    error, correct = state.trace[1], state.trace[3]
    assert error.tool == "check_service"
    assert "unknown office" in error.observation["error"]
    assert correct.observation["status"] == "down"


# --- Criterion 8: unreadable responses ---------------------------------------------------

def test_one_unreadable_then_valid(state, t):
    output = agents.classifier(state, ScriptedModel(["no idea", j(CLASSIFICATION)]), t)
    assert output.reason == "ok"
    assert "invalid response" in state.trace[0].observation


def test_two_unreadable_in_a_row(state, t):
    output = agents.classifier(state, ScriptedModel(["no idea", "neither"]), t)
    assert output.reason == "unreadable"
    assert output.data is None
    assert state.type is None and state.steps == 2


@pytest.mark.parametrize("bad", [
    {"type": "network", "priority": "P1"},                   # reason missing
    {"type": "router", "priority": "P1", "reason": "x"},     # invalid type
    {"type": "network", "priority": "P9", "reason": "x"},    # invalid priority
])
def test_broken_contract_counts_as_unreadable(state, t, bad):
    output = agents.classifier(state, ScriptedModel([j(bad), j(bad)]), t)
    assert output.reason == "unreadable"


def test_non_consecutive_unreadable_do_not_stop(state, t):
    model = ScriptedModel(["no idea", call("search_tickets", office="MAD-01"),
                           "still no", j(CLASSIFICATION)])
    assert agents.classifier(state, model, t).reason == "ok"


# --- Criterion 9: step limit ------------------------------------------------------------

def test_limit(state, t):
    model = ScriptedModel([call("search_tickets")] * 10)
    output = agents.classifier(state, model, t, max_steps=3)
    assert output.reason == "limit"
    assert state.steps == 3 and len(state.trace) == 3


def test_limit_counts_previous_steps(state, t):
    state.steps = 12
    model = ScriptedModel([j(CLASSIFICATION)])
    assert agents.classifier(state, model, t).reason == "limit"
    assert model.calls == []


# --- Criterion 10: classifier and diagnosis fill in the state -------------------------------

def test_classifier_fills_state(state, t):
    model = ScriptedModel([call("search_tickets", symptom="internet"),
                           j(dict(CLASSIFICATION, priority="P3"))])
    agents.classifier(state, model, t)
    assert state.type == "network"
    assert state.priority == "P3"  # as is; the orchestrator raises it (milestone 5)


def test_diagnosis_fills_state(state, t):
    agents.diagnosis(state, ScriptedModel([j(DIAGNOSIS)]), t)
    assert state.cause == "VPN of MAD-01 down"
    assert state.service == "vpn"


def test_diagnosis_null_service_for_device(t):
    state = State("I have no internet", "VAL-01", ticket="T-0002")
    response = {"cause": "faulty network card in PC-VAL01-002", "service": None,
                "evidence": ["PC-VAL01-002: faulty_network_card"]}
    model = ScriptedModel([call("check_device", device_id="PC-VAL01-002"), j(response)])
    assert agents.diagnosis(state, model, t).reason == "ok"
    assert state.service is None


# --- Criterion 11: escalation --------------------------------------------------------------

def test_escalation_creates_in_the_network(state, t, network):
    output = agents.escalation(state, ScriptedModel([j(ESCALATION)]), t)
    assert output.reason == "ok"
    assert output.data["escalation"] == "ESC-0001"
    assert network.escalations == [{"id": "ESC-0001", "ticket": "T-0001",
                                    "summary": ESCALATION["summary"], "priority": "P1"}]
    last = state.trace[-1]
    assert (last.agent, last.tool) == ("escalation", "create_escalation")
    assert last.observation["escalation"] == "ESC-0001"


def test_escalation_not_duplicated_if_the_agent_created_it(state, t, network):
    model = ScriptedModel([
        call("create_escalation", ticket="T-0001", summary="VPN down", priority="P1"),
        j(ESCALATION),
    ])
    output = agents.escalation(state, model, t)
    assert output.data["escalation"] == "ESC-0001"
    assert len(network.escalations) == 1


def test_escalation_with_nonexistent_ticket_creates_without_ticket(t, network):
    state = State("x", "MAD-01", ticket="T-9999")
    output = agents.escalation(state, ScriptedModel([j(ESCALATION)]), t)
    assert output.data["escalation"] == "ESC-0001"
    assert network.escalations[0]["ticket"] is None


# --- Criterion 12: messages sent to the model -------------------------------------------------

def test_messages_carry_context_and_observations(state, t):
    state.type, state.priority = "network", "P1"
    state.cause, state.service = "VPN of MAD-01 down", "vpn"
    model = ScriptedModel([call("search_docs", query="vpn down"), j(VPN_PROCEDURE)])
    agents.knowledge(state, model, t)
    first = json.loads(model.calls[0]["messages"][0]["content"])
    assert first["incident"] == "I have no internet"
    assert first["office"] == "MAD-01" and first["ticket"] == "T-0001"
    assert first["known"] == {"type": "network", "priority": "P1",
                              "cause": "VPN of MAD-01 down", "service": "vpn"}
    second = model.calls[1]["messages"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    assert "kb-network-01.md" in second[-1]["content"]
    assert "knowledge" in model.calls[0]["system"]


# --- After the test with the real model: exact format in the prompt -----------------------------

@pytest.mark.parametrize("name", sorted(AGENTS))
def test_prompt_includes_exact_format(name, t):
    prompt = system_prompt(AGENTS[name], t)
    assert AGENTS[name].format and AGENTS[name].format in prompt


def test_diagnosis_prompt_values_and_lists(t):
    prompt = system_prompt(AGENTS["diagnosis"], t)
    assert all(s in prompt for s in SERVICES)
    assert '"evidence": ["<text>"' in prompt
    assert "check at least one tool" in prompt


def test_classifier_prompt_allowed_types(t):
    prompt = system_prompt(AGENTS["classifier"], t)
    assert "|".join(sorted(TYPES)) in prompt


def test_service_descriptions_match_the_catalog():
    catalog = (Path(__file__).resolve().parents[1] / "docs" / "service-catalog.md"
               ).read_text(encoding="utf-8")
    assert set(SERVICE_DESCRIPTIONS) == SERVICES
    for service, description in SERVICE_DESCRIPTIONS.items():
        assert f"| `{service}` | {description} |" in catalog


def test_knowledge_prompt_searches_first(t):
    assert "first turn is ALWAYS a call to search_docs" in system_prompt(
        AGENTS["knowledge"], t)

"""Tests of HFModel (with a fake client, no network) and of SimulatedModel."""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from office_support.interfaces import cli
from office_support import model as model_module
from office_support.model import (DEFAULT_MODEL, OLLAMA_DEFAULT_MODEL, HFModel,
                                  OllamaModel, SimulatedModel)
from office_support.orchestration import orchestrate, trajectory
from office_support.tools import Network

MONDAY_10 = datetime(2026, 10, 12, 10, 0)
FAKE_TOKEN = "hf_faketokenfortests123"


@pytest.fixture(autouse=True)
def without_real_env(monkeypatch):
    """No test reads the real .env or uses a real token."""
    monkeypatch.setattr(model_module, "load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HF_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)


def response(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class FakeClient:
    """Imitates InferenceClient.chat_completion; it can fail the first times."""

    def __init__(self, failures: int = 0, text: str = '{"ok": true}') -> None:
        self.failures, self.text = failures, text
        self.calls: list[dict] = []

    def chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) <= self.failures:
            raise ConnectionError(f"provider down (token {FAKE_TOKEN})")
        return response(self.text)


# --- Criterion 1: messages and parameters --------------------------------------

def test_sends_system_messages_and_parameters():
    client = FakeClient(text='{"type": "network"}')
    messages = [{"role": "user", "content": "I have no internet"}]
    text = HFModel(client=client).generate("you are the classifier", messages)
    assert text == '{"type": "network"}'
    call = client.calls[0]
    assert call["messages"] == [{"role": "system", "content": "you are the classifier"},
                                *messages]
    assert call["temperature"] == 0 and call["max_tokens"] == 512


# --- Criterion 2: no token ----------------------------------------------------

def test_without_token_clear_error():
    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        HFModel()


# --- Criterion 3: retry and errors without the token --------------------------------

def test_retries_once():
    client = FakeClient(failures=1)
    assert HFModel(client=client).generate("s", []) == '{"ok": true}'
    assert len(client.calls) == 2


def test_fails_after_two_attempts_without_showing_token(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", FAKE_TOKEN)
    client = FakeClient(failures=99)
    with pytest.raises(RuntimeError) as error:
        HFModel(client=client).generate("s", [])
    assert len(client.calls) == 2
    assert FAKE_TOKEN not in str(error.value)
    assert "2 attempt" in str(error.value)


class HTTPError(Exception):
    """Imitates HfHubHTTPError: it carries the response with its status code."""

    def __init__(self, status: int) -> None:
        super().__init__(f"HTTP {status}")
        self.response = SimpleNamespace(status_code=status)


class HTTPClient:
    def __init__(self, status: int) -> None:
        self.status, self.calls = status, 0

    def chat_completion(self, **kwargs):
        self.calls += 1
        raise HTTPError(self.status)


@pytest.mark.parametrize("status, calls", [
    (401, 1), (402, 1), (404, 1),    # not fixed by retrying
    (429, 2), (500, 2), (503, 2),    # transient
])
def test_only_retries_transient_failures(status, calls):
    client = HTTPClient(status)
    with pytest.raises(RuntimeError, match=str(status)):
        HFModel(client=client).generate("s", [])
    assert client.calls == calls


# --- Criterion 4: HF_MODEL -------------------------------------------------------

def test_default_model_and_hf_model(monkeypatch):
    assert HFModel(client=FakeClient()).model == DEFAULT_MODEL
    monkeypatch.setenv("HF_MODEL", "other/model")
    assert HFModel(client=FakeClient()).model == "other/model"
    assert HFModel("explicit/model", client=FakeClient()).model == "explicit/model"


# --- Criterion 5: SimulatedModel with the orchestrator --------------------------------

def run(incident: str, office: str, confirm: bool, ticket: str | None = None):
    network = Network.from_directory()
    result = orchestrate(incident, office, SimulatedModel(), lambda action: confirm,
                         now=lambda: MONDAY_10, ticket=ticket, network=network)
    return result, network


def test_simulated_resolves_with_restart():
    result, network = run("I have no internet", "MAD-01", True)
    assert result.final == "resolved"
    assert (result.type, result.priority) == ("network", "P1")
    assert network.services["MAD-01"]["vpn"] == "ok"
    assert result.citations == ["docs/kb-network-01.md#Steps"]


def test_simulated_rejection_escalates():
    result, network = run("I have no internet", "MAD-01", False)
    assert result.final == "escalated"
    assert network.services["MAD-01"]["vpn"] == "down"


def test_simulated_multi_office():
    result, network = run("I can't log in to the ERP", "MAD-02", True)
    assert result.final == "escalated" and result.priority == "P1"
    assert trajectory(result.trace) == ["classifier", "diagnosis", "escalation"]
    assert network.escalations[0]["priority"] == "P1"


def test_simulated_reopened_ticket():
    result, _ = run("the printer is not printing", "MAD-02", True, ticket="T-0007")
    assert result.final == "escalated"
    assert trajectory(result.trace) == ["classifier", "diagnosis", "escalation"]


def test_simulated_device_without_restart():
    result, network = run("I have no internet", "VAL-01", True, ticket="T-0002")
    assert result.final == "resolved"
    assert not any(s.tool == "restart_service" for s in result.trace)


@pytest.mark.parametrize("incident, type_", [
    ("I have no internet", "network"),
    ("the printer is not printing", "printer"),
    ("I can't log in to the ERP", "app_access"),
    ("my password has expired", "app_access"),
    ("email takes a long time", "email"),
    ("my laptop won't turn on", "hardware"),
    ("the chair is broken", "other"),
    ("my computer is slow", "hardware"),
    ("the PC freezes", "hardware"),
    ("Can you recommend a restaurant?", "out_of_scope"),
])
def test_simulated_classifies_by_words(incident, type_):
    assert model_module._type_from_words(incident) == type_


@pytest.mark.parametrize("incident, priority", [
    ("the printer is not printing", "P4"),  # there is usually another printer
    ("my computer is slow", "P4"),          # annoyance: they can keep working
    ("I have no internet", "P3"),
])
def test_simulated_initial_priority(incident, priority):
    context = {"incident": incident, "office": "MAD-01", "known": {}}
    data = SimulatedModel()._classifier(context, 0, [])
    assert data["priority"] == priority


def test_simulated_does_not_cite_articles_of_another_type():
    context = {"incident": "my computer is slow", "office": "MAD-01",
               "known": {"type": "hardware", "cause": "slow device"}}
    observation = {"fragments": [{"doc": "docs/kb-network-02.md", "section": "Steps",
                                  "text": "1. Try another cable."}]}
    messages = [{"role": "user", "content": json.dumps(context)},
                {"role": "assistant", "content": "{}"},
                {"role": "user", "content": "Observation: " + json.dumps(observation)}]
    data = SimulatedModel()._knowledge(context, 1, messages)
    assert data["procedure"] is None and data["citations"] == []


# --- Milestone 6b: OllamaModel (fake client: Ollama need not be installed) -------

def test_ollama_without_token_sends_the_model():
    client = FakeClient(text='{"type": "network"}')
    text = OllamaModel(client=client).generate("you are the classifier", [])
    assert text == '{"type": "network"}'
    call = client.calls[0]
    assert call["model"] == OLLAMA_DEFAULT_MODEL
    assert call["temperature"] == 0 and call["max_tokens"] == 512


def test_ollama_configurable_model(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")
    assert OllamaModel(client=FakeClient()).model == "llama3.1:8b"


def test_ollama_retries_like_hf():
    client = FakeClient(failures=1)
    OllamaModel(client=client).generate("s", [])
    assert len(client.calls) == 2


def test_hf_does_not_send_model_in_every_call():
    client = FakeClient()
    HFModel(client=client).generate("s", [])
    assert "model" not in client.calls[0]


def test_cli_creates_ollama_model():
    assert isinstance(cli._create_model("ollama"), OllamaModel)
    assert isinstance(cli._create_model("simulated"), SimulatedModel)


def test_simulated_only_gives_a_procedure_from_a_steps_section():
    """Bug found by Alberto in the web: it answered with the «Cause» section."""
    context = {"incident": "I don't know how to turn off the printer", "office": "MAD-01",
               "known": {"type": "printer", "cause": "printing ok"}}
    observation = {"fragments": [{"doc": "docs/kb-printer-01.md", "section": "Cause",
                                  "text": "Physical failure of the printer."}]}
    messages = [{"role": "user", "content": json.dumps(context)},
                {"role": "assistant", "content": "{}"},
                {"role": "user", "content": "Observation: " + json.dumps(observation)}]
    data = SimulatedModel()._knowledge(context, 1, messages)
    assert data["procedure"] is None and data["citations"] == []


@pytest.mark.parametrize("incident", ["The printer has exploded", "my laptop is on fire",
                                      "smoke is coming out of the monitor"])
def test_simulated_escalates_physical_damage(incident):
    """Found by Alberto in the React console: an exploded printer was "resolved" with
    the paper-jam steps. Physical repairs are not first level: no procedure → escalation."""
    result, network = run(incident, "MAD-01", True)
    assert result.final == "escalated" and result.citations == []
    assert not any(s.tool == "restart_service" for s in result.trace)
    assert "physical damage" in network.escalations[0]["summary"]

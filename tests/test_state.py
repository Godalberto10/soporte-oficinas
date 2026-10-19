"""Tests of the dataclasses of the shared state."""

from dataclasses import fields, is_dataclass

from office_support.state import Action, Result, State, Step


def _fields(cls) -> list[str]:
    return [f.name for f in fields(cls)]


def test_are_dataclasses():
    for cls in (Step, Action, State, Result):
        assert is_dataclass(cls)


def test_fields_from_claude_md():
    assert _fields(Step) == ["n", "agent", "tool", "arguments", "observation"]
    assert _fields(Action) == ["tool", "arguments"]
    assert _fields(State) == [
        "incident", "office", "ticket", "type", "priority", "cause",
        "service", "procedure", "citations", "actions", "trace", "steps", "final",
    ]
    assert _fields(Result) == [
        "final", "answer", "citations", "trace", "type", "priority", "escalation",
    ]


def test_state_initial_values():
    state = State("I have no internet", "MAD-01")
    assert state.trace == [] and state.actions == [] and state.citations == []
    assert state.steps == 0
    assert state.final is None
    assert state.ticket is None and state.service is None


def test_lists_not_shared_between_instances():
    a = State("x", "MAD-01")
    b = State("y", "VAL-01")
    a.trace.append(Step(1, "classifier", None, {}, "{}"))
    a.actions.append(Action("restart_service", {"service": "vpn"}))
    a.citations.append("docs/kb-network-01.md#Steps")
    assert b.trace == [] and b.actions == [] and b.citations == []


def test_result_defaults_to_no_escalation():
    result = Result(final="resolved", answer="Done.")
    assert result.escalation is None
    assert result.citations == [] and result.trace == []

"""Output contract of an agent: reading the JSON of a response and validating its keys."""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass

from office_support.domain.policy import PRIORITIES, SERVICES, TYPES

PROPOSABLE_ACTIONS = frozenset({"restart_service", "close_ticket"})


@dataclass(frozen=True)
class Agent:
    """Definition of an agent: role, allowed tools and output contract."""

    name: str
    instructions: str
    tools: tuple[str, ...]
    keys: tuple[str, ...]
    validate: Callable[[dict], None]
    format: str = ""  # exact example of the final output, with allowed types and values


@dataclass
class AgentOutput:
    """Result of running an agent: validated data or reason for stopping."""

    data: dict | None
    reason: str  # ok | unreadable | limit


# --- JSON ------------------------------------------------------------------

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> dict:
    """First JSON object of the text (bare, in a ```json block or with text around it)."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return _find_object(text)
    if not isinstance(data, dict):
        raise ValueError("a JSON object was expected, not another type of value")
    return data


def _find_object(text: str) -> dict:
    if not isinstance(text, str):
        raise ValueError("the response is not text")
    block = _JSON_BLOCK.search(text)
    candidate = block.group(1) if block else text
    decoder = json.JSONDecoder()
    for start in (i for i, c in enumerate(candidate) if c == "{"):
        try:
            data, _ = decoder.raw_decode(candidate, start)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    raise ValueError("there is no JSON object in the response")


# --- Contract validation ----------------------------------------------------

def _text(data: dict, key: str, nullable: bool = False) -> None:
    value = data.get(key)
    if value is None and nullable:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{key}' must be a non-empty string")


def _text_list(data: dict, key: str) -> None:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"'{key}' must be a list of strings")


def _one_of(data: dict, key: str, values: frozenset[str], nullable: bool = False) -> None:
    value = data.get(key)
    if value is None and nullable:
        return
    if not isinstance(value, str) or value not in values:
        raise ValueError(f"'{key}' must be one of {sorted(values)}")


def validate_classifier(data: dict) -> None:
    _one_of(data, "type", TYPES)
    _one_of(data, "priority", PRIORITIES)
    _text(data, "reason")


def validate_diagnosis(data: dict) -> None:
    _text(data, "cause")
    _one_of(data, "service", SERVICES, nullable=True)
    _text_list(data, "evidence")


def validate_knowledge(data: dict) -> None:
    _text(data, "procedure", nullable=True)
    _text_list(data, "citations")
    action = data.get("action")
    if action is None:
        return
    if (not isinstance(action, dict)
            or action.get("tool") not in PROPOSABLE_ACTIONS
            or not isinstance(action.get("arguments"), dict)):
        raise ValueError("'action' must be null or {\"tool\": "
                         f"one of {sorted(PROPOSABLE_ACTIONS)}, \"arguments\": {{...}}}}")


def validate_escalation(data: dict) -> None:
    _text(data, "summary")
    _text_list(data, "tried")
    _one_of(data, "priority", PRIORITIES)


def validate_contract(agent: Agent, data: dict) -> dict:
    """Checks keys and values; returns only the keys of the contract."""
    missing = [k for k in agent.keys if k not in data]
    if missing:
        raise ValueError(f"missing contract keys: {', '.join(missing)}")
    agent.validate(data)
    return {k: data[k] for k in agent.keys}

"""Common agent loop and the four specialist agents."""

import inspect
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from office_support.model import Model
from office_support.state import Action, State, Step
from office_support.tools import PRIORITIES, Tool, ToolError, execute

TYPES = frozenset({"network", "printer", "app_access", "email", "hardware", "other",
                   "out_of_scope"})
SERVICES = frozenset({"vpn", "email", "erp", "files", "intranet",
                      "printing", "guest_wifi"})
SERVICE_DESCRIPTIONS = {  # same as docs/service-catalog.md (a test checks it)
    "vpn": "Office tunnel to the data center and internet access",
    "email": "Corporate email (Outlook and webmail)",
    "erp": "Management application (orders, invoicing, warehouse)",
    "files": "Shared folders of the office",
    "printing": "Print queue server",
    "guest_wifi": "Wireless network for visitors",
    "intranet": "Internal portal and password self-service",
}
PROPOSABLE_ACTIONS = frozenset({"restart_service", "close_ticket"})
MAX_UNREADABLE = 2


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


def _validate_classifier(data: dict) -> None:
    _one_of(data, "type", TYPES)
    _one_of(data, "priority", PRIORITIES)
    _text(data, "reason")


def _validate_diagnosis(data: dict) -> None:
    _text(data, "cause")
    _one_of(data, "service", SERVICES, nullable=True)
    _text_list(data, "evidence")


def _validate_knowledge(data: dict) -> None:
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


def _validate_escalation(data: dict) -> None:
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


# --- Agent definitions -------------------------------------------------------

def _options(values: frozenset[str]) -> str:
    return "|".join(sorted(values))


_P = _options(PRIORITIES)

AGENTS: dict[str, Agent] = {
    "classifier": Agent(
        "classifier",
        "You decide the incident type and its priority.\n"
        f"Types: {', '.join(sorted(TYPES))}. Use 'other' for support incidents "
        "without a category and 'out_of_scope' if the request is not about office "
        "technical support.\n"
        "Priorities: P1 affects more than one office or a critical service is "
        "down; P2 affects an entire office or a critical service is degraded; P3 an "
        "employee cannot work and there is no alternative; P4 an inconvenience with "
        "an alternative.\n"
        "Critical services: vpn, email, erp, files, intranet.",
        ("search_tickets",),
        ("type", "priority", "reason"),
        _validate_classifier,
        f'{{"type": "{_options(TYPES)}", "priority": "{_P}", "reason": "<text>"}}',
    ),
    "diagnosis": Agent(
        "diagnosis",
        "You find out the probable cause by checking the real status of the services, "
        "the devices and the tickets. Give the affected service (or null if it is a "
        "device) and, in evidence, what you have observed. If the outage affects "
        "more than one office, say so in the evidence.\n"
        "Before concluding, check at least one tool (for example, check_service "
        "for the related service in the office of the incident) and do not invent "
        "causes you have not observed.\n"
        "Services of each office:\n"
        + "\n".join(f"- {s}: {d}" for s, d in SERVICE_DESCRIPTIONS.items()),
        ("check_service", "check_device", "search_tickets"),
        ("cause", "service", "evidence"),
        _validate_diagnosis,
        f'{{"cause": "<text>", "service": "{_options(SERVICES)}" or null, '
        '"evidence": ["<text>", "<text>"]}',
    ),
    "knowledge": Agent(
        "knowledge",
        "You search the knowledge base for the procedure that solves the diagnosed "
        "cause and write it for the employee. Your first turn is ALWAYS a call to "
        "search_docs with the diagnosed cause. Only cite fragments you have retrieved "
        "with search_docs, in the format docs/<file>.md#<section>. "
        "If you find no procedure, return procedure null and citations []. "
        "Irreversible actions are NOT called: they are proposed in 'action' as "
        "{\"tool\": ..., \"arguments\": {...}} and a person will confirm them.",
        ("search_docs", "restart_service", "close_ticket"),
        ("procedure", "citations", "action"),
        _validate_knowledge,
        '{"procedure": "<text>" or null, "citations": ["docs/<file>.md#<section>"], '
        f'"action": null or {{"tool": "{_options(PROPOSABLE_ACTIONS)}", '
        '"arguments": {...}}}',
    ),
    "escalation": Agent(
        "escalation",
        "You prepare the handoff to second level: a clear summary of the incident and "
        "its cause, the list of what has already been tried and the priority (P1–P4). "
        "If you do not call create_escalation, the system will create it with your response.",
        ("create_escalation",),
        ("summary", "tried", "priority"),
        _validate_escalation,
        f'{{"summary": "<text>", "tried": ["<text>", "<text>"], "priority": "{_P}"}}',
    ),
}


# --- Prompt and messages -----------------------------------------------------

def _signature(tool: Tool) -> str:
    signature = inspect.signature(tool.function)
    return f"{tool.name}{signature.replace(return_annotation=inspect.Signature.empty)}"


def system_prompt(agent: Agent, tools: dict[str, Tool]) -> str:
    """Prompt generated from the agent definition and the registry."""
    allowed = [tools[n] for n in agent.tools if n in tools]
    callable_ = [f"- {_signature(t)}: {t.description}" for t in allowed if t.reversible]
    proposable = [f"- {_signature(t)}: {t.description}" for t in allowed if not t.reversible]
    parts = [
        f'You are the "{agent.name}" agent of the first-level technical support '
        "of an office network.",
        agent.instructions,
        "ALWAYS answer with a single JSON object, with no additional text.",
        'To use a tool: {"tool": "<name>", "arguments": {...}}',
        f"To finish: an object with the keys {', '.join(agent.keys)}, "
        "exactly in this format (lists are JSON lists; | separates the "
        f"allowed values):\n{agent.format}",
        "Tools you can call:\n" + ("\n".join(callable_) or "- none"),
    ]
    if proposable:
        parts.append("Actions you can propose in 'action' (do not call them):\n"
                     + "\n".join(proposable))
    return "\n\n".join(parts)


def initial_message(state: State) -> str:
    """Incident and what has been found out so far, as JSON."""
    known = {
        key: getattr(state, key)
        for key in ("type", "priority", "cause", "service", "procedure", "citations")
        if getattr(state, key)
    }
    message = {"incident": state.incident, "office": state.office,
               "ticket": state.ticket, "known": known}
    notes = [s.observation for s in state.trace if s.agent == "orchestrator"]
    if notes:
        message["orchestrator_notes"] = notes
    return json.dumps(message, ensure_ascii=False)


def _observation(content: Any) -> dict[str, str]:
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    return {"role": "user", "content": f"Observation: {text}"}


# --- Common loop ---------------------------------------------------------------

def record(state: State, agent: str, tool: str | None,
           arguments: dict, observation: Any) -> None:
    """Adds a step to the trace and counts it for the limit (n = position in the trace)."""
    state.steps += 1
    state.trace.append(Step(len(state.trace) + 1, agent, tool, arguments, observation))


def _is_call(data: dict) -> bool:
    return "tool" in data and set(data) <= {"tool", "arguments"}


def _call(agent: Agent, state: State, tools: dict[str, Tool], data: dict) -> Any:
    """Runs the requested tool if it is allowed and reversible."""
    name, arguments = data.get("tool"), data.get("arguments", {})
    tool = tools.get(name) if name in agent.tools else None
    if tool is None:
        reason = f"tool not allowed for {agent.name}: {name}"
    elif not tool.reversible:
        reason = f"{name} is irreversible: it is not executed; propose it in the 'action' key"
    else:
        try:
            observation = execute(tools, name, arguments)
        except ToolError as error:
            observation = {"error": str(error)}
        record(state, agent.name, name, arguments, observation)
        return observation
    record(state, agent.name, None, {"requested": name, "arguments": arguments},
           {"error": reason})
    return {"error": reason}


def run_agent(agent: Agent, state: State, model: Model,
              tools: dict[str, Tool], max_steps: int = 12) -> AgentOutput:
    """Turns model → tool → observation until a valid output."""
    system = system_prompt(agent, tools)
    messages = [{"role": "user", "content": initial_message(state)}]
    unreadable = 0
    while state.steps < max_steps:
        text = model.generate(system, messages)
        messages.append({"role": "assistant", "content": text})
        try:
            data = extract_json(text)
            if not _is_call(data):
                data = validate_contract(agent, data)
        except ValueError as error:
            unreadable += 1
            record(state, agent.name, None, {}, f"invalid response ({error}): {text}")
            if unreadable >= MAX_UNREADABLE:
                return AgentOutput(None, "unreadable")
            messages.append(_observation(f"invalid response: {error}. "
                                         "Answer with a single JSON object."))
            continue
        unreadable = 0
        record(state, agent.name, None, {}, data)
        if not _is_call(data):
            return AgentOutput(data, "ok")
        if state.steps >= max_steps:
            break
        messages.append(_observation(_call(agent, state, tools, data)))
    return AgentOutput(None, "limit")


# --- Agents: run and apply to the state ----------------------------------------

def knowledge(state: State, model: Model, tools: dict[str, Tool],
              max_steps: int = 12) -> AgentOutput:
    """Procedure and citations; a proposed action is kept in state.actions."""
    output = run_agent(AGENTS["knowledge"], state, model, tools, max_steps)
    if output.data is not None:
        state.procedure = output.data["procedure"]
        state.citations = list(output.data["citations"])
        action = output.data["action"]
        if action is not None:
            state.actions.append(Action(action["tool"], dict(action["arguments"])))
    return output


def classifier(state: State, model: Model, tools: dict[str, Tool],
               max_steps: int = 12) -> AgentOutput:
    """Type and priority (the priority is stored as is; the orchestrator validates it)."""
    output = run_agent(AGENTS["classifier"], state, model, tools, max_steps)
    if output.data is not None:
        state.type = output.data["type"]
        state.priority = output.data["priority"]
    return output


def diagnosis(state: State, model: Model, tools: dict[str, Tool],
              max_steps: int = 12) -> AgentOutput:
    """Probable cause and affected service (or None if it is a device)."""
    output = run_agent(AGENTS["diagnosis"], state, model, tools, max_steps)
    if output.data is not None:
        state.cause = output.data["cause"]
        state.service = output.data["service"]
    return output


def _escalation_already_created(state: State, since: int) -> str | None:
    for step in state.trace[since:]:
        if step.tool == "create_escalation" and isinstance(step.observation, dict):
            if "escalation" in step.observation:
                return step.observation["escalation"]
    return None


def ensure_escalation(state: State, data: dict, tools: dict[str, Tool]) -> str:
    """Creates the escalation with the agent's output; without a ticket if the state's is invalid."""
    for ticket in dict.fromkeys([state.ticket, None]):
        arguments = {"ticket": ticket, "summary": data["summary"],
                     "priority": data["priority"]}
        try:
            observation = execute(tools, "create_escalation", arguments)
        except ToolError as error:
            record(state, "escalation", "create_escalation", arguments, {"error": str(error)})
            continue
        record(state, "escalation", "create_escalation", arguments, observation)
        return observation["escalation"]
    raise ToolError("the escalation could not be created")


def escalation(state: State, model: Model, tools: dict[str, Tool],
               max_steps: int = 12) -> AgentOutput:
    """Handoff to level 2; the code guarantees that an escalation is created."""
    since = len(state.trace)
    output = run_agent(AGENTS["escalation"], state, model, tools, max_steps)
    if output.data is not None:
        escalation_id = _escalation_already_created(state, since)
        output.data["escalation"] = escalation_id or ensure_escalation(
            state, output.data, tools)
    return output

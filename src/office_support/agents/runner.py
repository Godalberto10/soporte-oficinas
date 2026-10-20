"""Common agent loop: model → tool → observation until a valid output (R4)."""

from typing import Any

from office_support.agents.contracts import Agent, AgentOutput, extract_json, validate_contract
from office_support.agents.prompts import initial_message, observation, system_prompt
from office_support.domain.state import State, Step
from office_support.model import Model
from office_support.tools import Tool, ToolError, execute

MAX_UNREADABLE = 2


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
            result = execute(tools, name, arguments)
        except ToolError as error:
            result = {"error": str(error)}
        record(state, agent.name, name, arguments, result)
        return result
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
            messages.append(observation(f"invalid response: {error}. "
                                        "Answer with a single JSON object."))
            continue
        unreadable = 0
        record(state, agent.name, None, {}, data)
        if not _is_call(data):
            return AgentOutput(data, "ok")
        if state.steps >= max_steps:
            break
        messages.append(observation(_call(agent, state, tools, data)))
    return AgentOutput(None, "limit")

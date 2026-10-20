"""The four agents: each one runs the common loop and applies its output to the state."""

from office_support.agents.contracts import AgentOutput
from office_support.agents.definitions import AGENTS
from office_support.agents.runner import record, run_agent
from office_support.domain.state import Action, State
from office_support.model import Model
from office_support.tools import Tool, ToolError, execute


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

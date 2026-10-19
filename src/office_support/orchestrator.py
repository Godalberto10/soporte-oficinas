"""Orchestration by handoff and rules R1–R5 guaranteed in code."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime

from office_support import agents
from office_support.agents import AgentOutput
from office_support.model import Model
from office_support.retrieval import BM25Index, citation, tokenize
from office_support.state import Action, Result, State, Step, Trace
from office_support.tools import Network, Tool, ToolError, create_tools, execute

CRITICAL = frozenset({"vpn", "email", "erp", "files", "intranet"})
PRIORITY_ORDER = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
RESPONSE_TIMES = {"P1": "15 minutes", "P2": "30 minutes",
                  "P3": "2 hours", "P4": "1 business day"}
DEFAULT_PRIORITY = "P3"
SAFETY_PREFIXES = ("explod", "explosion", "smok", "spark", "burn", "melt", "flame")
SAFETY_WORDS = frozenset({"fire", "fires", "ablaze"})  # whole words: not "firewall"
SAFETY_PRIORITY = "P2"


@dataclass
class Context:
    """What the steps of the flow share in one run."""

    state: State
    model: Model
    tools: dict[str, Tool]
    network: Network
    max_steps: int


# --- Utilities ---------------------------------------------------------------

def in_business_hours(moment: datetime) -> bool:
    """Monday to Friday, from 08:00 to 18:00 (18:00 is no longer business hours)."""
    return moment.weekday() < 5 and 8 <= moment.hour < 18


def note(state: State, observation: str) -> None:
    """Orchestrator note: it stays in the trace but does not count for the limit."""
    state.trace.append(Step(len(state.trace) + 1, "orchestrator", None, {}, observation))


def trajectory(trace: list[Step]) -> list[str]:
    """Sequence of agents the run went through (without consecutive repeats)."""
    seen: list[str] = []
    for step in trace:
        if step.agent != "orchestrator" and seen[-1:] != [step.agent]:
            seen.append(step.agent)
    return seen


def most_urgent(a: str | None, b: str | None) -> str | None:
    """The higher of the two priorities (P1 > P4); ignores invalid values."""
    valid = [p for p in (a, b) if p in PRIORITY_ORDER]
    return min(valid, key=PRIORITY_ORDER.__getitem__) if valid else a


# --- Priority and multi-office ---------------------------------------------------

def affected_offices(network: Network, service: str | None) -> list[str]:
    """Offices where the service is not ok."""
    if service is None:
        return []
    return [o for o, statuses in network.services.items()
            if statuses.get(service, "ok") != "ok"]


def minimum_priority(network: Network, office: str, service: str | None) -> str | None:
    """Priority required by the data for the diagnosed service."""
    if len(affected_offices(network, service)) >= 2:
        return "P1"
    if service in CRITICAL:
        return {"down": "P1", "degraded": "P2"}.get(network.services[office].get(service))
    return None


def safety_hazard(incident: str) -> bool:
    """The incident describes a physical danger (explosion, fire, smoke, sparks…)."""
    return any(t in SAFETY_WORDS or t.startswith(SAFETY_PREFIXES) for t in tokenize(incident))


def raise_priority(state: State, network: Network) -> None:
    """Raises (never lowers) the priority to the minimum required by the data and notes it."""
    by_data = minimum_priority(network, state.office, state.service)
    by_safety = SAFETY_PRIORITY if safety_hazard(state.incident) else None
    minimum = most_urgent(by_data, by_safety)
    if minimum is None or most_urgent(minimum, state.priority) == state.priority:
        return
    if minimum == by_data:
        reason = (f"service {state.service} affected in "
                  f"{', '.join(affected_offices(network, state.service))}")
    else:
        reason = "the incident describes a safety hazard"
    note(state, f"priority raised from {state.priority} to {minimum}: {reason}")
    state.priority = minimum


# --- R5: verified citations ------------------------------------------------------

def retrieved_citations(state: State) -> set[str]:
    """Citations of the fragments that search_docs returned in this run."""
    return {
        citation(fragment)
        for step in state.trace
        if step.tool == "search_docs" and isinstance(step.observation, dict)
        for fragment in step.observation.get("fragments", [])
    }


def check_citations(state: State) -> None:
    """Removes (and notes) the citations that were not retrieved in this run."""
    retrieved = retrieved_citations(state)
    valid = [c for c in dict.fromkeys(state.citations) if c in retrieved]
    removed = [c for c in state.citations if c not in retrieved]
    if removed:
        note(state, f"citations removed because they were not retrieved: {', '.join(removed)}")
    state.citations = valid


# --- R2: guardrail -----------------------------------------------------------------

def restarts_done(state: State, service: str) -> int:
    """Successful restarts of a service in this run."""
    return sum(
        1 for s in state.trace
        if s.tool == "restart_service" and s.arguments.get("service") == service
        and not (isinstance(s.observation, dict) and "error" in s.observation)
    )


def _restart_guardrail(arguments: dict, state: State, network: Network,
                       now: datetime) -> str | None:
    service, office = arguments.get("service"), arguments.get("office")
    if office != state.office:
        return f"the office of the action ({office}) is not the office of the incident ({state.office})"
    if restarts_done(state, service) >= 1:
        return f"{service} has already been restarted in this run (maximum 1)"
    if service in CRITICAL and in_business_hours(now):
        if service != state.service:
            return (f"{service} is critical and during business hours only the "
                    f"diagnosed service ({state.service}) can be restarted")
        current = network.services.get(office, {}).get(service)
        if current not in {"down", "degraded"}:
            return f"{service} is critical, it is {current} and it is business hours"
    return None


def guardrail(action: Action, state: State, network: Network, now: datetime) -> str | None:
    """Reason why the action is blocked without asking, or None if it can be confirmed."""
    if action.tool == "restart_service":
        return _restart_guardrail(action.arguments, state, network, now)
    if action.tool == "close_ticket" and action.arguments.get("ticket") != state.ticket:
        return "only the ticket of this incident can be closed"
    return None


# --- End of the run -------------------------------------------------------------------

def _write_answer(state: State, final: str, escalation: str | None, reason: str | None) -> str:
    if final == "resolved":
        return f"{state.procedure}\n\nSources: {', '.join(state.citations)}"
    if final == "escalated":
        return (f"Your incident has been escalated to second level with the ID "
                f"{escalation} (priority {state.priority}). First response time: "
                f"{RESPONSE_TIMES.get(state.priority, 'as per the catalog')}.")
    if final == "rejected":
        return f"The request will not be processed: {reason}."
    return ("Automatic handling could not be completed within the maximum number of "
            "steps. A technician will review the incident.")


def finish(ctx: Context, final: str, escalation: str | None = None,
           reason: str | None = None) -> Result:
    """Sets the final state and builds the Result."""
    state = ctx.state
    state.final = final
    return Result(final=final, answer=_write_answer(state, final, escalation, reason),
                  citations=list(state.citations), trace=state.trace, type=state.type,
                  priority=state.priority, escalation=escalation)


def _reject(ctx: Context, reason: str) -> Result:
    """What is not processed has no priority (decision D1 of milestone 7b)."""
    ctx.state.priority = None
    note(ctx.state, f"rejected: {reason}")
    return finish(ctx, "rejected", reason=reason)


# --- Escalation -----------------------------------------------------------------------

def _escalation_tools(tools: dict[str, Tool], minimum: str | None) -> dict[str, Tool]:
    """create_escalation never uses a lower priority than the state's."""
    original = tools["create_escalation"]

    def create_escalation(ticket: str | None, summary: str, priority: str) -> dict:
        return original.function(ticket=ticket, summary=summary,
                                 priority=most_urgent(priority, minimum))

    return {**tools, "create_escalation": replace(original, function=create_escalation)}


def _automatic_summary(state: State) -> str:
    return (f"Incident in {state.office}: {state.incident}. "
            f"Probable cause: {state.cause or 'not diagnosed'}.")


def escalate(ctx: Context) -> Result:
    """Escalation agent; if its response is unreadable, the code creates the escalation anyway."""
    state = ctx.state
    tools = _escalation_tools(ctx.tools, state.priority)
    output = agents.escalation(state, ctx.model, tools, ctx.max_steps)
    if output.reason == "ok":
        escalation_id = output.data["escalation"]
    elif output.reason == "unreadable" and state.steps < ctx.max_steps:
        note(state, "unreadable response from the escalation agent: automatic escalation")
        data = {"summary": _automatic_summary(state),
                "priority": state.priority or DEFAULT_PRIORITY}
        escalation_id = agents.ensure_escalation(state, data, tools)
    else:
        return finish(ctx, "step_limit_reached")
    state.priority = next(e["priority"] for e in ctx.network.escalations
                          if e["id"] == escalation_id)
    return finish(ctx, "escalated", escalation=escalation_id)


def _after_agent(ctx: Context, output: AgentOutput, agent: str) -> Result | None:
    """limit → step_limit_reached; unreadable → escalation (R4); ok → continue."""
    if output.reason == "limit":
        return finish(ctx, "step_limit_reached")
    if output.reason == "unreadable":
        note(ctx.state, f"2 unreadable responses in a row from {agent}: escalating")
        return escalate(ctx)
    return None


# --- Flow -----------------------------------------------------------------------------

def _invalid_input(network: Network, office: str, ticket: str | None) -> str | None:
    if office not in network.services:
        return f"office {office} does not exist"
    if ticket is not None and not any(t["id"] == ticket for t in network.tickets):
        return f"ticket {ticket} does not exist"
    return None


def _direct_escalation_reason(ctx: Context) -> str | None:
    """Handoff rules after the diagnosis: safety hazard, reopened ticket or multi-office outage."""
    state = ctx.state
    if safety_hazard(state.incident):
        return "safety hazard: it needs a physical repair, which first level does not do"
    if state.ticket is not None:
        reopenings = ctx.network.ticket(state.ticket)["reopenings"]
        if reopenings >= 1:
            return f"ticket {state.ticket} has been reopened {reopenings} time(s)"
    affected = affected_offices(ctx.network, state.service)
    if len(affected) >= 2:
        return f"multi-office outage of {state.service}: {', '.join(affected)}"
    return None


def _execute_action(ctx: Context, action: Action) -> bool:
    """Executes the confirmed action; True if it went well."""
    try:
        observation = execute(ctx.tools, action.tool, action.arguments)
    except ToolError as error:
        observation = {"error": str(error)}
    agents.record(ctx.state, "knowledge", action.tool, dict(action.arguments), observation)
    return "error" not in observation


def _handle_action(ctx: Context, action: Action,
                   confirm: Callable[[Action], bool], now: datetime) -> Result:
    """R2 (guardrail) and R1 (confirmation) before executing an irreversible action."""
    state = ctx.state
    if state.steps >= ctx.max_steps:
        return finish(ctx, "step_limit_reached")
    reason = guardrail(action, state, ctx.network, now)
    if reason is not None:
        note(state, f"action {action.tool} blocked by the guardrail: {reason}")
        return escalate(ctx)
    if not confirm(action):
        note(state, f"action {action.tool} rejected by the user: not executed")
        return escalate(ctx)
    if not _execute_action(ctx, action):
        note(state, f"action {action.tool} failed: escalating")
        return escalate(ctx)
    return finish(ctx, "resolved")


def _flow(ctx: Context, confirm: Callable[[Action], bool],
          now: Callable[[], datetime]) -> Result:
    state, m, t, limit = ctx.state, ctx.model, ctx.tools, ctx.max_steps
    if end := _after_agent(ctx, agents.classifier(state, m, t, limit), "classifier"):
        return end
    if state.type == "out_of_scope":
        return _reject(ctx, "the request is not an office support incident")
    if end := _after_agent(ctx, agents.diagnosis(state, m, t, limit), "diagnosis"):
        return end
    raise_priority(state, ctx.network)
    if reason := _direct_escalation_reason(ctx):
        note(state, f"direct escalation: {reason}")
        return escalate(ctx)
    if end := _after_agent(ctx, agents.knowledge(state, m, t, limit), "knowledge"):
        return end
    check_citations(state)
    if not state.procedure or not state.citations:
        note(state, "no procedure with valid citations: escalating")
        return escalate(ctx)
    if state.actions:
        return _handle_action(ctx, state.actions[-1], confirm, now())
    return finish(ctx, "resolved")


def orchestrate(incident: str, office: str, model: Model,
                confirm: Callable[[Action], bool],
                now: Callable[[], datetime] = datetime.now,
                ticket: str | None = None, max_steps: int = 12, *,
                network: Network | None = None, index: BM25Index | None = None,
                on_step: Callable[[Step], None] | None = None) -> Result:
    """Handles an incident: classifier → diagnosis → knowledge → end | escalation.

    `on_step` (optional) is called with each step as soon as it enters the trace.
    """
    if network is None:
        network = Network.from_directory()
    state = State(incident, office, ticket, trace=Trace(on_step))
    ctx = Context(state, model, {}, network, max_steps)
    if reason := _invalid_input(network, office, ticket):
        return _reject(ctx, reason)
    ctx.tools = create_tools(network, index)
    return _flow(ctx, confirm, now)

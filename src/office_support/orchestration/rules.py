"""Rules guaranteed in code, not in the prompt: input, priority, handoff, R2 and R5.

Each function decides or corrects; the flow (orchestrator.py) only calls them.
"""

from datetime import datetime

from office_support.domain.policy import CRITICAL, in_business_hours, most_urgent
from office_support.domain.state import Action, State, Step
from office_support.retrieval import citation, tokenize
from office_support.tools import Network

SAFETY_PREFIXES = ("explod", "explosion", "smok", "spark", "burn", "melt", "flame")
SAFETY_WORDS = frozenset({"fire", "fires", "ablaze"})  # whole words: not "firewall"
SAFETY_PRIORITY = "P2"


def note(state: State, observation: str) -> None:
    """Orchestrator note: it stays in the trace but does not count for the limit."""
    state.trace.append(Step(len(state.trace) + 1, "orchestrator", None, {}, observation))


# --- Input -------------------------------------------------------------------------

def invalid_input(network: Network, office: str, ticket: str | None) -> str | None:
    """Reason to reject the input (non-existent office or ticket), or None."""
    if office not in network.services:
        return f"office {office} does not exist"
    if ticket is not None and not any(t["id"] == ticket for t in network.tickets):
        return f"ticket {ticket} does not exist"
    return None


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


# --- Handoff -----------------------------------------------------------------------

def direct_escalation_reason(state: State, network: Network) -> str | None:
    """Handoff rules after the diagnosis: safety hazard, reopened ticket or multi-office outage."""
    if safety_hazard(state.incident):
        return "safety hazard: it needs a physical repair, which first level does not do"
    if state.ticket is not None:
        reopenings = network.ticket(state.ticket)["reopenings"]
        if reopenings >= 1:
            return f"ticket {state.ticket} has been reopened {reopenings} time(s)"
    affected = affected_offices(network, state.service)
    if len(affected) >= 2:
        return f"multi-office outage of {state.service}: {', '.join(affected)}"
    return None


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

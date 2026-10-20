"""Web page logic, without Streamlit: app.py only shows what it returns.

The web decides nothing: it calls orchestrate(). For `confirm` to be a button,
the run happens in the background and waits for the person to press a button,
like the terminal with [y/N].
"""

import json
import os
import threading
import urllib.request
from dataclasses import dataclass

from office_support.agents import AGENTS as AGENTS_DEF
from office_support.domain.policy import CRITICAL, OFFICES, RESPONSE_TIMES
from office_support.domain.state import Action, Result, Step
from office_support.model import OLLAMA_DEFAULT_URL, Model, OllamaModel, SimulatedModel
from office_support.orchestration import orchestrate, trajectory
from office_support.tools import Network

SIMULATED = "simulated"


@dataclass(frozen=True)
class Example:
    title: str
    incident: str
    office: str
    ticket: str = ""


EXAMPLES = (
    Example("Asks for confirmation", "I have no internet", "MAD-01", "T-0001"),
    Example("Same symptom, another cause", "I have no internet", "VAL-01", "T-0002"),
    Example("Outage in several offices", "I can't log in to the ERP", "MAD-02", "T-0004"),
    Example("Reopened ticket", "the printer is not printing", "MAD-02", "T-0007"),
    Example("Slow computer", "my computer is slow", "MAD-01"),
    Example("Out of scope", "Can you recommend a restaurant?", "MAD-01"),
    Example("Safety hazard", "The printer has exploded", "MAD-02"),
)


# --- Models ---------------------------------------------------------------------

def ollama_models(url: str | None = None, timeout: float = 1.0) -> list[str]:
    """Models installed in Ollama, or [] if Ollama is not running on this computer."""
    base = (url or os.environ.get("OLLAMA_URL") or OLLAMA_DEFAULT_URL).removesuffix("/v1")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=timeout) as response:
            return sorted(m["name"] for m in json.load(response).get("models", []))
    except (OSError, ValueError, KeyError):
        return []


def create_model(name: str) -> Model:
    """'simulated' or the name of an Ollama model."""
    return SimulatedModel() if name == SIMULATED else OllamaModel(model=name)


# --- A run that stops to ask -------------------------------------------------------

class Execution:
    """A run of orchestrate() in the background that waits for the confirm button.

    It is a single run, like the terminal with [y/N]: the agent that asks is the
    same one that receives the answer. Repeating it does not work with a real model,
    which may answer differently the second time.
    """

    def __init__(self, incident: str, office: str, ticket: str = "",
                 model: Model | None = None) -> None:
        self.pending: Action | None = None
        self.answer: bool | None = None
        self.result: Result | None = None
        self.error: Exception | None = None
        self.steps: list[Step] = []              # live copy of the trace
        self._stopped = threading.Event()        # finished or asking
        self._answered = threading.Event()
        arguments = (incident.strip(), office, model or SimulatedModel(),
                     ticket.strip() or None)
        threading.Thread(target=self._run, args=arguments, daemon=True).start()

    def _run(self, incident: str, office: str, model: Model, ticket: str | None) -> None:
        try:
            self.result = orchestrate(incident, office, model, self._confirm, ticket=ticket,
                                      on_step=self.steps.append)
        except Exception as error:  # the real model does not respond, for example
            self.error = error
        finally:
            self._stopped.set()

    def _confirm(self, action: Action) -> bool:
        self.pending = action
        self._stopped.set()
        self._answered.wait()
        return bool(self.answer)

    def wait(self, seconds: float | None = None) -> None:
        """Until it finishes or asks."""
        self._stopped.wait(seconds)

    def respond(self, yes: bool) -> None:
        """The person's answer to the pending action (R1); with no question, does nothing."""
        if self.pending is None:
            return
        self.answer, self.pending = yes, None
        self._stopped.clear()
        self._answered.set()

    @property
    def done(self) -> bool:
        return self.result is not None or self.error is not None

    def snapshot(self, since: int = 0) -> dict:
        """JSON-ready state for the API: new steps since `since`, question, result."""
        return {"steps": [step_view(s) for s in self.steps[since:]],
                "total": len(self.steps),
                "pending": action_view(self.pending) if self.pending else None,
                "answer": self.answer, "done": self.done,
                "result": result_view(self.result) if self.result else None,
                "error": str(self.error) if self.error else None}


# --- Presentation -----------------------------------------------------------------

def describe_action(action: Action) -> str:
    arguments = ", ".join(f"{k}={v}" for k, v in action.arguments.items())
    return f"{action.tool}({arguments})"


def trajectory_text(result: Result) -> str:
    agents = trajectory(result.trace)
    return " → ".join(agents) if agents else "no agents"


AGENTS = ("classifier", "diagnosis", "knowledge", "escalation")

# Same text as docs/priority-guide.md and same times as the policy (the tests check
# it): the web only explains them, it decides nothing.
PRIORITY_CRITERIA = {
    "P1": "affects more than one office, or a critical service is down",
    "P2": "affects an entire office, or a critical service is degraded",
    "P3": "an employee cannot work and there is no alternative",
    "P4": "an inconvenience with an alternative (another printer, webmail…)",
}
FINAL_MEANING = {
    "resolved": "first level solved it with a documented and cited procedure.",
    "escalated": "a second-level technician handles it, receiving a summary of what has "
                 "already been tried and the escalation ID.",
    "rejected": "it is not processed: the input is not valid or it is not a support incident.",
    "step_limit_reached": "the allowed steps ran out; a technician will review the incident.",
}


def explain_priority(priority: str) -> str:
    return (f"{priority}: {PRIORITY_CRITERIA[priority]}. First response within "
            f"{RESPONSE_TIMES[priority]}.")


def stages(result: Result) -> list[tuple[str, bool]]:
    """The four agents in order and whether they acted in this run."""
    acted = set(trajectory(result.trace))
    return [(agent, agent in acted) for agent in AGENTS]


def outages() -> dict[str, dict[str, str]]:
    """Services that are not ok, by office (initial state of data/)."""
    services = Network.from_directory().services
    return {o: {s: st for s, st in services[o].items() if st != "ok"} for o in OFFICES}


def trace_rows(trace: list[Step]) -> list[dict[str, str]]:
    """One row per step, to show it as a table."""
    return [{"n": str(s.n), "agent": s.agent, "tool": s.tool or "—",
             "observation": str(s.observation)[:300]} for s in trace]


# --- JSON views for the browser (server.py) -------------------------------------

ROLES = {
    "classifier": "Decides the incident type and its priority.",
    "diagnosis": "Finds the probable cause by checking services, devices and tickets.",
    "knowledge": "Finds the documented procedure and proposes actions.",
    "escalation": "Hands the incident over to second level with a summary.",
}
RULES = {
    "R1": "Confirmation: an irreversible action only runs if a person confirms it.",
    "R2": "Guardrail: a critical service in business hours is only restarted if it is "
          "the diagnosed one and it is down or degraded; at most 1 restart.",
    "R3": "Step limit: 12 steps per run.",
    "R4": "Errors as observations: tool errors, disallowed tools and unreadable JSON "
          "go back to the agent; 2 unreadable in a row → escalation.",
    "R5": "Checked citations: only fragments retrieved in this run can be cited.",
}
_NOTE_RULES = (("rejected by the user", "R1"), ("guardrail", "R2"), ("unreadable", "R4"),
               ("citations removed", "R5"), ("no procedure with valid citations", "R5"),
               ("priority raised", "priority"), ("direct escalation", "handoff"),
               ("rejected:", "input"))


def note_rule(text: str) -> str | None:
    """Which rule an orchestrator note shows (R1–R5, priority, handoff or input)."""
    return next((rule for words, rule in _NOTE_RULES if words in text), None)


def _is_error(observation: object) -> bool:
    return isinstance(observation, dict) and "error" in observation


def step_kind(step: Step) -> str:
    """note | tool | blocked | invalid | call | output."""
    if step.agent == "orchestrator":
        return "note"
    if step.tool is not None:
        return "tool"
    if "requested" in step.arguments:
        return "blocked"
    if isinstance(step.observation, str):
        return "invalid"
    if isinstance(step.observation, dict) and "tool" in step.observation:
        return "call"
    return "output"


def step_view(step: Step) -> dict:
    kind = step_kind(step)
    rule = note_rule(str(step.observation)) if kind == "note" else None
    if kind in {"blocked", "invalid"} or (kind == "tool" and _is_error(step.observation)):
        rule = "R4"
    return {"n": step.n, "agent": step.agent, "tool": step.tool, "kind": kind, "rule": rule,
            "arguments": step.arguments, "observation": step.observation}


def action_view(action: Action) -> dict:
    return {"tool": action.tool, "arguments": action.arguments,
            "text": describe_action(action)}


def result_view(result: Result) -> dict:
    return {"final": result.final, "answer": result.answer.split("\n\nSources:")[0],
            "citations": result.citations, "type": result.type,
            "priority": result.priority, "escalation": result.escalation,
            "trajectory": trajectory(result.trace), "steps": result_steps(result)}


def result_steps(result: Result) -> int:
    """Steps that count for the limit (orchestrator notes do not)."""
    return sum(1 for s in result.trace if s.agent != "orchestrator")


def meta() -> dict:
    """Everything the page needs to draw itself; it decides nothing."""
    return {"offices": OFFICES, "examples": [vars(e) for e in EXAMPLES],
            "services": Network.from_directory().services, "critical": sorted(CRITICAL),
            "agents": [{"name": a, "role": ROLES[a], "tools": list(AGENTS_DEF[a].tools),
                        "output": list(AGENTS_DEF[a].keys)} for a in AGENTS],
            "rules": RULES, "priorities": PRIORITY_CRITERIA, "response_times": RESPONSE_TIMES,
            "finals": FINAL_MEANING, "models": [SIMULATED, *ollama_models()],
            "max_steps": 12}

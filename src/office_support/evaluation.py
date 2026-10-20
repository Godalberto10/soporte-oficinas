"""Evaluation: cases with expected result and trajectory (milestone 7).

The expected outcome of each case is defined by the project author applying their
rules, without looking at the code. The script of each case only plays the model.
"""

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime

from office_support.domain.state import Action, Result
from office_support.model import Model, ScriptedModel, SimulatedModel
from office_support.orchestration import orchestrate, trajectory
from office_support.tools import Network

MONDAY_10 = datetime(2026, 10, 12, 10, 0)
ABBREVIATIONS = {"classifier": "C", "diagnosis": "D", "knowledge": "K", "escalation": "E"}
COLUMNS = ("final", "type", "priority", "trajectory")


# --- Script pieces (responses of a ScriptedModel) ----------------------------

def _j(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def _call(tool: str, **arguments) -> str:
    return _j({"tool": tool, "arguments": arguments})


def _classify(type_: str, priority: str) -> str:
    return _j({"type": type_, "priority": priority, "reason": "based on the incident"})


def _diagnose(service: str | None, office: str, cause: str) -> list[str]:
    check = (_call("check_service", service=service, office=office)
             if service else _call("check_device", device_id="PC-VAL01-002"))
    return [check, _j({"cause": cause, "service": service,
                       "evidence": ["observed with the tool"]})]


def _resolve(query: str, citation: str, action: dict | None = None) -> list[str]:
    return [_call("search_docs", query=query, k=5),
            _j({"procedure": "Follow the steps of the cited article.",
                "citations": [citation], "action": action})]


def _restart(service: str, office: str) -> dict:
    return {"tool": "restart_service",
            "arguments": {"service": service, "office": office}}


def _escalate(priority: str) -> list[str]:
    return [_j({"summary": "not solved at first level", "tried": ["diagnosis"],
                "priority": priority})]


# --- Cases -----------------------------------------------------------------------

@dataclass(frozen=True)
class Expected:
    final: str
    type: str | None
    priority: str | None
    trajectory: str


@dataclass(frozen=True)
class Case:
    n: int
    name: str
    incident: str
    office: str
    ticket: str | None
    confirm: bool
    script: tuple[str, ...]
    expected: Expected
    simulated: bool = True  # also included in the run with SimulatedModel


INTERNET = "I have no internet"
_VPN_MAD01 = (_classify("network", "P3"),
              *_diagnose("vpn", "MAD-01", "vpn down in MAD-01"))

CASES: tuple[Case, ...] = (
    Case(1, "internet MAD-01, confirms", INTERNET, "MAD-01", "T-0001", True,
         (*_VPN_MAD01, *_resolve("vpn down", "docs/kb-network-01.md#Steps",
                                 _restart("vpn", "MAD-01"))),
         Expected("resolved", "network", "P1", "C-D-K")),
    Case(2, "internet MAD-01, rejects", INTERNET, "MAD-01", "T-0001", False,
         (*_VPN_MAD01, *_resolve("vpn down", "docs/kb-network-01.md#Steps",
                                 _restart("vpn", "MAD-01")), *_escalate("P1")),
         Expected("escalated", "network", "P1", "C-D-K-E")),
    Case(3, "internet VAL-01, broken card", INTERNET, "VAL-01", "T-0002", False,
         (_classify("network", "P3"),
          *_diagnose(None, "VAL-01", "faulty network card in PC-VAL01-002"),
          *_resolve("faulty network card cable", "docs/kb-network-02.md#Steps")),
         Expected("resolved", "network", "P3", "C-D-K")),
    Case(4, "printer MAD-02, reopened", "the printer is not printing", "MAD-02",
         "T-0007", False,
         (_classify("printer", "P4"),
          *_diagnose("printing", "MAD-02", "printing degraded"), *_escalate("P4")),
         Expected("escalated", "printer", "P4", "C-D-E")),
    Case(5, "ERP MAD-02, several offices", "I can't log in to the ERP", "MAD-02",
         "T-0004", False,
         (_classify("app_access", "P2"),
          *_diagnose("erp", "MAD-02", "erp down"), *_escalate("P2")),
         Expected("escalated", "app_access", "P1", "C-D-E")),
    Case(6, "email BCN-01, model says P4", "email takes a long time to arrive",
         "BCN-01", "T-0006", True,
         (_classify("email", "P4"),
          *_diagnose("email", "BCN-01", "email degraded in BCN-01"),
          *_resolve("email takes long to arrive service degraded",
                    "docs/kb-email-01.md#Steps", _restart("email", "BCN-01"))),
         Expected("resolved", "email", "P2", "C-D-K")),
    Case(7, "restaurant", "Can you recommend a restaurant?", "MAD-01", None, False,
         (_classify("out_of_scope", "P4"),),
         Expected("rejected", "out_of_scope", None, "C")),
    Case(8, "nonexistent office", INTERNET, "SEV-01", None, False, (),
         Expected("rejected", None, None, "")),
    Case(9, "made-up citation", INTERNET, "MAD-01", None, False,
         (*_VPN_MAD01, *_resolve("vpn down", "docs/kb-network-07.md#Steps"),
          *_escalate("P1")),
         Expected("escalated", "network", "P1", "C-D-K-E"), simulated=False),
    Case(10, "proposes restarting the ERP", INTERNET, "MAD-01", None, False,
         (*_VPN_MAD01, *_resolve("vpn down", "docs/kb-network-01.md#Steps",
                                 _restart("erp", "MAD-01")), *_escalate("P1")),
         Expected("escalated", "network", "P1", "C-D-K-E"), simulated=False),
    Case(11, "slow computer", "my computer is slow", "MAD-01", None, False,
         (_classify("hardware", "P4"),
          _j({"cause": "slow device", "service": None,
              "evidence": ["no service affected"]}),
          *_resolve("slow computer restart", "docs/kb-hardware-03.md#Steps"),
          *_escalate("P4")),
         Expected("resolved", "hardware", "P4", "C-D-K")),
)


# --- Run and compare ---------------------------------------------------------------

class CountingModel:
    """Wraps a model and counts how many times it is called."""

    def __init__(self, model: Model) -> None:
        self.model = model
        self.calls = 0

    def generate(self, system: str, messages: list[dict]) -> str:
        self.calls += 1
        return self.model.generate(system, messages)


@dataclass
class Evaluation:
    case: Case
    result: Result
    network: Network
    model_calls: int
    questions: list[Action] = field(default_factory=list)

    def obtained(self) -> Expected:
        abbreviations = "-".join(ABBREVIATIONS[a] for a in trajectory(self.result.trace))
        return Expected(self.result.final, self.result.type,
                        self.result.priority, abbreviations)

    def hits(self) -> dict[str, bool]:
        obtained = self.obtained()
        return {c: getattr(obtained, c) == getattr(self.case.expected, c) for c in COLUMNS}


def evaluate(case: Case, model: Model | None = None) -> Evaluation:
    """Runs a case with a fresh Network; without a model, uses the case's script."""
    network = Network.from_directory()
    counted = CountingModel(model or ScriptedModel(list(case.script)))
    questions: list[Action] = []

    def confirm(action: Action) -> bool:
        questions.append(action)
        return case.confirm

    result = orchestrate(case.incident, case.office, counted, confirm,
                         now=lambda: MONDAY_10, ticket=case.ticket, network=network)
    return Evaluation(case, result, network, counted.calls, questions)


# --- Table for the report -------------------------------------------------------------

def _cell(expected: str | None, obtained: str | None) -> str:
    text = expected or "—"
    return text if expected == obtained else f"{text} ✘ ({obtained or '—'})"


def table(evaluations: list[Evaluation]) -> str:
    """Markdown table: expected per column, with ✘ (obtained) if it does not match."""
    rows = ["| # | Case | Final | Type | Priority | Trajectory |",
            "|---|---|---|---|---|---|"]
    for ev in evaluations:
        exp, obt = ev.case.expected, ev.obtained()
        cells = [_cell(getattr(exp, c), getattr(obt, c)) for c in COLUMNS]
        rows.append(f"| {ev.case.n} | {ev.case.name} | " + " | ".join(cells) + " |")
    totals = [sum(ev.hits()[c] for ev in evaluations) for c in COLUMNS]
    rows.append("| | **Hits** | " + " | ".join(
        f"{t}/{len(evaluations)}" for t in totals) + " |")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluation with my cases.")
    parser.add_argument("--model", choices=["script", "simulated"], default="script")
    args = parser.parse_args(argv)
    if args.model == "script":
        evaluations = [evaluate(c) for c in CASES]
    else:
        evaluations = [evaluate(c, SimulatedModel()) for c in CASES if c.simulated]
    print(table(evaluations))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

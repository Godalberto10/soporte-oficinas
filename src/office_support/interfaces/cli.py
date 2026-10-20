"""office-support command: handles an incident from the terminal."""

import argparse
import json
import sys
from collections.abc import Callable

from office_support.domain.state import Action, Result, Step
from office_support.model import HFModel, Model, OllamaModel, SimulatedModel
from office_support.orchestration import orchestrate

YES_ANSWERS = {"y", "yes"}
OBSERVATION_LENGTH = 160


def _arguments() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="office-support",
        description="First-level technical support for the office network.")
    parser.add_argument("incident", help="text of the employee's incident")
    parser.add_argument("--office", required=True, help="MAD-01, MAD-02, BCN-01 or VAL-01")
    parser.add_argument("--ticket", help="ticket id, e.g. T-0007")
    parser.add_argument("--model", choices=["simulated", "hf", "ollama"], default="simulated",
                        help="simulated (no token, default), hf (Hugging Face) "
                             "or ollama (local model)")
    parser.add_argument("--trace", action="store_true", help="shows the steps")
    return parser


def confirmer(read: Callable[[str], str]) -> Callable[[Action], bool]:
    """confirm() that asks in the terminal; no answer (EOF) is False."""
    def confirm(action: Action) -> bool:
        arguments = ", ".join(f"{k}={v}" for k, v in action.arguments.items())
        try:
            answer = read(f"Confirm {action.tool}({arguments})? [y/N] ")
        except EOFError:
            return False
        return answer.strip().lower() in YES_ANSWERS
    return confirm


def _step(step: Step) -> str:
    action = (f"{step.tool}({json.dumps(step.arguments, ensure_ascii=False)})"
              if step.tool else "response" if step.agent != "orchestrator" else "note")
    observation = (step.observation if isinstance(step.observation, str)
                   else json.dumps(step.observation, ensure_ascii=False))
    if len(observation) > OBSERVATION_LENGTH:
        observation = observation[:OBSERVATION_LENGTH] + "…"
    return f"  {step.n:>2}. [{step.agent}] {action} -> {observation}"


def format_result(result: Result, trace: bool = False) -> str:
    """Text shown at the end."""
    lines = [f"Final: {result.final}",
             f"Type: {result.type or '-'} · Priority: {result.priority or '-'}"]
    if result.escalation:
        lines.append(f"Escalation: {result.escalation}")
    lines += ["", "Answer to the employee:", result.answer]
    if trace:
        lines += ["", "Trace:", *(_step(s) for s in result.trace)]
    return "\n".join(lines)


def _create_model(name: str) -> Model:
    models = {"hf": HFModel, "ollama": OllamaModel}
    return models.get(name, SimulatedModel)()


def main(argv: list[str] | None = None, read: Callable[[str], str] = input) -> int:
    """Entry point of the office-support command."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    args = _arguments().parse_args(argv)
    try:
        result = orchestrate(args.incident, args.office, _create_model(args.model),
                             confirmer(read), ticket=args.ticket)
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    print(format_result(result, args.trace))
    return 0

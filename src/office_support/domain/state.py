"""State shared between agents and the result of a run."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Step:
    """One step of the trace: a model response or a tool call."""

    n: int
    agent: str
    tool: str | None
    arguments: dict[str, Any]
    observation: Any


class Trace(list):
    """List of steps that also tells a listener about each new step (live web)."""

    def __init__(self, on_step: Callable[[Step], None] | None = None) -> None:
        super().__init__()
        self._on_step = on_step

    def append(self, step: Step) -> None:
        super().append(step)
        if self._on_step is not None:
            self._on_step(step)


@dataclass
class Action:
    """A tool call that an agent proposes to execute."""

    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class State:
    """What has been found out so far; each agent receives it and completes it."""

    incident: str
    office: str
    ticket: str | None = None
    type: str | None = None
    priority: str | None = None
    cause: str | None = None
    service: str | None = None
    procedure: str | None = None
    citations: list[str] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    trace: list[Step] = field(default_factory=list)
    steps: int = 0
    final: str | None = None


@dataclass
class Result:
    """Output of orchestrate(): final state, answer to the employee and trace."""

    final: str
    answer: str
    citations: list[str] = field(default_factory=list)
    trace: list[Step] = field(default_factory=list)
    type: str | None = None
    priority: str | None = None
    escalation: str | None = None

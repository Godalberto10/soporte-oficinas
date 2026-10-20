"""What the model receives: system prompt, first message and observations."""

import inspect
import json
from typing import Any

from office_support.agents.contracts import Agent
from office_support.domain.state import State
from office_support.tools import Tool


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


def observation(content: Any) -> dict[str, str]:
    """A tool result (or an error) as the next user message."""
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    return {"role": "user", "content": f"Observation: {text}"}

"""Agents: output contracts, definitions, prompts, common loop and the four specialists.

The public names are re-exported here: `from office_support import agents` and
`agents.classifier(...)` work without knowing the internal module.
"""

from office_support.agents.contracts import (
    PROPOSABLE_ACTIONS,
    Agent,
    AgentOutput,
    extract_json,
    validate_contract,
)
from office_support.agents.definitions import AGENTS
from office_support.agents.prompts import initial_message, system_prompt
from office_support.agents.runner import MAX_UNREADABLE, record, run_agent
from office_support.agents.specialists import (
    classifier,
    diagnosis,
    ensure_escalation,
    escalation,
    knowledge,
)

__all__ = [
    "AGENTS", "MAX_UNREADABLE", "PROPOSABLE_ACTIONS", "Agent", "AgentOutput", "classifier",
    "diagnosis", "ensure_escalation", "escalation", "extract_json", "initial_message",
    "knowledge", "record", "run_agent", "system_prompt", "validate_contract",
]

"""The four specialist agents: role, instructions, allowed tools and output contract."""

from office_support.agents.contracts import (
    PROPOSABLE_ACTIONS,
    Agent,
    validate_classifier,
    validate_diagnosis,
    validate_escalation,
    validate_knowledge,
)
from office_support.domain.policy import PRIORITIES, SERVICE_DESCRIPTIONS, SERVICES, TYPES


def _options(values: frozenset[str]) -> str:
    return "|".join(sorted(values))


_P = _options(PRIORITIES)

AGENTS: dict[str, Agent] = {
    "classifier": Agent(
        "classifier",
        "You decide the incident type and its priority.\n"
        f"Types: {', '.join(sorted(TYPES))}. Use 'other' for support incidents "
        "without a category and 'out_of_scope' if the request is not about office "
        "technical support.\n"
        "Priorities: P1 affects more than one office or a critical service is "
        "down; P2 affects an entire office or a critical service is degraded; P3 an "
        "employee cannot work and there is no alternative; P4 an inconvenience with "
        "an alternative.\n"
        "Critical services: vpn, email, erp, files, intranet.",
        ("search_tickets",),
        ("type", "priority", "reason"),
        validate_classifier,
        f'{{"type": "{_options(TYPES)}", "priority": "{_P}", "reason": "<text>"}}',
    ),
    "diagnosis": Agent(
        "diagnosis",
        "You find out the probable cause by checking the real status of the services, "
        "the devices and the tickets. Give the affected service (or null if it is a "
        "device) and, in evidence, what you have observed. If the outage affects "
        "more than one office, say so in the evidence.\n"
        "Before concluding, check at least one tool (for example, check_service "
        "for the related service in the office of the incident) and do not invent "
        "causes you have not observed.\n"
        "Services of each office:\n"
        + "\n".join(f"- {s}: {d}" for s, d in SERVICE_DESCRIPTIONS.items()),
        ("check_service", "check_device", "search_tickets"),
        ("cause", "service", "evidence"),
        validate_diagnosis,
        f'{{"cause": "<text>", "service": "{_options(SERVICES)}" or null, '
        '"evidence": ["<text>", "<text>"]}',
    ),
    "knowledge": Agent(
        "knowledge",
        "You search the knowledge base for the procedure that solves the diagnosed "
        "cause and write it for the employee. Your first turn is ALWAYS a call to "
        "search_docs with the diagnosed cause. Only cite fragments you have retrieved "
        "with search_docs, in the format docs/<file>.md#<section>. "
        "If you find no procedure, return procedure null and citations []. "
        "Irreversible actions are NOT called: they are proposed in 'action' as "
        "{\"tool\": ..., \"arguments\": {...}} and a person will confirm them.",
        ("search_docs", "restart_service", "close_ticket"),
        ("procedure", "citations", "action"),
        validate_knowledge,
        '{"procedure": "<text>" or null, "citations": ["docs/<file>.md#<section>"], '
        f'"action": null or {{"tool": "{_options(PROPOSABLE_ACTIONS)}", '
        '"arguments": {...}}}',
    ),
    "escalation": Agent(
        "escalation",
        "You prepare the handoff to second level: a clear summary of the incident and "
        "its cause, the list of what has already been tried and the priority (P1–P4). "
        "If you do not call create_escalation, the system will create it with your response.",
        ("create_escalation",),
        ("summary", "tried", "priority"),
        validate_escalation,
        f'{{"summary": "<text>", "tried": ["<text>", "<text>"], "priority": "{_P}"}}',
    ),
}

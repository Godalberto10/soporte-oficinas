"""Tools over the simulated state of the network and their registry."""

import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

from office_support.retrieval import BM25Index

DATA_PATH = Path(__file__).resolve().parents[2] / "data"
PRIORITIES = {"P1", "P2", "P3", "P4"}
MAX_K = 10


class ToolError(Exception):
    """A tool failure; the orchestrator records it as an observation."""


@dataclass
class Network:
    """Simulated state of the network. Changes are only made in memory."""

    services: dict[str, dict[str, str]]
    inventory: list[dict]
    tickets: list[dict]
    escalations: list[dict] = field(default_factory=list)

    @classmethod
    def from_directory(cls, path: Path = DATA_PATH) -> "Network":
        """Loads a fresh copy of services, inventory and tickets."""
        def load(name: str) -> Any:
            return json.loads((Path(path) / name).read_text(encoding="utf-8"))

        return cls(load("services.json"), load("inventory.json"), load("tickets.json"))

    def statuses_of(self, office: str) -> dict[str, str]:
        """Statuses of the services of an office, or ToolError."""
        _require_text(office, "office")
        if office not in self.services:
            raise ToolError(f"unknown office: {office}")
        return self.services[office]

    def device(self, device_id: str) -> dict:
        """Inventory record of a device, or ToolError."""
        _require_text(device_id, "device_id")
        for device in self.inventory:
            if device["id"] == device_id:
                return device
        raise ToolError(f"unknown device: {device_id}")

    def ticket(self, ticket_id: str) -> dict:
        """Ticket by id, or ToolError."""
        _require_text(ticket_id, "ticket")
        for ticket in self.tickets:
            if ticket["id"] == ticket_id:
                return ticket
        raise ToolError(f"unknown ticket: {ticket_id}")


@dataclass
class Tool:
    """Registry entry: what it does, whether it is reversible and the function to call."""

    name: str
    description: str
    reversible: bool
    function: Callable[..., dict]


def _require_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"'{name}' must be a non-empty string")
    return value


def _service_statuses(network: Network, service: str, office: str) -> dict[str, str]:
    statuses = network.statuses_of(office)
    _require_text(service, "service")
    if service not in statuses:
        raise ToolError(f"unknown service: {service}")
    return statuses


def check_service(network: Network, service: str, office: str) -> dict:
    """Status (ok|degraded|down) of a service in an office."""
    statuses = _service_statuses(network, service, office)
    return {"service": service, "office": office, "status": statuses[service]}


def check_device(network: Network, device_id: str) -> dict:
    """Inventory record of a device."""
    return dict(network.device(device_id))


def search_tickets(network: Network, office: str | None = None,
                   symptom: str | None = None) -> dict:
    """Tickets that match the office and/or contain the symptom."""
    if office is not None:
        network.statuses_of(office)
    if symptom is not None:
        _require_text(symptom, "symptom")
    found = [
        dict(t) for t in network.tickets
        if (office is None or t["office"] == office)
        and (symptom is None or symptom.lower() in t["symptom"].lower())
    ]
    return {"tickets": found}


def create_escalation(network: Network, ticket: str | None, summary: str,
                      priority: str) -> dict:
    """Records an escalation to second level and returns its id."""
    if ticket is not None:
        network.ticket(ticket)
    _require_text(summary, "summary")
    if priority not in PRIORITIES:
        raise ToolError(f"invalid priority: {priority} (P1–P4)")
    escalation_id = f"ESC-{len(network.escalations) + 1:04d}"
    network.escalations.append({"id": escalation_id, "ticket": ticket,
                                "summary": summary, "priority": priority})
    return {"escalation": escalation_id, "ticket": ticket, "priority": priority}


def restart_service(network: Network, service: str, office: str) -> dict:
    """Restarts a service of an office: it is left ok."""
    statuses = _service_statuses(network, service, office)
    previous = statuses[service]
    statuses[service] = "ok"
    return {"service": service, "office": office,
            "previous_status": previous, "status": "ok"}


def close_ticket(network: Network, ticket: str, resolution: str) -> dict:
    """Closes an open or reopened ticket, saving the resolution."""
    data = network.ticket(ticket)
    _require_text(resolution, "resolution")
    if data["status"] == "closed":
        raise ToolError(f"ticket {ticket} is already closed")
    data["status"] = "closed"
    data["resolution"] = resolution
    return {"ticket": ticket, "status": "closed", "resolution": resolution}


def search_docs(index: BM25Index, query: str, k: int = 3) -> dict:
    """Most relevant fragments of docs/ for the query (BM25)."""
    _require_text(query, "query")
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= MAX_K:
        raise ToolError(f"'k' must be an integer between 1 and {MAX_K}")
    return {"fragments": index.search(query, k)}


_CATALOG: list[tuple[Callable[..., dict], str, bool]] = [
    (check_service, "Status ok|degraded|down of a service in an office.", True),
    (check_device, "Inventory record (type, office, model, status) of a device.", True),
    (search_tickets, "Tickets filtered by office and/or by symptom text.", True),
    (create_escalation, "Creates a second-level escalation with a summary and priority P1–P4.",
     True),
    (restart_service, "Restarts a service of an office. IRREVERSIBLE.", False),
    (close_ticket, "Closes a ticket with its resolution. IRREVERSIBLE.", False),
]


def create_tools(network: Network, index: BM25Index | None = None) -> dict[str, Tool]:
    """Registry of tools bound to a network and to a document index."""
    tools = {
        f.__name__: Tool(f.__name__, description, reversible, partial(f, network))
        for f, description, reversible in _CATALOG
    }
    if index is None:
        index = BM25Index.from_directory()
    tools["search_docs"] = Tool(
        "search_docs",
        "Searches the knowledge base; returns fragments {doc, section, text}.",
        True, partial(search_docs, index))
    return tools


def execute(tools: dict[str, Tool], name: str, arguments: dict[str, Any]) -> dict:
    """Single call point: every usage failure becomes a ToolError."""
    tool = tools.get(name) if isinstance(name, str) else None
    if tool is None:
        raise ToolError(f"unknown tool: {name}")
    if not isinstance(arguments, dict):
        raise ToolError(f"the arguments of {name} must be an object")
    try:
        inspect.signature(tool.function).bind(**arguments)
    except TypeError as error:
        raise ToolError(f"invalid arguments for {name}: {error}") from None
    return tool.function(**arguments)

"""Support policy shared by every layer: types, services, priorities and hours."""

from datetime import datetime

OFFICES = ("MAD-01", "MAD-02", "BCN-01", "VAL-01")
TYPES = frozenset({"network", "printer", "app_access", "email", "hardware", "other",
                   "out_of_scope"})
SERVICES = frozenset({"vpn", "email", "erp", "files", "intranet",
                      "printing", "guest_wifi"})
CRITICAL = frozenset({"vpn", "email", "erp", "files", "intranet"})
SERVICE_DESCRIPTIONS = {  # same as docs/service-catalog.md (a test checks it)
    "vpn": "Office tunnel to the data center and internet access",
    "email": "Corporate email (Outlook and webmail)",
    "erp": "Management application (orders, invoicing, warehouse)",
    "files": "Shared folders of the office",
    "printing": "Print queue server",
    "guest_wifi": "Wireless network for visitors",
    "intranet": "Internal portal and password self-service",
}

PRIORITIES = frozenset({"P1", "P2", "P3", "P4"})
PRIORITY_ORDER = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
RESPONSE_TIMES = {"P1": "15 minutes", "P2": "30 minutes",
                  "P3": "2 hours", "P4": "1 business day"}
DEFAULT_PRIORITY = "P3"


def in_business_hours(moment: datetime) -> bool:
    """Monday to Friday, from 08:00 to 18:00 (18:00 is no longer business hours)."""
    return moment.weekday() < 5 and 8 <= moment.hour < 18


def most_urgent(a: str | None, b: str | None) -> str | None:
    """The higher of the two priorities (P1 > P4); ignores invalid values."""
    valid = [p for p in (a, b) if p in PRIORITY_ORDER]
    return min(valid, key=PRIORITY_ORDER.__getitem__) if valid else a

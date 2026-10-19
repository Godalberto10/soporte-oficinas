# Service restart policy

## Services
- **Critical services:** `vpn`, `email`, `erp`, `files`, `intranet`.
- **Non-critical services:** `printing`, `guest_wifi`.
- **Business hours:** Monday to Friday, 08:00 to 18:00 (local time).

## Rules
1. Restarting a service is an **irreversible** action: it cuts off open
   sessions. It always requires explicit confirmation before it runs.
2. A **critical** service can only be restarted during business hours if:
   - it is the service identified in the diagnosis of the incident, and
   - its current status is `down` or `degraded`.
   If both conditions are not met, the restart is blocked without asking.
3. Outside business hours, and for non-critical services, confirmation
   is enough.
4. At most **one restart per service** is done in each support case. If it does
   not resolve the issue, it is escalated to second level.
5. Nothing is restarted when the outage affects more than one office: it is P1
   and second level handles it.

## If the restart is rejected
If the person confirming rejects the restart, it is not run and the incident is
escalated to second level according to `escalation-procedure.md`.

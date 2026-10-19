# Escalation procedure to second level

## When to escalate
- The outage affects more than one office (always with priority P1).
- The ticket has already been reopened at least once (`reopenings >= 1`).
- There is no documented procedure in the knowledge base.
- The proposed action (restart, closure) was rejected or did not resolve the issue.
- The problem is a hardware fault that requires replacement or repair.
- The incident describes a safety hazard (explosion, fire, smoke, sparks):
  escalate at once with at least P2 and tell the employee to unplug the device
  only if it is safe and to keep away from it.

## What to include
1. Summary of the incident: office, symptom and probable cause.
2. List of what has already been tried at first level.
3. Priority according to `priority-guide.md`:
   - **P1**: affects more than one office, or a critical service is `down`.
   - **P2**: affects an entire office, or a critical service is `degraded`.
   - **P3**: an employee cannot work and there is no alternative.
   - **P4**: an inconvenience with an alternative (another printer, webmail…).
4. Ticket number, if there is one.

## Services
- **Critical services:** `vpn`, `email`, `erp`, `files`, `intranet`.
- **Business hours:** Monday to Friday, 08:00 to 18:00 (local time).
- Outside business hours only P1 is handled, through the second-level on-call team.

## Communicating with the employee
Tell the employee that their incident has been escalated, give them the
escalation identifier and the first response time according to `service-catalog.md`.

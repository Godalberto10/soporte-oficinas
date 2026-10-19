# Cannot log in to the ERP because the service is down

## Symptoms
- Opening the ERP shows "service unavailable" or the screen stays blank.
- It affects every employee in the office.
- It can happen in several offices at the same time.

## Cause
The ERP server is `down` or `degraded`. When it fails in more than one
office, the source is in the data center, not in the office.

## Steps
1. Check the status of `erp` in the employee's office.
2. Search for open tickets with the same symptom in other offices.
3. If `erp` is down in more than one office: multi-office outage, priority
   P1, escalate to second level without restarting (see `escalation-procedure.md`).
4. If it only affects one office, a restart of `erp` can be requested
   according to `restart-policy.md`.
5. Tell the employee the response time according to `service-catalog.md`.

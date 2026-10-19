# Email is slow to arrive or is not sent: email service degraded

## Symptoms
- Messages take many minutes to arrive or stay stuck in the outbox.
- Outlook shows "trying to connect".
- It affects several employees in the office.

## Cause
The office's `email` service is `degraded` (saturated sending queue)
or `down`. It is a critical service.

## Steps
1. Check the status of `email` in the office.
2. In the meantime, recommend webmail as an alternative.
3. If the status is `degraded` or `down`, a restart of `email` can be
   requested according to `restart-policy.md` (during business hours only if
   it is the diagnosed service).
4. If it does not improve within 15 minutes, escalate to second level.

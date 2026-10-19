# No printer in the office is printing: printing service degraded

## Symptoms
- No printer in the office receives jobs, or jobs take several minutes.
- The error "print server unavailable" appears.
- The printers turn on normally and show no warnings.

## Cause
The office's print queue server is `degraded` or `down`.
`printing` is a non-critical service, so it can also be restarted
during business hours with confirmation.

## Steps
1. Check the status of the `printing` service in the office.
2. If it is `degraded` or `down`, request a restart of `printing`
   (requires confirmation, see `restart-policy.md`).
3. Ask the employee to resend the job after the restart.
4. If the ticket had already been reopened before, do not repeat the restart:
   escalate to second level.

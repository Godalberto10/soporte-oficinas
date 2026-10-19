# No internet or application access because the VPN is down

## Symptoms
- The employee says "I have no internet" or "nothing loads".
- The ERP, the intranet and the shared folders do not open.
- Several colleagues in the same office notice the same thing at the same time.
- The computer's network icon shows as connected.

## Cause
The office's VPN tunnel to the data center is down. Corporate traffic
(and internet access, which goes through the data center) is cut off
for the whole office. If `check_service("vpn", office)` returns `down`
or `degraded`, this is the most likely cause.

## Steps
1. Check the status of the `vpn` service in the employee's office.
2. Check whether other offices also have the `vpn` down; if so, the outage
   is multi-office: escalate with P1 without restarting anything.
3. If it only affects this office and the service is `down` or `degraded`,
   a restart of `vpn` can be requested according to `restart-policy.md`
   (requires confirmation; during business hours only if it is the diagnosed service).
4. After the restart, ask the employee to close and reopen the browser.
5. If internet access is not back within 10 minutes, escalate to second level.

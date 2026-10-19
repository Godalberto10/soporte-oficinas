# Priority guide

## Services
- **Critical services:** `vpn`, `email`, `erp`, `files`, `intranet`.
- **Non-critical services:** `printing`, `guest_wifi`.
- **Business hours:** Monday to Friday, 08:00 to 18:00 (local time).

## Levels
- **P1**: affects more than one office, or a critical service is `down`.
- **P2**: affects an entire office, or a critical service is `degraded`.
- **P3**: an employee cannot work and there is no alternative.
- **P4**: an inconvenience with an alternative (another printer, webmail…).

## How to decide
1. Always apply the highest level that the incident meets.
2. Check the actual status of the services before setting the priority:
   the employee's perception is not enough.
3. If the data require a higher priority than the one proposed (for example,
   P3 with a critical service `down`), the priority is raised and this is
   recorded in the trace.
4. Safety first: if the employee describes an explosion, fire, smoke, sparks
   or something burning, the priority is at least P2, whatever the device.

## Examples
- `erp` down in MAD-02 and BCN-01 at the same time → P1 (several offices).
- `email` degraded in one office → P2.
- A laptop that won't turn on and no loan device available → P3.
- A jammed printer with another one available in the office → P4.
- A printer that has exploded or is giving off smoke → P2 (safety hazard).

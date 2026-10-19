# Service catalog

## Services
- **Critical services:** `vpn`, `email`, `erp`, `files`, `intranet`.
- **Non-critical services:** `printing`, `guest_wifi`.
- **Business hours:** Monday to Friday, 08:00 to 18:00 (local time).

| Service | Description | Critical |
|---|---|---|
| `vpn` | Office tunnel to the data center and internet access | yes |
| `email` | Corporate email (Outlook and webmail) | yes |
| `erp` | Management application (orders, invoicing, warehouse) | yes |
| `files` | Shared folders of the office | yes |
| `printing` | Print queue server | no |
| `guest_wifi` | Wireless network for visitors | no |
| `intranet` | Internal portal and password self-service | yes |

## Response times
| Priority | Criterion | First response | Resolution target |
|---|---|---|---|
| P1 | affects more than one office, or a critical service is `down` | 15 minutes | 4 hours |
| P2 | affects an entire office, or a critical service is `degraded` | 30 minutes | 8 hours |
| P3 | an employee cannot work and there is no alternative | 2 hours | 2 business days |
| P4 | an inconvenience with an alternative (another printer, webmail…) | 1 business day | 5 business days |

Response times count within the working schedule, except P1, which the
second-level on-call team also handles at night and at weekends.

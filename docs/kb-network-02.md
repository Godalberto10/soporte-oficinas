# A single computer without connection because of a faulty network card

## Symptoms
- The employee says "I have no internet", but their colleagues can browse.
- The network icon shows "cable disconnected" or "no network".
- The office's services (`vpn`, `intranet`) are `ok`.

## Cause
The computer's network card is faulty or the cable is damaged. It is a
local hardware problem, not an issue with the office's services. In the
inventory the device appears with status `faulty_network_card`.

## Steps
1. Check the status of `vpn` in the office; if it is `ok`, rule out a general outage.
2. Check the device record in the inventory with `check_device`.
3. Ask the employee to try another cable and another network socket.
4. If the inventory shows a faulty network card, offer a loan laptop
   and escalate to second level to replace the card.
5. Do not restart office services: they do not fix a local fault.

# The printer is not printing because of a paper jam or lack of toner

## Symptoms
- Jobs stay in the queue and do not come out.
- The printer's display shows a paper jam or low toner warning.
- Only one printer fails; the other printers in the office work.

## Cause
Physical printer fault: jammed paper or an empty toner cartridge.
In the inventory it appears with status `paper_jam` or `out_of_toner`.

## Steps
1. Check the printer record with `check_device`.
2. If there is a paper jam, tell the employee to open the front tray and remove
   the paper following the arrows on the panel.
3. If it is out of toner, request a cartridge from the office manager.
4. In the meantime, send the job to another printer in the office
   (alternative available: priority P4).
5. If it still does not print after clearing the jam, escalate to second level.

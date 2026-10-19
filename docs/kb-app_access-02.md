# Cannot log in to an application because of an expired password or a locked account

## Symptoms
- The application responds "incorrect username or password" or "account locked".
- Colleagues in the same office can log in normally.
- The application's service is `ok`.

## Cause
The employee's password has expired (every 90 days) or the account has been
locked after five failed login attempts.

## Steps
1. Check the status of the application's service; if it is not `ok`,
   follow `kb-app_access-01.md`.
2. Tell the employee to use the password self-service portal on the
   intranet.
3. If the account is locked, wait 15 minutes for it to unlock
   automatically.
4. If they still cannot log in, escalate to second level for an account review.

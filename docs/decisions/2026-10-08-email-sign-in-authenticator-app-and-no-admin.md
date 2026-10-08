# Sign in by email, an authenticator app in place of the emailed code, a cooldown per address, and no Django admin (2026-10-08)

Until now a user signed in with a username and password, then a six-digit
code sent to their email address; the application counted no failed
passwords, leaving nginx as the only brake; and the Django admin site at
`/admin/` was installed, reachable by a staff user through the same
sign-in, with every app carrying an `admin.py`.

## Decision

Four changes, made together:

- **The email address is the sign-in name.** `EmailBackend` is the only
  authentication backend, matching `email__iexact`; a partial unique
  constraint on `Lower("email")` (blank excluded, for the inactive system
  user) keeps each address to one user, and every form that edits the
  address requires it and checks the same rule. The username stays as a
  display name, which is what the rest of the application uses it for.
- **An authenticator app (TOTP) replaces the emailed code for a user who
  sets one up**, under Settings > Security. It does not sit on top of the
  emailed code: with the app enrolled, no email is sent and the emailed
  step is closed to that user. The secret is stored encrypted with a key
  derived from `SECRET_KEY`, as the AI keys are; the last accepted step is
  recorded so a code is good once. The firm can require the app
  (`Firm.require_authenticator`): a middleware then confines an
  unenrolled user to the Security page until they enrol. A lost phone is
  an administrator's reset from the Users page, or the
  `reset_authenticator` command.
- **Failed sign-ins start a cooldown**, counted per email address as
  typed, in a table (`SignInThrottle`) rather than the per-process cache:
  five free, then 30 seconds doubling to 15 minutes. Wrong authenticator
  codes count toward it; the password is not checked during it; a
  completed sign-in clears it; an hour's quiet forgets it. Addresses that
  belong to nobody are counted the same, so the cooldown does not say
  which exist.
- **The Django admin is removed**: `django.contrib.admin` is out of
  `INSTALLED_APPS`, its URLs and the `admin_login` redirect are gone, and
  every `admin.py` is deleted. Repairs are the application's screens, two
  commands (`changepassword`, `reset_authenticator`) and the shell.

## Alternatives

- **Keep the emailed code as a fallback behind the app.** Rejected: the
  app would then be only as strong as the inbox, which is exactly what it
  is meant to improve on. The cost, a lost phone, is met by the
  administrator's reset and the command for the last administrator.
- **Recovery codes.** Not built. The firm has an administrator a user can
  reach, and a reset that falls back to the emailed code covers the case
  with less to explain and nothing to store.
- **Count failures in the cache.** The cache is per process
  (`config/settings.py` says so), so three gunicorn workers would allow
  three times the failures. A table is one row per address and shared.
- **Key the cooldown on the client address.** nginx already limits by
  address. Keying the application's count on the typed address is what
  stops a password being guessed against one account from many addresses;
  the trade, that someone who knows an address can keep its owner waiting
  up to 15 minutes at a time, is accepted and written into the security
  checklist.
- **Keep the admin behind the new sign-in.** Rejected by the request
  itself. The admin bypassed every rule the application enforces (the
  last-administrator guard, what deleting a matter removes, the
  permission flags), and its one operator use, the Django-Q task pages,
  is covered by `qinfo`, `qmonitor` and the shell.

## Consequences

- `client.login(username=...)` in a test reaches `EmailBackend` and finds
  nobody; tests sign in with `force_login`.
- The sub-package models (`invoicing/*/models.py`, `activity/*/models.py`,
  `matters/*/models.py`) are imported from their app's `models.py`. The
  `admin.py` files had been importing them at start-up as a side effect;
  without that, the registry lacked them until a URL import loaded them,
  and the test database's serialisation failed on trust's relation to
  `invoicing.Payment`.
- Rotating `SECRET_KEY` makes every stored authenticator unreadable. Such
  a row counts as no authenticator: the user gets the emailed code (or
  the Security page, if the app is required) and enrols again.
- Deploying this needs the two migrations (`accounts 0019`,
  `settings 0011`) and a restart of both services. The nginx login
  location no longer needs to name `/admin/login`; an installed site file
  that still does is harmless.
- There is no `collectstatic` step any more: the admin's assets were the
  only files it collected.
- Operators lose the admin's change-history pages. `simple_history` still
  records every change; the rows are reached from the shell.

## Evidence

- `apps/accounts/backends.py`, `apps/accounts/totp.py`,
  `apps/accounts/views.py`, `apps/accounts/middleware.py`
  (`AuthenticatorRequiredMiddleware`), `apps/settings/security/views.py`.
- `apps/accounts/migrations/0019_authenticator_and_sign_in_throttle.py`,
  `apps/settings/migrations/0011_firm_require_authenticator.py`.
- `apps/accounts/tests/test_signin.py`, `test_authenticator.py`,
  `test_no_admin.py`.
- `apps/invoicing/models.py` and the comments at the foot of
  `apps/activity/models.py` and `apps/matters/models.py`.

## Related

- [Wrong sign-in codes are counted on the code, not the session](2026-10-01-sign-in-attempts-on-the-code-row.md),
  which this keeps for the emailed code.
- [Identity and access](../dev/subsystems/identity-and-access.md), the
  Sign-in section.
- [Users and permissions](../admin/users.md) and the
  [Security checklist](../admin/security.md).

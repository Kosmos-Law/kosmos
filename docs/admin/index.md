# Operator guide

For the person who installs Kosmos and keeps it running for a firm.

## Install

The quickest path is the installer script, described in the
[README](https://github.com/Kosmos-Law/kosmos/blob/dev/README.md#installation).
It sets up a development instance with one command, or a production server
with `--prod --domain HOST`.

- [Install by hand](install-manual.md): every step the script performs,
  for other platforms or for repairing a partial install.
- [Configuration](configuration.md): the `config/.env` file and its two
  templates.
- [Troubleshooting](troubleshooting.md): dependency and migration problems.

The systemd, nginx and gunicorn templates are documented beside the files
themselves, in
[`deploy/README.md`](https://github.com/Kosmos-Law/kosmos/blob/dev/deploy/README.md).

## Integrations

Each integration stays off until its keys are set.

- [Google Workspace](integrations/google.md): Calendar, Contacts and Drive.
- [Intakes from forwarded email](integrations/inbound-email.md): Mailgun
  inbound routing.
- [Claude Desktop](integrations/claude-desktop.md): per-user access through
  an MCP server.

## Not written yet

These pages are planned and do not exist yet: payments (LawPay, Stripe,
Confido), AI providers, outbound email, object storage, Gmail sync, the
background worker and its schedules, users and permissions, upgrading,
backup and restore, monitoring, and security.

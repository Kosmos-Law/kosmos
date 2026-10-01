# Operator guide

For the person who installs Kosmos and keeps it running for a firm.

A new server goes in this order: install, configure outgoing email (nobody
can sign in without it), then add the integrations the firm uses, then set
up backups and monitoring before real work begins.

## Install

- [Install with the script](install.md): one command for a development
  machine or a production server, and what it changes on the machine.
- [Install by hand](install-manual.md): every step the script performs,
  for other platforms or for repairing a partial install.
- [Configuration](configuration.md): the `config/.env` file and its two
  templates.

The systemd, nginx and gunicorn templates are documented beside the files
themselves, in
[`deploy/README.md`](https://github.com/Kosmos-Law/kosmos/blob/dev/deploy/README.md).

## Integrations

Each integration stays off until it is configured.

- [Outgoing email](integrations/email.md): SMTP, sender addresses, and why
  sign-in depends on it.
- [File storage](integrations/storage.md): local disk or an S3-compatible
  bucket, and how files are served.
- [AI providers and research](integrations/ai.md): API keys, semantic
  search, CourtListener, scheduled AI jobs, and what data leaves the
  server.
- [Online payments](integrations/payments.md): LawPay, Stripe or Confido,
  webhooks, and settlement.
- [Google Workspace](integrations/google.md): the shared Google setup,
  Calendar, Contacts and Drive.
- [Gmail sync](integrations/gmail.md): case email from each user's
  mailbox.
- [Intakes from forwarded email](integrations/inbound-email.md): Mailgun
  inbound routing.
- [Drafting with LibreOffice](integrations/libreoffice.md): the companion
  extension.
- [Claude Desktop](integrations/claude-desktop.md): per-user access
  through an MCP server.

## Operate

- [Background worker](worker.md): what it does, what breaks without it,
  schedules, and the commands an operator uses.
- [Monitoring](monitoring.md): health checks, logs, error emails and
  failed tasks.
- [Backup and restore](backup.md): what holds a firm's data and how to
  protect it.
- [Upgrading](upgrading.md): moving an install to newer code.
- [Troubleshooting](troubleshooting.md): dependency and migration
  problems.

## Not written yet

Users and permissions, and a security checklist for production.

## Reference

[Environment variables](../reference/environment.md),
[management commands](../reference/commands.md) and
[scheduled jobs](../reference/schedules.md) are generated from the code.

<p align="center">
  <img src="static/images/kosmos-mark.svg" alt="Kosmos logo" width="96" height="96">
</p>

# Kosmos

Kosmos is a web-based practice management application for small law firms,
with case building and AI-assisted legal analysis built in. It is a Django
application backed by PostgreSQL, with HTMX for interactivity and a
background worker for syncs, OCR and AI jobs. The emphasis is a clean,
simple interface and the efficient execution of core functionality.

## What it does

**Practice management.** Matters, contacts, tasks and deadlines, a calendar,
time entries and expenses, invoicing (including LEDES export), trust
accounting, and client intakes. Multiple users and time-keepers, each with
their own rates and permissions.

**Billing and collection.** Hourly and flat-fee matters, invoices sent by
email with online payment links, and card payments collected through
LawPay/AffiniPay or Stripe with trust and operating accounts routed
separately. Clients can be asked for trust deposits the same way.

**Case building.** Documents with OCR text extraction, highlights and
citations, a chronological fact timeline, witness tracking, case law pulled
from CourtListener, and a Research tab that assembles full-opinion briefs
with citation chasing.

**AI assistance.** Per-matter chat with a context system that selects the
relevant documents, notes, case law and prior conversations for each question
within the model's budget. An agentic mode can search the matter and
CourtListener itself, and chat can write back into the record: facts,
witnesses, notes and saved case law. Nightly summaries and a daily plan are
generated automatically. Claude and Gemini are supported.

**Notes and drafting.** A rich-text notes editor with folders, matter-scoped
and general libraries that feed the AI, and AI-proposed edits applied to
LibreOffice drafts as native tracked changes.

**Google Workspace.** Calendar and Contacts sync, Gmail labels mapped to
matters with a per-matter email view, and Drive folders mapped to document
categories so PDFs flow into the matter automatically.

**Claude Desktop.** An MCP server exposes notes, matters, conversations and
financial data to Claude Desktop (see [Claude Desktop access](docs/admin/integrations/claude-desktop.md)).

## Installation

On a fresh Ubuntu or Debian machine, one command stands up a working
development instance:

```bash
git clone https://github.com/Kosmos-Law/kosmos.git
cd kosmos
scripts/install.sh
```

The script installs the system packages, PostgreSQL with the `pgvector` and
`pg_trgm` extensions, [uv](https://docs.astral.sh/uv/) and the Python
environment, generates `config/.env` with a fresh secret key, runs
migrations and the post-migration commands, and asks for the first
superuser. It uses `sudo` where it has to and never runs as root. It is
idempotent: re-run it after pulling new code or after a failure and it only
does what is still missing. An existing `config/.env` is always kept.

Then start the app in two terminals:

```bash
.venv/bin/python manage.py runserver
.venv/bin/python manage.py qcluster
```

| Option | Effect |
| --- | --- |
| `--db-name`, `--db-user`, `--db-password` | database settings (default `kosmos` / `kosmos` / `kosmos`); values in an existing `config/.env` win |
| `--no-superuser` | skip the superuser prompt |
| `--seed-intake-forms` | also run `manage.py seed_intake_forms` |
| `--yes` | skip the confirmation prompt |
| `--dry-run` | print every command instead of running it; rendered files are left in a temp dir for inspection |
| `--force` | production only: overwrite system files that differ from the templates and remove nginx's default site |

For a non-interactive superuser, export `DJANGO_SUPERUSER_USERNAME`,
`DJANGO_SUPERUSER_EMAIL` and `DJANGO_SUPERUSER_PASSWORD` before running.

### Production

```bash
scripts/install.sh --prod --domain kosmos.example.com
sudo certbot --nginx -d kosmos.example.com
```

`--prod` generates a production `config/.env` (`DEBUG=False`, a generated
database password, the hostname in `ALLOWED_HOSTS` and friends), installs
nginx, renders the systemd units and nginx site from
[`deploy/`](deploy/README.md), runs `collectstatic`, and starts
`law.socket`, `law.service` and `qcluster.service`. Certbot adds TLS; later
runs of the installer leave a certbot-managed file alone. Then fill in the
blanks in `config/.env` (SMTP, `ADMINS`, API keys, object storage) and
restart the two services.

### Manual installation and configuration

Every step the script performs, written out for other platforms or for
debugging, plus troubleshooting and the Google Calendar, Contacts and Drive
setup that happens after the app is running:
**[docs/admin/install-manual.md](docs/admin/install-manual.md)**, with
[configuration](docs/admin/configuration.md),
[troubleshooting](docs/admin/troubleshooting.md) and
[Google Workspace setup](docs/admin/integrations/google.md) beside it.

Nix users: `flake.nix` and `process-compose.yaml` provide a development shell
instead; note their database defaults (`aletheia` on port 5433) differ from
`config/.env.dev` (`kosmos` on 5432).

## Configuration

The application reads only `config/.env`. Two templates live beside it:
`config/.env.dev` holds safe, credential-free development defaults, and
`config/.env.example` documents every variable, including the optional
integrations (Google, AI providers, CourtListener, payments, Mailgun inbound
email, DigitalOcean Spaces). Each integration stays off until its keys are
set.

## Development

```bash
.venv/bin/python -m pytest -n auto        # run the test suite
pre-commit run --all-files                # ruff + djlint, the same checks the workflow defines
```

The repository carries two workflows (lint and tests, and the installer on
a clean Ubuntu runner in both modes) as the definition of the checks, but
GitHub Actions is switched off on this repository: run them locally before
opening a pull request. Conventions for contributors and coding agents are
in [AGENTS.md](AGENTS.md).

## Documentation

The documentation lives in [`docs/`](docs/index.md) and is built into a site
with Zensical (see [Writing documentation](docs/dev/writing-docs.md)). It
has a section for each reader:

- [Operator guide](docs/admin/index.md): install, configure, connect
  integrations, troubleshoot
- [User guide](docs/guide/index.md): working in the application
- [Developer guide](docs/dev/index.md): conventions and how the subsystems
  work
- [Reference](docs/reference/index.md) and
  [Decisions](docs/decisions/index.md)

The gunicorn, systemd and nginx templates are documented in
[deploy/README.md](deploy/README.md).

## License

Kosmos is released under the GNU Affero General Public License v3
(see [LICENSE](LICENSE)). Contributions are welcome under the
[Code of Conduct](CODE_OF_CONDUCT.md); security issues go through
[SECURITY.md](SECURITY.md).

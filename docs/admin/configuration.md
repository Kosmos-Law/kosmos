# Configuration

The project uses a number of environment variables to store either
sensitive information or instance-specific configuration.

Two `.env` templates are provided in the configuration directory:

- `config/.env.dev` contains safe, working development defaults. It uses local
  file storage, console email, fake payments, and no external API credentials.
- `config/.env.example` is the comprehensive reference for configuring other
  environments and optional integrations.

For local development, create the private environment file with:

```bash
cp config/.env.dev config/.env
```

The application only reads `config/.env`; `.env.dev` is a copy-ready template
and is never loaded directly. Its PostgreSQL defaults are database `kosmos`,
user `kosmos`, and password `kosmos` on `localhost:5432`. Replace
`SECRET_KEY` with a fresh value (for example
`python3 -c 'import secrets; print(secrets.token_urlsafe(50))'`).

For staging or production, start from `config/.env.dev` as well and change
`DEBUG`, `ENV`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `PUBLIC_BASE_URL`, the
database values and the email settings, using `config/.env.example` as the
reference for every optional integration. The `[string]` placeholders in
`.env.example` are not blank, so do not copy that file as-is: a placeholder
API key enables the integration it belongs to.

For a credential-free local setup, keep `STORAGE_BACKEND=local` and
`EMAIL_BACKEND=console`. Set `STORAGE_BACKEND=s3` to use DigitalOcean Spaces,
or `EMAIL_BACKEND=smtp` for real email delivery; credentials for each service
are only required when that mode is selected. Never expose a production local
`MEDIA_ROOT` directly through a web server because it contains confidential
client documents.

Leave `SEMANTIC_AUTO_INDEX=False` until `GEMINI_API_KEY` is set. Saving a
record with it on queues embedding tasks that need Gemini, and without a key
the worker keeps retrying tasks that cannot succeed.

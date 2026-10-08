# Decisions

Dated records of design choices: what was decided, what was tried first,
and why. They explain the code as it is and stop settled questions from
being reopened by accident. Read the record for an area before changing
it, and before rebuilding anything a record says was retired.

A record describes the moment it was written. When a later decision
replaces it, the old record stays and gains a link to the new one. How
to write one is in [Writing documentation](../dev/writing-docs.md#decision-records).

## Platform and tooling

- [JavaScript ships without a build step (2026-02-28)](2026-02-28-javascript-without-a-build-step.md)
- [Ruff replaces black, isort, pycln and flake8 (2026-03-10)](2026-03-10-ruff-replaces-the-lint-stack.md)
- [`ENV` is a switch of its own, not `DEBUG` (2026-06-24)](2026-06-24-env-is-not-debug.md)
- [Local storage by default, media unrouted, the logo excepted (2026-08-03)](2026-08-03-local-storage-and-unrouted-media.md)
- [Shared state lives in the database cache, not the default one (2026-08-17)](2026-08-17-shared-state-in-the-database-cache.md)
- [Civil dates come from `timezone.localdate()` (2026-08-25)](2026-08-25-civil-dates-from-localdate.md)
- [A failing queue task stops after ten attempts (2026-08-25)](2026-08-25-task-queue-attempts-are-capped.md)
- [Schema the migrations do not own (2026-09-30)](2026-09-30-schema-the-migrations-do-not-own.md)
- [Reference pages are generated and drift-tested (2026-10-01)](2026-10-01-generated-reference-pages.md)
- [Three branches, and the checks run locally (2026-10-05)](2026-10-05-three-branches-and-no-actions.md)

## Front-end conventions

- [Visibility and polling inside htmx swaps (2026-07-29)](2026-07-29-visibility-and-polling-inside-swaps.md)
- [A list's sort key is checked on write and again on read (2026-10-02)](2026-10-02-sort-keys-validated-twice.md)
- [How a modal closes and how toasts stack (2026-10-05)](2026-10-05-modal-and-toast-rules.md)
- [Yes/No selects, not checkboxes, over one `YESNO_CHOICES` (2026-10-05)](2026-10-05-yes-no-selects.md)

## Access, matters and contacts

- [The in-form client wizard keeps its draft in the session (2026-07-01)](2026-07-01-client-wizard-keeps-its-draft-in-the-session.md)
- [The matter owns the client relationship (2026-07-02)](2026-07-02-the-matter-owns-the-client.md)
- [Closing a matter unlinks its mirrors and starts the chat clock (2026-08-01)](2026-08-01-closing-a-matter-unlinks-mirrors-and-starts-the-chat-clock.md)
- [Drive folder mappings replace the per-proceeding folder link (2026-08-21)](2026-08-21-drive-folder-mappings-replace-proceeding-folders.md)
- [Matter membership is enforced from the URL (2026-10-01)](2026-10-01-matter-membership-from-the-url.md)
- [Wrong sign-in codes are counted on the code, not the session (2026-10-01)](2026-10-01-sign-in-attempts-on-the-code-row.md)
- [The last active administrator cannot be demoted or deactivated (2026-10-02)](2026-10-02-last-administrator-cannot-be-removed.md)
- [The Reports permission alone opens the reports, and starts off (2026-10-02)](2026-10-02-reports-permission-opens-the-reports.md)
- [What deleting a matter or a contact removes (2026-10-02)](2026-10-02-what-deleting-a-matter-or-contact-removes.md)
- [The "two shells" redesign is abandoned (2026-10-05)](2026-10-05-two-shells-redesign-abandoned.md)
- [Sign in by email, an authenticator app in place of the emailed code, a cooldown per address, and no Django admin (2026-10-08)](2026-10-08-email-sign-in-authenticator-app-and-no-admin.md)

## Tasks, calendar, email and intakes

- [An event's location is one short line (2026-07-07)](2026-07-07-event-location-is-one-short-line.md)
- [Client forms replace the website questionnaire (2026-07-25)](2026-07-25-client-forms-replace-the-website-questionnaire.md)
- [Intake email: forwarding rules and canned replies (2026-07-28)](2026-07-28-intake-email-rules.md)
- [The Gmail mirror: one mailbox per user, Gmail is the archive (2026-07-31)](2026-07-31-gmail-mirror-per-user-mailboxes.md)
- [Quick add never guesses a matter, and AI entry is a firm opt-in (2026-08-04)](2026-08-04-quick-add-never-guesses-a-matter.md)
- [Tasks panel retired, user chips stay (2026-08-04)](2026-08-04-tasks-panel-retired-user-chips-stay.md)
- [Date presets are re-derived from their label on every read (2026-08-07)](2026-08-07-semantic-date-presets.md)
- [Google Calendar sync: Kosmos wins on conflicts (2026-10-02)](2026-10-02-google-calendar-sync-rules.md)

## Billing and trust

- [Online payments: provisional until settled, and the processor switch (2026-06-25)](2026-06-25-online-payments-provisional-and-the-processor-switch.md)
- [Trust available: client-level, pending, computed in one place (2026-07-03)](2026-07-03-trust-available-client-level-pending.md)
- [Invoice emails carry a link, and the stored PDF is what the link serves (2026-07-10)](2026-07-10-invoice-emails-carry-a-link.md)
- [One category per time entry, folder-style, not labels (2026-07-16)](2026-07-16-one-category-per-entry.md)
- [Work on a draft invoice is work in progress, not unbilled (2026-10-02)](2026-10-02-draft-invoice-work-is-work-in-progress.md)
- [Fee-agreement wording lives on the Firm record, not in templates (2026-10-02)](2026-10-02-firm-wording-lives-in-settings.md)
- [A payment's side effects are changed through the payment, never by cascade (2026-10-02)](2026-10-02-trust-payment-and-withdrawal-one-movement.md)
- [Retainer plans are abandoned; the billing arrangement stays per matter (2026-10-05)](2026-10-05-retainer-plans-abandoned.md)

## AI and research

- [Scheduled AI jobs run only when ENV is prod (2026-07-30)](2026-07-30-scheduled-ai-jobs-run-only-in-production.md)
- [AI writes are fenced blocks, applied at once (2026-08-09)](2026-08-09-fenced-write-blocks.md)
- [Effort tiers and answer streaming, tried and reverted (2026-08-14)](2026-08-14-effort-tiers-and-streaming-reverted.md)
- [AI chat runs on threads, research runs on the queue (2026-08-17)](2026-08-17-chat-on-threads-research-on-the-queue.md)
- [The user picks which cases a research run reads (2026-08-18)](2026-08-18-research-selection-gate.md)
- [The token estimate is 2.5 characters per token (2026-08-20)](2026-08-20-token-estimate-at-two-and-a-half-chars.md)
- [What the AI says about money follows what the screens show (2026-10-02)](2026-10-02-ai-money-follows-the-screens.md)
- [The Plan chat and the nightly auto threads are retired (2026-10-06)](2026-10-06-plan-chat-and-auto-threads-retired.md)
- [The Research tab is retired (2026-10-06)](2026-10-06-research-tab-retired.md)
- [AI is optional (2026-10-06)](2026-10-06-ai-is-optional.md)
- [Claude Desktop: packaging roadmap](claude-desktop-roadmap.md)
- [Research Chat (retired 2026-08-16)](research-chat-retired.md)

## Notes, drafts and documents

- [The Drive mirror: append-only, PDF-only, read-only on Drive (2026-08-01)](2026-08-01-drive-mirror-contract.md)
- [Drafts are companion-first over a Drive `.odt` (2026-08-06)](2026-08-06-drafts-are-companion-first.md)
- [Notes are app-owned and carry no AI knobs (2026-08-11)](2026-08-11-notes-are-app-owned-with-no-ai-knobs.md)
- [The case-law viewer renders CourtListener's HTML unsanitised (2026-10-02)](2026-10-02-opinion-html-rendered-as-is.md)

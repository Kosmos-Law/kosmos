# The Gmail mirror: one mailbox per user, Gmail is the archive (2026-07-31)

Emails reach a matter by Gmail label: a message labelled with the
matter's label is synced onto the matter's Emails tab. The first version
(2026-07-30) read one mailbox through a single shared token file and
stored the label's id on the matter. A firm has several mailboxes, each
with its own copy of a thread and its own label ids, and a message often
sits in two of them. The design that settled the next day, and the rules
that have been added to it since, all follow from one choice: the rows
in Kosmos are a mirror for reading and for the AI, and Gmail stays the
archive of record.

## Decision

- **One mailbox per user**, `GmailAccount`, connected by each user on the
  integrations page. The matter's contract is the label *name*
  (`Matter.gmail_label_name`); each account resolves that name to its own
  label id at sync time, and the sync provisions missing labels in every
  mailbox that allows it.
- **One row per (account, matter, message)**, collapsed into one
  chronology by RFC 822 `message_id` through `EmailQuerySet.dedup()`,
  first-synced row wins. The duplicate rows are provenance: unlabelling in
  one mailbox drops only that mailbox's row.
- **Rows hold text only.** `body_text` and `body_html` for the preview,
  attachment metadata and extracted text, never the bytes. `gmail_url`
  deep-links to the original. Rows are immutable once synced.
- **A matter with no label is left alone.** Closing a matter clears the
  label name but removes no rows; the sync's removal paths touch only
  matters that still have a label; an empty choice in the link modal is
  refused rather than read as an unlink. Unlink is the one confirmed
  action that removes a matter's emails (2026-10-02).
- **Promote-to-document is a copy.** The email is rendered to PDF and
  filed as a Correspondence `Document` on the Kosmos side of the sync
  boundary, where nothing in Gmail can touch it, which is what makes it
  safe to carry highlights.
- **On-demand refresh runs on a daemon thread**, not the shared task
  queue, and signals completion through the cross-process status cache
  (2026-08-03).

## Alternatives

The single shared token lived one day, 2026-07-30 to 2026-07-31. Storing
the label id was replaced by the name because ids differ per mailbox.
Keeping one row per message across mailboxes would have lost the
provenance that makes per-mailbox unlabelling safe. Storing attachment
bytes or rendering emails as Documents on sync was not taken; Gmail
holds the file. The refresh first polled a queued task and stranded the
button behind a wedged attachment batch; the thread fixed that.

The label-less rule was a comment in `Matter.save()` before it was true:
until 2026-10-02 an empty label choice, or a message trashed in a
mailbox, emptied a closed matter's file.

## Consequences

- Renaming a label in Gmail detaches it: the old name lands in
  `missing_labels` and a fresh, empty label is created under the linked
  name. The name is the contract.
- Two removal paths with different scope (`_remove_email()` for one
  account and matter, `_remove_everywhere()` for a trashed message across
  label-linked matters); neither touches a matter with no label. Only
  `remove_matter_emails()`, called only by Unlink, does.
- Rows from before per-user mailboxes carry a null `account` until
  `adopt_gmail_account` claims them.
- A change to the parser needs `refresh_email_bodies` or a full resync
  to reach old rows, since the sync skips rows it has. A promoted
  email's `ai_context` flips to `never` so the AI reads the Document.

## Evidence

- Commit "feat(mail): multi-user Gmail sync into one matter chronology"
  (2026-07-31): "The label NAME is the cross-mailbox contract ... The
  same message held in two mailboxes yields one row per account; list,
  preview and AI context collapse duplicates via EmailQuerySet.dedup."
- `Email` docstring in `apps/mail/models.py`: "Text-only record: Gmail
  remains the archive of record"; `GmailAccount` docstring: "Replaces the
  single shared token file."
- `apps/mail/promote.py` module docstring: "The Document is a copy across
  the sync boundary: nothing Gmail-side (unlabel, trash, sync error) can
  touch it, which is what makes it safe to carry highlights."
- Commits "fix(mail): a matter with no Gmail label keeps its emails, and
  the label picker shows only what is the user's" and "fix(mail): a
  message trashed in a mailbox is not removed from a matter with no
  label" (2026-10-02); the docstrings in `apps/mail/google.py` that
  state the rule.
- Commit "fix(mail): refresh runs on a thread, not the shared django-q
  queue" (2026-08-03).

## Related

- [Email and intakes](../dev/subsystems/email-and-intakes.md): the sync,
  the Emails tab, and the removal paths.
- [Gmail sync](../admin/integrations/gmail.md) in the operator guide.
- [Closing a matter unlinks its mirrors](2026-08-01-closing-a-matter-unlinks-mirrors-and-starts-the-chat-clock.md).

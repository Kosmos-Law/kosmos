# Client forms replace the website questionnaire (2026-07-25)

Before July 2026 a prospective client's questionnaire reached Kosmos
from a firm's website, which posted the answers to JSON endpoints under
`/api/` guarded by a shared key (`apps/intakes/api_views.py`). The
questions lived on the website, the mapping of dispute types to practice
areas lived in the Kosmos code as one firm's table, and staff could not
change a question without a web developer. On 2026-07-25 Kosmos got its
own form builder: staff build a questionnaire, send a link to the
prospective client, and read the answers on the intake.

## Decision

- **An answer keeps its meaning.** Every field carries an immutable
  `key`, minted once by the server from the label
  (`normalize_schema()` in `client_forms/schema.py` is the only thing
  that mints keys) and never changed, so relabelling, reordering or
  deleting a question never orphans an answer. Sending a form deep-copies
  the template's question list into `FormSubmission.schema_snapshot`,
  and every later page renders from the snapshot, never the live
  template, so editing or deleting a template never changes what an old
  submission says. `FormTemplate.version` is a display counter, not
  copy-on-write versioning. `template` is `SET_NULL`.
- **The public page mounts at `/form/<token>/`**, outside `/intakes/`,
  because `PermissionMiddleware` gates that prefix on `perm_intakes` and
  the person filling the form has no account. The token is the
  submission's `uuid` signed with its own salt and an expiry, following
  the invoice pay page; `form_submission_reissue` rotates the uuid.
- **`is_active` on templates was retired** (2026-07-28). Every form is
  offered in the add-form modal; a form silently missing from a list
  because of a flag set in another modal was exactly the failure the
  setting invited.
- **The website push is unused and slated for removal.** The owner said
  so on 2026-10-02. The native forms are the live design for
  questionnaires; do not build on `receive_intake`, `receive_inquiry` or
  `search_intakes`.

## Alternatives

Copy-on-write template versions were the shape the snapshot was chosen
over: the commit says `version` is "a plain counter for display, not
copy-on-write versioning", because submissions are self-contained.
Mounting the public page under `/intakes/` was rejected for the reason
above. Blocking
the builder's save on incomplete fields was tried and dropped on
2026-07-27: completeness now gates presentation, through one
`is_complete` / `presentable` filter, not storage. File upload was left
out of the first version so the public endpoints carry no upload
surface.

## Consequences

- Never render a submission from `FormTemplate.schema`; `orphan_answers()`
  in `render.py` shows what no longer lines up after an edit.
- The `is_active` column stayed in the table, unread, for a later cleanup
  migration (the development database's nightly reload is why it could
  not go casually).
- The bundled seed forms (`sample_forms.json`) have frozen keys so a
  re-seed lands on the same ones; since 2026-10-02 they name no firm.
- The note filed on submission carries fixed text only, because
  `Note.details` is emitted with `|safe`; answers are read through the
  escaped review modal.
- `KOSMOS_SEAM_KEY` blank means the website endpoints refuse everything.
  Their removal, when it comes, takes the key and the operator page's
  table with it.

## Evidence

- The commit that introduced the forms, "feat(intakes): custom intake
  forms", subtitled "a builder, a client link, and the answers"
  (2026-07-25): "The point of the design is that an answer keeps its
  meaning ... It mounts at /form/ rather than under /intakes/, which
  PermissionMiddleware gates on perm_intakes."
- `apps/intakes/client_forms/public_urls.py` docstring and the key
  discipline paragraph at the top of `client_forms/schema.py`.
- Commit "feat(intakes): retire is_active; one client card for everyone;
  link never walls" (2026-07-28).
- Commit "fix(intakes): the website's dispute type is matched to the
  firm's own practice areas" (2026-10-02), which removed the one-firm
  table from `api_views.py`.
- [Email and intakes](../dev/subsystems/email-and-intakes.md), "The
  legacy website endpoints", recording the owner's statement.

## Related

- [Email and intakes](../dev/subsystems/email-and-intakes.md): Client
  forms.
- [Security checklist](../admin/security.md): `KOSMOS_SEAM_KEY`.
- [Intake email rules](2026-07-28-intake-email-rules.md).

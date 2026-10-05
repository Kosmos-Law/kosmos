# Local storage by default, media unrouted, the logo excepted (2026-08-03)

Uploaded files (documents, invoice PDFs, the firm logo) had been served
two ways: in production from an S3-compatible bucket with signed URLs,
and under `runserver` from `MEDIA_ROOT` through Django's `static()`
helper. A checkout therefore needed cloud credentials to behave like
production, and a server running local storage would have served every
confidential upload at a guessable `media/...` address. The
containerization work of August 2026 made the storage backend a setting
and had to decide what a local-storage server exposes.

## Decision

`STORAGE_BACKEND` selects the default storage: `local` (the default) is
`FileSystemStorage` under `MEDIA_ROOT`; `s3` is `django-storages` with
query-string signing on. Local is the default on purpose so a checkout
runs without cloud credentials. Any other value refuses to start.

`MEDIA_ROOT` is never exposed through Django's URL configuration in
production. `development_media_urlpatterns()` routes `media/` only when
`DEBUG` is on and the backend is local. Everything confidential is
reached through a view that checks access and streams the file through
the storage API, so the two backends are interchangeable.

One exception: `media/company/`, the `upload_to` of `Firm.logo`, stays
routed under local storage in every mode
(`public_branding_media_urlpatterns()`). The logo is public branding
and is loaded by URL from the settings page, the public intake form
pages and the invoice PDF renderer. Only that subdirectory is exposed;
under S3 the bucket's own URLs apply and the route is not installed.

## Alternatives

- Keeping S3 as the only backend. Rejected so that "a checkout can run
  without cloud credentials"; the test suite likewise points storage at
  a temporary directory for every test.
- Routing all of `media/` under local storage, as `runserver` does.
  Rejected: "confidential uploads must go through the authenticated
  download views".
- Unrouting the logo along with everything else. Tried, for part of a
  day on 2026-08-03: the logo 404ed on the settings page, the intake
  forms and in every invoice PDF generated in that window, which had to
  be regenerated afterwards (`generate_invoice_pdfs --sent-since`).
- Embedding the logo from disk in PDFs instead of fetching it by URL.
  Done as well for the PDF renderer's `file://` fetcher, so the PDF no
  longer depends on the HTTP route; the route remains for the pages.

## Consequences

- Code reads and writes files only through a `FieldFile` or
  `default_storage`. A path on disk is wrong under either backend.
- A template that builds a `media/...` URL for anything but the firm
  logo works under `runserver` and 404s on a server. Serve the file
  through a view.
- A new public asset (a second logo, a letterhead image) is not public
  by putting it in `media/`; it needs either `company/` as its
  `upload_to` or a route of its own, and a decision that it is public.
- `config/tests/test_media_security.py` pins all of this: unrouted in
  production, routed under `runserver`, never mapped under S3, the logo
  exception's scope, and a login on the document endpoints.
- Changing `STORAGE_BACKEND` on a live install moves nothing: the files
  must be copied across with the paths kept, as the operator page
  describes.

## Evidence

- `config/settings.py`, the storage block: "Local is deliberately the
  default so a checkout can run without cloud credentials. Production
  never exposes MEDIA_ROOT through Django's public URL configuration;
  protected download views continue to stream confidential files
  through Django's storage API."
- `config/urls.py`, `public_branding_media_urlpatterns()`: "Unrouting
  MEDIA_ROOT protects confidential uploads, but the logo is deliberately
  public branding ... Only this one subdirectory - Firm.logo's upload_to
  - is exposed."
- Commit "feat: containerization optimizations (#482)" (2026-08-03):
  `STORAGE_BACKEND`, the media routing functions and
  `test_media_security.py`.
- Commit "fix: firm logo 404s after media unrouting - route
  media/company/ publicly" (2026-08-03): "PR #482 rightly stopped routing
  MEDIA_ROOT in production (confidential uploads must go through the
  authenticated download views), but the firm logo lives there too and
  is deliberately public branding."
- Commit "fix(invoicing): heal logo-less invoice PDFs from the media
  unrouting window" (2026-08-03).

## Related

- [Platform and config](../dev/subsystems/platform-and-config.md),
  "Storage" and "URLs"
- [File storage](../admin/integrations/storage.md)

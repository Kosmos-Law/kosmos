# File storage

Where Kosmos keeps uploaded files, how to put them in an S3-compatible
object store, how files reach the browser, and the commands that repair a
mismatch between the database and the stored files.

## What is stored

Kosmos stores three kinds of file. Everything else, including notes, synced
email text and extracted document text, lives in the database.

| Files | Path inside storage |
|---|---|
| Matter documents (uploaded PDFs, PDFs mirrored from Google Drive, emails promoted to documents) | `documents/<matter id>/<document id>.<extension>` |
| Invoice PDFs | `invoices/<matter id>/<invoice id>.pdf` |
| The firm logo | `company/<file name>` |

The database records each file by that relative path. The same paths are
used whichever backend is selected.

Deleting a document or invoice record in the application deletes its file
as well. Text extraction (OCR) can replace a scanned document's file, at
the same path, with a searchable copy.

## Choose a backend

`STORAGE_BACKEND` selects where the files go. It accepts `local` or `s3`,
and any other value stops the application at start-up. The variables are
described in the
[environment variable reference](../../reference/environment.md).

### Local disk

`STORAGE_BACKEND=local` is the default. Files are written to the `media/`
directory at the root of the checkout. The location is not configurable;
to keep the files on another volume, mount it there or make `media/` a
symbolic link.

The user the application runs as must be able to write to `media/`, and
the background worker must run as the same user, because it reads and
rewrites documents during text extraction.

`media/` holds confidential client documents. Include it in backups
alongside the database: one is not usable without the other.

### S3-compatible object store

1. Create a bucket and an access key that can read, write and delete
   objects in it. Keep the bucket private: Kosmos sends no access-control
   setting with its uploads, so each object takes the bucket's default.

2. Set all five variables in `config/.env`. With `STORAGE_BACKEND=s3`,
   the application will not start if any of them is missing.

    ```
    STORAGE_BACKEND=s3
    DIGITAL_OCEAN_REGION_NAME=<region>
    DIGITAL_OCEAN_ENDPOINT_URL=https://<endpoint host>
    DIGITAL_OCEAN_BUCKET_NAME=<bucket>
    DIGITAL_OCEAN_ACCESS_KEY_ID=<key id>
    DIGITAL_OCEAN_SECRET_ACCESS_KEY=<secret>
    ```

3. Restart the web application and the background worker.

The variable names say DigitalOcean for historical reasons. They are
passed straight to a generic S3 client as the region, endpoint URL, bucket
and key pair, so any store that speaks the S3 API at a custom endpoint can
be used. Two things are fixed in the code and cannot be changed from
`config/.env`: objects are written at the top level of the bucket (there
is no key prefix), and there is no setting for the addressing style or
signature version. A store that needs non-default values for those is not
supported without a code change.

Set `STORAGE_BACKEND` explicitly on every server. If it is missing from
the environment file of a server that is meant to use a bucket, Kosmos
falls back to `local` without complaint and new uploads are written to
the server's own disk.

## How files are served

Kosmos does not publish its files at a URL. Each one is read through the
storage backend by the application and streamed to a request it has
checked.

- **Documents** are downloaded and displayed in the viewer by views that
  require a signed-in user. A request without a session is redirected to
  the sign-in page. Responses are marked private so that shared caches do
  not keep them.
- **Invoice PDFs** are served to signed-in staff inside the application,
  and to clients through the payment links sent by email. Those links
  carry a signed token that expires (see `INVOICE_PAY_LINK_MAX_AGE`) and
  the PDF endpoint is rate-limited. A voided invoice's link stops working.
- **Email attachments from Gmail** are never stored. See
  [Gmail sync](gmail.md).

This holds for both backends. With `s3`, the browser never talks to the
bucket for documents or invoices: the application fetches the object and
relays it.

### The one exception: the firm logo

The logo is public branding. It appears on the sign-in page, on the public
intake form and payment pages, and in invoice PDFs.

- With `local` storage, Kosmos serves `media/company/` at
  `/media/company/` without requiring a sign-in. Nothing else under
  `media/` is routed.
- With `s3` storage, pages link to the logo in the bucket with a signed
  URL that expires after an hour. The bucket itself stays private.

Emails embed the logo in the message instead of linking to it.

### What you must not do

- Do not add a `/media/` location to the web server. The supplied nginx
  site has none, on purpose. Serving `media/` directly would expose every
  client document to anyone who can guess a path.
- Do not run a production server with `DEBUG` on. With `DEBUG` on and
  local storage, Kosmos routes the whole of `media/` at `/media/` without
  authentication, as a convenience for development.

## Switching backends on a live install

Changing `STORAGE_BACKEND` changes where Kosmos looks. It does not move
anything: there is no migration command, and the application never copies
files between backends.

Because the database stores relative paths, and both backends use the same
ones, the files can be moved with any tool as long as the paths are kept:
`media/documents/12/345.pdf` on disk corresponds to the object
`documents/12/345.pdf` in the bucket, and likewise for `invoices/` and
`company/`.

1. Stop the web application and the worker, so nothing is written during
   the copy.
2. Copy the whole tree from the old backend to the new one, preserving
   paths.
3. Change the variables in `config/.env` and start both services.
4. Run the checks under [Check that it works](#check-that-it-works).
5. Keep the old copy until you are satisfied.

If you switch without copying, records remain but their files are missing
from the new backend:

- Opening or downloading a document answers "File not found in storage."
- The firm logo is broken wherever it is shown.
- A client following a payment link still gets an invoice PDF, because
  that page regenerates a missing PDF from the invoice data. Other places
  that read a stored invoice PDF fail until the files are restored or
  regenerated.

Switching back restores access to the files that were in the first
backend. Anything uploaded while the wrong backend was active is in the
other one, and has to be copied across by hand.

## Check that it works

1. Upload a small PDF to a matter's Documents tab. Kosmos confirms after
   every upload that the file reached storage and reports "Upload failed"
   if it did not.
2. Open the document in the viewer and download it.
3. With `s3`, confirm the object exists in the bucket at
   `documents/<matter id>/<document id>.pdf`. With `local`, confirm the
   file is under `media/`.
4. Upload a logo under **Settings → Firm** and load the sign-in page in a
   private window.
5. In a private window, request a document path directly, for example
   `https://kosmos.example.com/media/documents/1/1.pdf`. It must not
   return the file.
6. Run `python manage.py cleanup_orphan_documents`. Without `--apply` it
   checks every document record against storage and deletes nothing. On a
   healthy install it prints "No orphan documents found."

## Repair commands

All three are listed in the
[management command reference](../../reference/commands.md). Take a
database backup before running any of them without its dry-run option.

### restore_drive_documents

For documents that were mirrored from Google Drive and whose file is
missing from storage. The regular Drive sync does not repair these: it
compares modification times and treats an unchanged Drive file as already
done.

```bash
python manage.py restore_drive_documents           # report only
python manage.py restore_drive_documents --apply   # download again
python manage.py restore_drive_documents --apply --ids 101 102
```

It reports by default and writes only with `--apply`. Each missing file
is downloaded from Drive again and saved under the record's existing
path. Finished text extraction is kept, and a document whose extraction
was pending or had failed is queued again. Google Drive must be connected
(see [Google Workspace](google.md)).

Use it after files were lost or written to the wrong backend. It cannot
help with documents that users uploaded by hand: Kosmos held the only
copy of those.

### cleanup_orphan_documents

Lists document records whose file is missing from storage and, with
`--apply`, deletes them together with the highlights made on them.

```bash
python manage.py cleanup_orphan_documents           # list only
python manage.py cleanup_orphan_documents --apply   # delete
```

Like the command above, it reports by default and changes nothing without
`--apply`. Deleting is the last step, not the first: use it only when the files are
certainly gone, after restoring what can be restored from backups and
from Drive. Run against the wrong backend, it would list every document
as an orphan, so always read the list before applying.

### fix_document_paths

Corrects records that point at a path in an older naming scheme
(`documents/<matter name>_<id>/<category>/<file name>`) when the file
already exists at the current path.

```bash
python manage.py fix_document_paths --dry-run
python manage.py fix_document_paths
```

It only updates the database and never moves a file. A record whose file
exists only at the old path is reported as `SKIP` and left alone, and a
record whose file is at neither path is reported as `MISSING`. Records
already at the current path are not examined at all, so this command is
not a check for missing files. An install that has only ever run current
code has nothing for it to fix.

### Invoice PDFs

Invoice PDFs can be rebuilt from invoice data, so they need no restore
from backup:

```bash
python manage.py generate_invoice_pdfs               # invoices with no PDF recorded
python manage.py generate_invoice_pdfs --overwrite   # every invoice that is not void
```

The first form only fills in invoices that have no PDF on record. After
losing files that the database still points at, use `--overwrite`. A
regenerated PDF is drawn from the invoice as it stands today, with the
current firm details and logo, so it is not guaranteed to be identical to
the copy a client was originally sent.

## Troubleshooting

**The application will not start after setting `STORAGE_BACKEND=s3`.**
One of the five `DIGITAL_OCEAN_*` variables is missing. The error names
it.

**Uploads fail with "file did not save to storage".** With `local`,
check ownership and free space under `media/`. With `s3`, check the key's
permissions on the bucket, the endpoint URL and the region.

**Documents show "File not found in storage" or "Could not retrieve file
from storage".** The first means the record's file is absent from the
active backend. The second means the backend returned an error; the cause
is in `logs/django.log`.

**Large uploads fail.** The supplied nginx site caps request bodies at
100 MB (`client_max_body_size`). Larger uploads are rejected by the web
server before they reach Kosmos.

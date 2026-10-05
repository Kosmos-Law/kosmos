"""Server side of the LibreOffice companion extension.

The extension (apps/drafts/companion_src, downloaded as a personalized .oxt
via companion_oxt) runs inside the user's LibreOffice Writer, pairs the open
document with its draft link by filename, and polls this API:

    GET  sessions/              the token user's draft links, newest first
    POST <link>/hello/          register + push the document (odt_b64)
    GET  <link>/ops/            pick up the next pending edit round
    POST <link>/rounds/<id>/    claim the round ({"claim": true}), or
                                report its outcome (+ document)

Two versions of the extension are in use and both must keep working, since
a user's installed copy only changes when they download it again:

    0.3.0  collects a round from ops/ and applies it at once, then reports.
    0.4.0  collects a round, claims it, applies it only if the claim is
           granted, then reports. It claims only when the round it was
           handed says "claim": true, so it also works against a server
           that predates the claim.

The protocol therefore only ever grows: no path, method or key that 0.3.0
uses may change, and anything new must be optional for the client.

Every call refreshes companion_seen; while that is fresh the chat worker
routes edit rounds here (chat._apply_via_companion). Document pushes are ODT
bytes, converted server-side to a Markdown facsimile (the accepted view,
tables included), which becomes the AI's draft context.

Auth is a per-user key in the X-Kosmos-Token header (CompanionToken). These
endpoints are CSRF-exempt: the client is urllib inside LibreOffice, not a
browser with cookies. An unlinked draft answers 404, which tells the
extension to stop polling; a link whose matter the user can no longer open
answers 403, so the extension can say that instead (0.3.0 reads a 403 as
a server error and keeps polling, which is harmless).
"""

import base64
import io
import json
import logging
import zipfile
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.case.ai.access import accessible_matters
from apps.drafts.models import CompanionRound, CompanionToken, DraftLink
from apps.drive import convert

logger = logging.getLogger(__name__)

COMPANION_SRC = Path(__file__).resolve().parent / "companion_src"
# Also declared in companion_src/description.xml (LibreOffice reads the
# version from there); test_companion checks the two agree.
EXTENSION_VERSION = "0.4.0"


def companion_auth(view):
    """Token auth for extension endpoints; sets request.companion_user."""

    @csrf_exempt
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        key = request.headers.get("X-Kosmos-Token", "")
        token = (
            CompanionToken.objects.select_related("user").filter(key=key).first()
            if key
            else None
        )
        if token is None or not token.user.is_active:
            return JsonResponse({"error": "invalid token"}, status=401)
        request.companion_user = token.user
        try:
            return view(request, *args, **kwargs)
        except PermissionDenied as exc:
            return JsonResponse({"error": str(exc)}, status=403)

    return wrapper


def _user_links(user):
    """The draft links this token may work with: on conversations the user
    started, on matters the user can still open. A user taken off a matter
    keeps their token, so the matter check has to be made on every call."""
    return DraftLink.objects.filter(
        conversation__user=user,
        conversation__matter__in=accessible_matters(user),
    ).select_related("conversation__matter")


def _get_link(request, link_id):
    """The link, if it is the token user's own and its matter is still
    theirs to open. A link that exists on the user's own conversation but
    whose matter they have lost is told apart from one that was unlinked:
    the extension's message names the right cause."""
    link = get_object_or_404(
        DraftLink.objects.filter(
            conversation__user=request.companion_user
        ).select_related("conversation__matter"),
        pk=link_id,
    )
    if not request.companion_user.has_matter_access(link.conversation.matter):
        raise PermissionDenied("no access to the matter")
    return link


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}


def _store_document(link, payload):
    """Decode a pushed ODT and store its Markdown facsimile as the draft
    text on the link AND its siblings (other conversations linking the same
    file read the same live document). Fails soft: a bad push never breaks
    the poll loop."""
    odt_b64 = payload.get("odt_b64")
    if not odt_b64:
        return
    try:
        odt_bytes = base64.b64decode(odt_b64)
        text = convert.to_markdown(odt_bytes, ".odt")
    except Exception:
        logger.exception("Companion document push failed for link %s", link.id)
        return
    now = timezone.now()
    link.sibling_links().update(doc_text=text, doc_text_at=now)
    link.doc_text = text
    link.doc_text_at = now


def _touch(link):
    link.companion_seen = timezone.now()
    link.save(update_fields=["companion_seen"])


@companion_auth
@require_http_methods(["GET"])
def api_sessions(request):
    """The token user's draft links, newest first."""
    links = _user_links(request.companion_user)
    return JsonResponse(
        {
            "sessions": [
                {
                    "id": link.id,
                    "name": link.name,
                    "matter": link.conversation.matter.name
                    if link.conversation.matter
                    else "",
                    # Let the extension tell apart links to different files
                    # of the same name, and name them to the user (0.4.0;
                    # 0.3.0 ignores both). Links to one file are siblings
                    # and need no telling apart.
                    "file": link.drive_file_id,
                    "conversation": link.conversation.title,
                }
                for link in links
            ]
        }
    )


@companion_auth
@require_http_methods(["POST"])
def api_hello(request, link_id):
    """Register the companion (and on later calls, refresh the document)."""
    link = _get_link(request, link_id)
    _store_document(link, _json_body(request))
    _touch(link)
    logger.info("Companion connected to draft link %s", link.id)
    matter = link.conversation.matter
    return JsonResponse(
        {
            "status": "drafting",
            "name": link.name,
            "matter": matter.name if matter else "",
        }
    )


@companion_auth
@require_http_methods(["GET"])
def api_ops(request, link_id):
    """Deliver the oldest undelivered pending round, at most once.

    A round is never redelivered: if the extension dies mid-application the
    chat worker's wait expires it and the user simply asks again. Redelivery
    would risk applying the same edits twice to the live document.
    """
    link = _get_link(request, link_id)
    _touch(link)
    round_ = (
        CompanionRound.objects.filter(
            link__in=link.sibling_links(),
            status="pending",
            delivered_at__isnull=True,
        )
        .order_by("created_at")
        .first()
    )
    if round_ is None:
        return JsonResponse({"status": "drafting", "round": None})
    # Conditional, so a round the chat worker expired a moment ago (or one
    # a second poller just took) is not handed out.
    collected = CompanionRound.objects.filter(
        pk=round_.pk, status="pending", delivered_at__isnull=True
    ).update(delivered_at=timezone.now())
    if not collected:
        return JsonResponse({"status": "drafting", "round": None})
    return JsonResponse(
        {
            "status": "drafting",
            "round": {
                "id": round_.id,
                "edits": round_.edits,
                # Asks a 0.4.0 extension to claim before applying. 0.3.0
                # ignores the key and applies straight away.
                "claim": True,
            },
        }
    )


@companion_auth
@require_http_methods(["POST"])
def api_result(request, link_id, round_id):
    """Record a round's outcome and the resulting document, or answer a
    claim.

    A claim ({"claim": true}, sent by 0.4.0 just before it applies) is
    granted only while the chat worker is still waiting on the round, and
    restarts that wait. A refused claim tells the extension to leave the
    document alone: the chat has already said the edits were not applied.

    An outcome is recorded for a pending round, and also for a collected
    round the worker has since given up on: the edits are in the document
    by then, and the record should say so.
    """
    link = _get_link(request, link_id)
    round_ = get_object_or_404(
        CompanionRound, pk=round_id, link__in=link.sibling_links()
    )
    payload = _json_body(request)
    if payload.get("claim"):
        granted = CompanionRound.objects.filter(
            pk=round_.pk, status="pending", delivered_at__isnull=False
        ).update(delivered_at=timezone.now())
        _touch(link)
        return JsonResponse({"status": "drafting", "apply": bool(granted)})

    late = round_.status == "expired" and round_.delivered_at is not None
    if late:
        logger.info("Companion round %s reported after its wait ran out", round_.id)
    if round_.status == "pending" or late:
        if payload.get("ok"):
            round_.status = "applied"
            round_.result = payload.get("results") or []
        else:
            round_.status = "failed"
            round_.error = str(payload.get("error") or "unknown companion error")
            index = payload.get("edit_index")
            round_.edit_index = index if isinstance(index, int) else None
        round_.save()
    _store_document(link, payload)
    _touch(link)
    return JsonResponse({"status": "drafting"})


def companion_oxt(request):
    """Build and serve the personalized .oxt (login required, applied in
    urls.py via the standard decorator on the wrapping view).

    The extension source is zipped as-is with one generated member:
    config.json carrying this server's URL and the requesting user's token.
    Building on demand keeps the download in lockstep with deployed code.
    """
    token = CompanionToken.for_user(request.user)
    server = settings.PUBLIC_BASE_URL or request.build_absolute_uri("/").rstrip("/")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(COMPANION_SRC.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(COMPANION_SRC).as_posix())
        archive.writestr(
            "config.json",
            json.dumps(
                {
                    "server": server,
                    "token": token.key,
                    "version": EXTENSION_VERSION,
                }
            ),
        )
    buffer.seek(0)
    return FileResponse(
        buffer,
        as_attachment=True,
        filename="kosmos-companion.oxt",
        content_type="application/vnd.openofficeorg.extension",
    )

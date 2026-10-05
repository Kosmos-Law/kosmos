import hmac
import json
import re
from functools import wraps

from django.conf import settings
from django.db import models
from django.db.models import Q, Value
from django.db.models.functions import Replace
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.intakes.models import Intake, Note
from apps.matters.models import PracticeArea


def seam_protected(view):
    """Requires the X-Seam-Key header to match KOSMOS_SEAM_KEY. With no key
    configured the endpoint refuses every request: these views create
    intakes and return prospective clients' contact details, so a blank
    setting must mean "off", not "open"."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        key = settings.KOSMOS_SEAM_KEY
        sent = request.headers.get("X-Seam-Key", "")
        if not key or not hmac.compare_digest(sent.encode(), key.encode()):
            return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)
        return view(request, *args, **kwargs)

    return wrapper


def _name_key(text):
    """A name reduced to its letters and digits, lower-cased, so that
    "quiet_title", "Quiet Title" and "quiet-title" all compare equal."""
    return "".join(ch for ch in str(text or "").casefold() if ch.isalnum())


def practice_area_for(dispute_nature):
    """The firm's own practice area for the website's dispute type, or None.

    The website sends the dispute type as a short key ("boundary",
    "quiet_title"). Practice areas are the firm's to name (Settings), so the
    key is matched against the active ones by name, ignoring case, spaces and
    punctuation. No table of names lives here: a key that matches no practice
    area leaves the intake's practice area empty, for staff to set."""
    wanted = _name_key(dispute_nature)
    if not wanted:
        return None
    for area in PracticeArea.objects.filter(is_active=True).order_by("name"):
        if _name_key(area.name) == wanted:
            return area
    return None


@csrf_exempt
@require_http_methods(["POST"])
@seam_protected
def receive_inquiry(request):
    """
    API endpoint to receive inquiry data from external sources.
    Returns JSON response with success/failure status.
    """
    try:
        data = json.loads(request.body)

        full_name = data.get("full_name", "")
        phone_number = data.get("phone_number", "")
        email = data.get("email", "")
        summary = data.get("summary", "")

        if not all([full_name, phone_number, email, summary]):
            return JsonResponse(
                {"success": False, "error": "Missing required fields"}, status=400
            )

        # A repeat inquirer threads onto their existing intake instead of
        # opening a duplicate - the same matching the inbound-email
        # follow-up flow uses (email first, then 10-digit phone).
        from apps.intakes.inbound import _match_existing_intake

        matched = _match_existing_intake(email, phone_number)
        if matched:
            details = summary
            updates = []
            if not matched.phone and phone_number:
                matched.phone = phone_number
                updates.append(f"New phone: {phone_number}")
            if not matched.email and email:
                matched.email = email
                updates.append(f"New email: {email}")
            if matched.status == "Unresponsive":
                # The client resurfacing is what this status was waiting on
                matched.status = "Open"
            matched.save()
            if updates:
                details = "\n".join(updates) + "\n\n" + details

            Note.objects.create(
                date=timezone.localdate(),
                time=timezone.localtime().time(),
                intake=matched,
                type="Email In",
                details=details,
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": "Inquiry added to existing intake",
                    "intake_id": matched.id,
                }
            )

        intake = Intake.objects.create(
            name=full_name,
            phone=phone_number,
            date=timezone.localdate(),
            status="Open",
            email=email,
        )

        Note.objects.create(
            date=timezone.localdate(),
            time=timezone.localtime().time(),
            intake=intake,
            type="Email In",
            details=summary,
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Inquiry received successfully",
                "intake_id": intake.id,
            }
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@seam_protected
def search_intakes(request):
    """
    The website office's window into the intake roster: it searches
    here before minting client-form links, so an intake logged from a
    phone call is found and attached rather than duplicated. A blank
    query lists the open roster — the office's landing view, one click
    from attaching. Numeric queries match the intake number exactly or
    a phone fragment; text queries match name or phone.
    """
    q = (request.GET.get("q") or "").strip()
    if not q:
        matches = Q(status="Open")
    else:
        # Phones are stored however they were typed; compare digits to
        # digits so "5550122" finds "404-555-0122"
        q_digits = re.sub(r"\D", "", q)
        matches = Q(id=int(q)) if q.isdigit() else Q(name__icontains=q)
        if q_digits:
            matches |= Q(phone_digits__contains=q_digits)

    phone_digits = models.F("phone")
    for mark in ("-", " ", "(", ")", "."):
        phone_digits = Replace(phone_digits, Value(mark), Value(""))
    intakes = (
        Intake.objects.annotate(phone_digits=phone_digits)
        .filter(matches)
        .select_related("practice_area")
        .order_by("-id")[:20]
    )
    results = [
        {
            "id": intake.id,
            "name": intake.name,
            "phone": intake.phone or "",
            "email": intake.email or "",
            "status": intake.status,
            "date": intake.date.isoformat() if intake.date else "",
            "practice_area": (
                intake.practice_area.name if intake.practice_area else ""
            ),
        }
        for intake in intakes
    ]
    return JsonResponse({"success": True, "results": results})


@csrf_exempt
@require_http_methods(["POST"])
@seam_protected
def receive_intake(request):
    """
    API endpoint receiving the website's client intake questionnaire.
    Maps the basic contact details onto an Intake and files the full
    report as a note with no user, typed "Client Form" to flag it as
    self-submitted by the prospective client. A follow-up payload may
    carry intake_id to attach a note to the same intake, and note_id
    to update a previously filed note in place — the website's forms
    stay editable after submission, and each resubmission replaces its
    original note rather than adding another.
    """
    try:
        data = json.loads(request.body)

        full_name = data.get("full_name", "")
        report = data.get("report", "")
        intake_id = data.get("intake_id")
        note_id = data.get("note_id")

        if not report or not (full_name or intake_id):
            return JsonResponse(
                {"success": False, "error": "Missing required fields"}, status=400
            )

        intake = None
        if intake_id:
            intake = Intake.objects.filter(id=intake_id).first()

        if intake is None:
            # Create-fallback for legacy unbound website intakes only.
            # Since the website's office attaches to existing Kosmos
            # intakes (intake records are born here, not there), every
            # new push carries intake_id and this branch should be
            # unreachable; it stays for old cl rows without a binding.
            practice_area = practice_area_for(data.get("dispute_nature"))
            intake = Intake.objects.create(
                name=full_name,
                phone=data.get("phone_number", ""),
                email=data.get("email", ""),
                address=data.get("address", "")[:255],
                disputed_property=data.get("disputed_property", "")[:255],
                practice_area=practice_area,
                date=timezone.localdate(),
                status="Open",
                source="Internet",
            )

        note = None
        if note_id:
            # An update edits the original note; a stale id falls
            # through and files a fresh note instead
            note = Note.objects.filter(id=note_id, intake=intake).first()
        if note is not None:
            note.details = report
            note.save()
        else:
            note = Note.objects.create(
                date=timezone.localdate(),
                time=timezone.localtime().time(),
                intake=intake,
                user=None,
                type="Client Form",
                details=report,
            )

        return JsonResponse(
            {
                "success": True,
                "message": "Intake received successfully",
                "intake_id": intake.id,
                "note_id": note.id,
            }
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

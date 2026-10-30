"""One matter's working record, as service functions and as a
token-authed JSON API over them.

The service functions (list_matters, read_section, ... create_task) are
what the remote MCP server's tools call (apps/mcp/tools.py); the JSON
views under case/api/ are the same functions behind the X-Kosmos-Token
header, for scripts. Reads serve every section
of a matter as AI-ready text, reusing the in-app chat's formatters where
they exist so the two surfaces cannot drift; writes are create-shaped
(timeline facts, witnesses, tasks, time entries, events, contacts, and
marking a task complete) through the same validation the application's
forms and the in-app AI's fenced blocks apply.

Access mirrors the app: matters are the user's accessible OPEN matters
only, and every denial is a 404 so it doesn't confirm existence. The
money sections (rates, ledger, trust) and invoice reads additionally
require the user's financial permission, like the in-app Rates and Ledger
tabs; that denial is a 403 since the matter's existence is already known
to the caller. The activity section is open to every user who can see the
matter, as the Activity screens are.
"""

import json
from datetime import date, time
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import wraps

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Count, F, Max, Q
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.access import filter_matters_for_user
from apps.accounts.api_auth import ApiError, kosmos_api_auth
from apps.activity.expenses.models import ExpenseEntry
from apps.activity.flat_fees.models import FlatFeeEntry
from apps.activity.models import ActivityCategory
from apps.activity.time.models import TimeEntry
from apps.activity.time.views import calculate_rate_for_matter
from apps.ai.access import has_financial_access
from apps.ai.context import (
    format_events,
    format_invoice,
    format_matter_overview,
    format_proceedings,
    format_settlement,
    format_witnesses,
)
from apps.ai.fact_blocks import _create_fact_from_entry
from apps.ai.models import Conversation
from apps.ai.witness_blocks import _create_witness_from_entry
from apps.calendar.events import default_end_time
from apps.calendar.models import Event
from apps.case.models import Document, Fact, Highlight
from apps.checklists.models import can_complete_task
from apps.contacts.access import already_assigned, assignable_roles
from apps.contacts.models import Contact
from apps.invoicing.invoices.models import Invoice
from apps.invoicing.requests.models import PaymentRequest
from apps.mail.ai import format_email_thread, group_by_thread, thread_subject
from apps.matters.ledger.get_ledger_data import get_ledger_data
from apps.matters.models import Group, Matter, Relationship
from apps.matters.rates.models import Rate
from apps.tasks.constants import CHECKLIST_INCOMPLETE_MESSAGE, STATUS_COMPLETE
from apps.tasks.models import Task
from apps.tasks.services import create_task_from_ai_entry
from apps.trust.available import client_trust_available, trust_available_severity
from apps.trust.trust import (
    get_client_history,
    get_confirmed_client_balance,
    get_pending_client_balance,
)
from config.helpers import normalize_phone

MATTER_404 = "No such matter, or you do not have access to it."
DOCUMENT_404 = "No such document, or you do not have access to it."
THREAD_404 = "No such email thread in this matter."
CONVERSATION_404 = "No such AI conversation in this matter."
INVOICE_404 = "No such invoice, or you do not have access to it."
TASK_404 = "No such task, or you do not have access to it."
FINANCIAL_403 = "Your Kosmos account does not have financial access."

# Sections behind the Financial permission in the application itself (the
# Rates and Ledger tabs, trust). The in-app agent applies the same list to
# the user it is working for (ai/agent_tools.agent_sections). Activity is
# not among them: the Activity screens show rate and fee to every user.
FINANCIAL_SECTIONS = ("rates", "ledger", "trust")


def _has_financial_access(user):
    return has_financial_access(user)


def _get_matter(user, matter_id):
    """The matter, if it is open and accessible to user; None otherwise."""
    return (
        filter_matters_for_user(Matter.objects.filter(status="Open"), user)
        .filter(pk=matter_id)
        .first()
    )


def _json_body(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return body if isinstance(body, dict) else None


# ---------------------------------------------------------------------------
# Section formatters not shared with the in-app chat context. These are
# manifest-shaped (ids and handles for follow-up tool calls) rather than
# chat-context-shaped, which is why they live here and not in ai/context.
# ---------------------------------------------------------------------------


def _format_contacts(matter):
    """The parties: each contact with its role and group, then the groups
    and roles add_contact may use on this matter."""
    relationships = (
        Relationship.objects.filter(matter=matter)
        .select_related("contact", "role", "group")
        .order_by("group__order", "contact__name")
    )
    lines = []
    for rel in relationships:
        contact = rel.contact
        line = f"- [contact:{contact.id}] {contact.name} ({rel.role.name}, {rel.group.name})"
        if contact.company:
            line += f" - {contact.company}"
        if contact.email:
            line += f" [{contact.email}]"
        if contact.phone1:
            line += f" {contact.phone1}"
        lines.append(line)
    if not lines:
        lines.append("No contacts assigned.")
    lines.append(
        "Groups add_contact may use on this matter: "
        + ", ".join(g.name for g in _assignable_groups(matter))
        + ". Roles: "
        + ", ".join(r.name for r in assignable_roles())
        + "."
    )
    return "\n".join(lines)


def _format_tasks(matter):
    """Task manifest, pending first, capped at 20; [task:ID] handles feed
    complete_task. Within each group the most important come first (7 is
    the top of the scale), then the soonest due; nulls are ordered
    explicitly, as the in-app formatter does, or the cut fills with
    finished work."""
    tasks = (
        Task.objects.filter(matter=matter)
        .select_related("user")
        .order_by(
            F("date_completed").desc(nulls_first=True),
            "-importance",
            F("date_due").asc(nulls_last=True),
        )[:20]
    )
    if not tasks:
        return "No tasks."
    lines = []
    for task in tasks:
        status = task.status or ("Complete" if task.date_completed else "Pending")
        line = f"- [task:{task.id}] [{status}] P{task.importance}: {task.description}"
        if task.date_due:
            line += f" (Due: {task.date_due})"
        if task.user:
            line += f" - {task.user.full_name}"
        lines.append(line)
    lines.append("Use complete_task with a task id to mark one complete.")
    return "\n".join(lines)


def _format_rates(matter):
    """Billing setup: matter type plus hourly rates (matter overrides first)."""
    lines = [f"Billing type: {matter.get_billing_type_display()}"]
    if matter.billing_type == "FLAT_FEE" and matter.flat_fee_amount is not None:
        lines.append(f"Flat fee: ${matter.flat_fee_amount:,.2f}")
    if not matter.billable:
        lines.append("Matter is marked non-billable.")

    rates = list(
        Rate.objects.filter(Q(matter=matter) | Q(matter__isnull=True)).select_related(
            "user"
        )
    )
    matter_rows = [r for r in rates if r.matter_id]
    firm_rows = [r for r in rates if not r.matter_id]
    if matter_rows:
        lines.append("Rates for this matter (override the firm defaults):")
        lines += [f"- {r.user.full_name}: ${r.matter_rate}/hr" for r in matter_rows]
    if firm_rows:
        lines.append("Firm default rates:")
        lines += [f"- {r.user.full_name}: ${r.matter_rate}/hr" for r in firm_rows]
    if not matter_rows and not firm_rows:
        lines.append("No hourly rates set.")
    return "\n".join(lines)


def _format_activity(matter):
    """Time, expense, and flat-fee entries with category coding and totals."""
    sections = []

    entries = list(
        TimeEntry.objects.filter(matter=matter)
        .select_related("user", "invoice", "category")
        .order_by("-date")
    )
    if entries:
        lines = ["Time entries:"]
        total_hours = 0
        total_fees = 0
        for entry in entries:
            user_name = entry.user.get_full_name() if entry.user else "Unknown"
            fee = entry.hours * entry.rate if entry.rate else 0
            category = f" [{entry.category.name}]" if entry.category else ""
            line = (
                f"- [{entry.date}]{category} {entry.actions} — "
                f"{entry.hours}h @ ${entry.rate}/hr (${fee:,.2f}) by {user_name}"
            )
            if entry.comp:
                line += " [COMP]"
            if entry.invoice:
                line += f" [Invoice #{entry.invoice.id}, {entry.invoice.status}]"
            lines.append(line)
            total_hours += entry.hours
            if not entry.comp:
                total_fees += fee
        lines.append(f"Total: {total_hours}h, ${total_fees:,.2f} in non-comp fees")
        sections.append("\n".join(lines))

    expenses = list(
        ExpenseEntry.objects.filter(matter=matter)
        .select_related("activity_category", "invoice")
        .order_by("-date")
    )
    if expenses:
        lines = ["Expenses:"]
        for expense in expenses:
            category = (
                f" [{expense.activity_category.name}]"
                if expense.activity_category
                else ""
            )
            label = f"{expense.category}: " if expense.category else ""
            line = (
                f"- [{expense.date}]{category} {label}{expense.description} "
                f"(${expense.amount:,.2f})"
            )
            if expense.comp:
                line += " [COMP]"
            if expense.invoice:
                line += f" [Invoice #{expense.invoice.id}]"
            lines.append(line)
        total = sum(x.amount for x in expenses if not x.comp)
        lines.append(f"Total: ${total:,.2f} in non-comp expenses")
        sections.append("\n".join(lines))

    flat_fees = list(
        FlatFeeEntry.objects.filter(matter=matter)
        .select_related("invoice")
        .order_by("-date")
    )
    if flat_fees:
        lines = ["Flat fees:"]
        for fee in flat_fees:
            line = f"- [{fee.date}] {fee.description} (${fee.amount:,.2f})"
            if fee.comp:
                line += " [COMP]"
            if fee.invoice:
                line += f" [Invoice #{fee.invoice.id}]"
            lines.append(line)
        sections.append("\n".join(lines))

    return "\n\n".join(sections) or "No activity recorded."


def _format_documents(matter):
    """Document manifest: metadata only, never the extracted text."""
    documents = matter.documents.all()
    if not documents:
        return "No documents."
    lines = []
    for doc in documents:
        line = (
            f"- [doc:{doc.id}] {doc.name} ({doc.category}, "
            f"{doc.date or 'no date'}, importance {doc.importance})"
        )
        if doc.description:
            line += f"\n  {doc.description}"
        if doc.summary:
            line += f"\n  Summary: {doc.summary}"
        lines.append(line)
    lines.append("Use read_document with a doc id for a document's full text.")
    return "\n".join(lines)


def _format_highlights(matter):
    """Highlight manifest; [hl:ID] handles are valid add_fact sources."""
    highlights = Highlight.objects.filter(document__matter=matter).select_related(
        "document"
    )
    if not highlights:
        return "No highlights."
    lines = []
    for hl in highlights:
        text = hl.text if len(hl.text) <= 300 else hl.text[:300] + "..."
        lines.append(
            f'- [hl:{hl.id}] {hl.citation}: "{text}" '
            f"({hl.color}, importance {hl.importance})"
        )
    return "\n".join(lines)


def _format_facts(matter):
    """The timeline, oldest first, with linked source citations."""
    facts = (
        Fact.objects.filter(matter=matter)
        .order_by("date", "time")
        .prefetch_related("highlights", "documents")
    )
    if not facts:
        return "No timeline facts."
    lines = []
    for fact in facts:
        when = f"{fact.date or 'no date'}"
        if fact.time:
            when += f" {fact.time}"
        line = f"- [{when}] {fact.description} (importance {fact.importance})"
        sources = [hl.citation for hl in fact.highlights.all()[:3]]
        sources += [doc.name for doc in fact.documents.all()[:3]]
        if sources:
            line += f"\n  Sources: {', '.join(sources[:3])}"
        lines.append(line)
    return "\n".join(lines)


def _format_email_threads(matter):
    """Thread manifest: one line per Gmail thread, most recent activity
    first, so a reader that truncates the manifest loses the oldest
    threads rather than the latest."""
    threads = group_by_thread(matter.emails.dedup())
    if not threads:
        return "No synced emails."
    threads.sort(
        key=lambda emails: emails[-1].date or emails[-1].created_at, reverse=True
    )
    lines = [
        "Threads, most recent activity first. "
        "Use read_email_thread with a thread id for the full thread."
    ]
    for emails in threads:
        key = emails[0].thread_id or emails[0].gmail_id
        first, last = emails[0], emails[-1]
        dates = ""
        if first.date and last.date:
            dates = (
                f", {first.date:%Y-%m-%d}"
                if len(emails) == 1
                else f", {first.date:%Y-%m-%d} to {last.date:%Y-%m-%d}"
            )
        senders = ", ".join(dict.fromkeys(e.sender_display for e in emails if e.sender))
        line = (
            f"- [thread {key}] {thread_subject(emails)} "
            f"({len(emails)} message{'s' if len(emails) != 1 else ''}{dates})"
        )
        if senders:
            line += f"\n  From: {senders}"
        if last.snippet:
            line += f"\n  Latest: {last.snippet[:150]}"
        lines.append(line)
    return "\n".join(lines)


def _format_conversations(matter):
    """Manifest of the matter's AI conversations; [conv:ID] handles feed
    read_conversation. Conversations the attorney marked never-for-AI are
    omitted, as the in-app agent omits them."""
    conversations = (
        Conversation.objects.filter(matter=matter)
        .exclude(ai_context="never")
        .annotate(
            message_count=Count("messages"),
            last_activity=Coalesce(Max("messages__created_at"), F("created_at")),
        )
        .order_by("-last_activity")
    )
    if not conversations:
        return "No AI conversations."
    lines = []
    for conv in conversations:
        count = conv.message_count
        line = (
            f"- [conv:{conv.id}] {conv.title or 'Untitled'} "
            f"({conv.get_kind_display()}, {conv.get_llm_display()}, "
            f"{count} message{'s' if count != 1 else ''}, "
            f"last activity {timezone.localtime(conv.last_activity):%Y-%m-%d})"
        )
        if conv.ai_context == "always":
            line += " [pinned]"
        if conv.summary:
            summary = " ".join(conv.summary.split())
            line += f"\n  Summary: {summary[:300]}"
        lines.append(line)
    lines.append(
        "Use read_conversation with a conversation id for the full transcript."
    )
    return "\n".join(lines)


def _format_transcript(conversation):
    lines = [f"Conversation: {conversation.title or 'Untitled'}"]
    messages = conversation.messages.select_related("user").order_by("created_at")
    for msg in messages:
        if msg.role == "user":
            who = msg.user.get_full_name() if msg.user else "User"
        else:
            who = "Assistant"
        lines.append(f"**{who}:** {msg.content}")
    return "\n\n".join(lines)


def _money(amount):
    amount = amount or 0
    return f"-${-amount:,.2f}" if amount < 0 else f"${amount:,.2f}"


def _format_ledger(matter):
    """The matter ledger as the in-app Ledger tab computes it, plus unsent
    invoices and open payment requests; [inv:ID] handles feed read_invoice."""
    data = get_ledger_data(matter)
    value = matter.value
    sections = []

    if data["transactions"]:
        lines = [
            "Ledger (charges are sent invoices; credits are payments and credits):"
        ]
        for t in data["transactions"]:
            is_charge = t["transaction_type"] == "Charge"
            handle = f"[inv:{t['id']}] " if is_charge else ""
            line = (
                f"- [{t['date']}] {t['transaction_type']}: {handle}{t['description']} "
                f"{_money(t['amount'])}"
            )
            if t.get("invoice_status"):
                line += f" ({t['invoice_status'].title()})"
            if t.get("processor_status") == "pending":
                line += " [online payment pending settlement]"
            if t.get("affects_balance", True):
                line += f" | balance {_money(t['balance'])}"
            lines.append(line)
        sections.append("\n".join(lines))
    else:
        sections.append(
            "No ledger activity yet (no sent invoices, payments, or credits)."
        )

    totals = [f"Balance due: {_money(data['balance_due'])}"]
    if data["has_deferred"]:
        totals.append(f"Currently owed: {_money(data['currently_owed'])}")
        totals.append(
            "Deferred (recovery claim, not currently collectible): "
            f"{_money(data['deferred_total'])}"
        )
    totals.append(f"Payments received: {_money(value['invoices']['payment_sum'])}")
    totals.append(f"Credits: {_money(data['total_credits'])}")
    totals.append(
        "Work in progress (not yet billed; includes invoices not yet sent): "
        f"{_money(value['work_in_progress'])}"
    )
    sections.append("\n".join(totals))

    if data["unsent_invoices"]:
        lines = ["Invoices not yet sent (part of work in progress, not owed yet):"]
        for invoice in data["unsent_invoices"]:
            lines.append(
                f"- [inv:{invoice['id']}] Invoice {invoice['id']} "
                f"({invoice['status'].title()}, dated {invoice['date']}) "
                f"{_money(invoice['amount'])}"
            )
        sections.append("\n".join(lines))

    requests = PaymentRequest.objects.filter(matter=matter, status="SENT").order_by(
        "created_at"
    )
    if requests:
        lines = ["Open payment requests:"]
        for req in requests:
            lines.append(
                f"- {_money(req.amount_requested)} to {req.recipient_email} "
                f"({req.account} account), sent {timezone.localdate(req.created_at)}"
            )
        sections.append("\n".join(lines))

    sections.append("Use read_invoice with an invoice id for its line items.")
    return "\n\n".join(sections)


_TRUST_SEVERITY = {
    "danger": "in deficit",
    "warning": "running low",
    "ok": "ok",
    "none": "no trust held",
}


def _format_trust(matter):
    """The client's trust position and transaction history. Trust is held per
    client and pooled across that client's matters, so the figures are the
    client's, not this matter's alone."""
    client = matter.client
    if client is None:
        return "No client on this matter, so there is no trust account to report."
    pending = get_pending_client_balance(client.id)
    confirmed = get_confirmed_client_balance(client.id)
    available = client_trust_available(client.id)
    severity = trust_available_severity(available, pending)
    lines = [
        "Trust is held per client and pooled across the client's matters; "
        f"these figures are for {client.name}.",
        f"Trust balance: {_money(pending)} (confirmed {_money(confirmed)})",
        "Trust available after what is currently owed and unbilled work "
        f"across the client's matters: {_money(available)} "
        f"({_TRUST_SEVERITY[severity]})",
    ]
    history = get_client_history(client.id)
    if history:
        lines.append("Transactions:")
        for t in history:
            line = f"- [{t.date}] {t.type} {_money(t.amount)}"
            if t.method:
                line += f" by {t.method}"
            if t.description:
                line += f": {t.description}"
            if not t.confirmed:
                line += " [unconfirmed]"
            lines.append(line)
    else:
        lines.append("No trust transactions for this client.")
    return "\n".join(lines)


def _format_invoice_lines(invoice):
    sections = []
    entries = (
        TimeEntry.objects.filter(invoice=invoice)
        .select_related("user")
        .order_by("date")
    )
    if entries:
        lines = ["Time entries:"]
        for entry in entries:
            user_name = entry.user.get_full_name() if entry.user else "Unknown"
            fee = entry.hours * entry.rate if entry.rate else 0
            line = (
                f"- [{entry.date}] {entry.actions} — {entry.hours}h @ "
                f"${entry.rate}/hr ({_money(fee)}) by {user_name}"
            )
            if entry.comp:
                line += " [COMP]"
            lines.append(line)
        sections.append("\n".join(lines))
    expenses = ExpenseEntry.objects.filter(invoice=invoice).order_by("date")
    if expenses:
        lines = ["Expenses:"]
        for expense in expenses:
            label = f"{expense.category}: " if expense.category else ""
            line = (
                f"- [{expense.date}] {label}{expense.description} "
                f"({_money(expense.amount)})"
            )
            if expense.comp:
                line += " [COMP]"
            lines.append(line)
        sections.append("\n".join(lines))
    flat_fees = FlatFeeEntry.objects.filter(invoice=invoice).order_by("date")
    if flat_fees:
        lines = ["Flat fees:"]
        for fee in flat_fees:
            line = f"- [{fee.date}] {fee.description} ({_money(fee.amount)})"
            if fee.comp:
                line += " [COMP]"
            lines.append(line)
        sections.append("\n".join(lines))
    return "\n\n".join(sections) or "No line items."


SECTIONS = {
    "overview": format_matter_overview,
    "contacts": _format_contacts,
    "rates": _format_rates,
    "activity": _format_activity,
    "events": format_events,
    "tasks": _format_tasks,
    "proceedings": format_proceedings,
    "settlement": format_settlement,
    "documents": _format_documents,
    "highlights": _format_highlights,
    "timeline": _format_facts,
    "witnesses": format_witnesses,
    "emails": _format_email_threads,
    "conversations": _format_conversations,
    "ledger": _format_ledger,
    "trust": _format_trust,
}


def _matter_or_404(user, matter_id):
    matter = _get_matter(user, matter_id)
    if matter is None:
        raise ApiError(404, MATTER_404)
    return matter


def _entry_or_400(entry):
    if not isinstance(entry, dict):
        raise ApiError(400, "Request body must be a JSON object.")
    return entry


def _matter_id_or_404(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(404, MATTER_404)


def _text(entry, name, limit, minimum=0, required=False):
    """A trimmed string field, refused when too short, cut when too long."""
    value = str(entry.get(name) or "").strip()
    if len(value) < minimum:
        if required or value:
            raise ApiError(400, f"{name} is required (at least {minimum} characters).")
    return value[:limit]


def _date_or_400(entry, name, required=False):
    value = entry.get(name)
    if value in (None, ""):
        if required:
            raise ApiError(400, f"{name} is required (YYYY-MM-DD).")
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ApiError(400, f"{name} must be a date, YYYY-MM-DD.")


def _time_or_400(entry, name):
    value = entry.get(name)
    if value in (None, ""):
        return None
    try:
        return time.fromisoformat(str(value))
    except ValueError:
        raise ApiError(400, f"{name} must be a time, HH:MM.")


def _hours_or_400(value):
    if value is None or value == "" or isinstance(value, bool):
        raise ApiError(400, "hours is required (a number of hours, e.g. 0.3).")
    try:
        hours = Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ApiError(400, "hours must be a number, e.g. 0.3.")
    if hours <= 0 or hours > Decimal("99.9"):
        raise ApiError(400, "hours must be between 0.1 and 99.9.")
    return hours


def _assignable_groups(matter):
    """The groups a party may be put in on this matter: the firm's and the
    matter's own, less the system Client group (the client is set on the
    matter)."""
    return Group.objects.for_matter(matter).exclude(is_system=True)


# ---------------------------------------------------------------------------
# The service functions. Each takes the acting user, checks access the way
# the application does, and returns the payload the JSON view serialises;
# every refusal is an ApiError. apps/mcp/tools.py calls these directly, so
# Claude over the remote MCP server and a script over the token API see the
# same data and the same refusals.
# ---------------------------------------------------------------------------


def list_matters(user, q=""):
    """Accessible open matters, name-ordered; ``q`` filters by name."""
    matters = filter_matters_for_user(
        Matter.objects.filter(status="Open"), user
    ).order_by("name")
    q = (q or "").strip()
    if q:
        matters = matters.filter(name__icontains=q)
    return [{"id": m.id, "name": m.name} for m in matters]


def read_section(user, matter_id, section):
    """One section of a matter as AI-ready text."""
    matter = _matter_or_404(user, matter_id)
    if section not in SECTIONS:
        raise ApiError(400, f"Unknown section. Valid sections: {', '.join(SECTIONS)}.")
    if section in FINANCIAL_SECTIONS and not _has_financial_access(user):
        raise ApiError(403, FINANCIAL_403)
    return {
        "matter_id": matter.id,
        "matter": matter.name,
        "section": section,
        "text": SECTIONS[section](matter),
    }


def read_document(user, document_id):
    """One document's extracted text (the caller truncates)."""
    document = (
        Document.objects.select_related("matter")
        .filter(pk=document_id, matter__status="Open")
        .first()
    )
    if document is None or not user.has_matter_access(document.matter):
        raise ApiError(404, DOCUMENT_404)
    return {
        "id": document.id,
        "name": document.name,
        "matter": document.matter.name,
        "category": document.category,
        "date": str(document.date) if document.date else None,
        "ocr_status": document.ocr_status,
        "text": document.ocr_text or "",
    }


def read_email_thread(user, matter_id, thread_id):
    """One email thread in full, formatted like the in-app AI context."""
    matter = _matter_or_404(user, matter_id)
    emails = list(
        matter.emails.filter(thread_id=thread_id)
        .dedup()
        .prefetch_related("attachment_files")
    )
    if not emails:
        raise ApiError(404, THREAD_404)
    emails.sort(key=lambda e: e.date or e.created_at)
    return {
        "thread_id": thread_id,
        "subject": thread_subject(emails),
        "text": format_email_thread(emails),
    }


def search_materials(user, matter_id, body):
    """Hybrid (keyword + semantic) search over a matter's materials, run
    through the in-app agent's own search_materials handler so ranking,
    fusion, and hit shapes stay identical between the surfaces."""
    from apps.ai.agent_tools import make_agent_executor

    matter = _matter_or_404(user, matter_id)
    if not isinstance(body, dict):
        raise ApiError(400, "Body must be a JSON object.")
    execute = make_agent_executor(matter, None)
    outcome = execute([{"id": "search", "name": "search_materials", "input": body}])[0]
    payload = json.loads(outcome["content"])
    if outcome["is_error"]:
        raise ApiError(400, payload.get("error", "Search failed."))
    payload.pop("budget", None)
    return payload


def read_conversation(user, matter_id, conversation_id):
    """One AI conversation's full transcript."""
    matter = _matter_or_404(user, matter_id)
    conversation = (
        Conversation.objects.filter(matter=matter, pk=conversation_id)
        .exclude(ai_context="never")
        .first()
    )
    if conversation is None:
        raise ApiError(404, CONVERSATION_404)
    return {
        "conversation_id": conversation.id,
        "title": conversation.title or "Untitled",
        "matter": matter.name,
        "kind": conversation.get_kind_display(),
        "llm": conversation.get_llm_display(),
        "text": _format_transcript(conversation),
    }


def read_invoice(user, invoice_id):
    """One invoice with totals, balance, and line items."""
    invoice = (
        Invoice.objects.select_related("matter")
        .filter(pk=invoice_id, matter__status="Open")
        .first()
    )
    if invoice is None or not user.has_matter_access(invoice.matter):
        raise ApiError(404, INVOICE_404)
    if not _has_financial_access(user):
        raise ApiError(403, FINANCIAL_403)
    return {
        "invoice_id": invoice.id,
        "matter": invoice.matter.name,
        "status": invoice.status_display,
        "text": f"{format_invoice(invoice)}\n\n{_format_invoice_lines(invoice)}",
    }


# Create-only writes, through the same entry creators the in-app AI's
# fenced blocks use (validation, matter scoping of cited ids, name dedup).


def create_fact(user, matter_id, entry):
    """Create one timeline fact on a matter."""
    matter = _matter_or_404(user, matter_id)
    fact = _create_fact_from_entry(_entry_or_400(entry), matter, user)
    if fact is None:
        raise ApiError(400, "description is required (4-150 characters).")
    source_names = [hl.citation for hl in fact.highlights.all()[:3]]
    source_names += [doc.name for doc in fact.documents.all()[:3]]
    sources = f", source: {', '.join(source_names[:3])}" if source_names else ""
    return {
        "id": fact.id,
        "message": (
            f"- Added to timeline: **{fact.description}**"
            f" ({fact.date or 'no date'}{sources})"
        ),
    }


def create_witness(user, matter_id, entry):
    """Create one witness on a matter (name-deduped). Returns the payload
    and whether a row was created."""
    matter = _matter_or_404(user, matter_id)
    witness, created = _create_witness_from_entry(_entry_or_400(entry), matter, user)
    if witness is None:
        raise ApiError(400, "name is required (at least 2 characters).")
    if created:
        message = (
            f"- Added witness: **{witness.name}** ({witness.get_alignment_display()})"
        )
    else:
        message = f"- Already on the witness list: **{witness.name}**"
    return {"id": witness.id, "created": created, "message": message}, created


def create_task(user, entry):
    """Create one task, assigned to the user; matter optional.

    The matter is authorized here (create_task_from_ai_entry resolves by
    name with no access check), and re-pointed after creation in case a
    duplicate matter name resolved to a different matter.
    """
    entry = _entry_or_400(entry)
    matter = None
    if entry.get("matter_id") is not None:
        try:
            matter_id = int(entry["matter_id"])
        except (TypeError, ValueError):
            raise ApiError(404, MATTER_404)
        matter = _matter_or_404(user, matter_id)

    task = create_task_from_ai_entry(
        {
            "description": entry.get("description"),
            "due": entry.get("due"),
            "importance": entry.get("importance"),
            "matter": matter.name if matter else None,
        },
        user,
    )
    if task is None:
        raise ApiError(400, "description is required (at least 4 characters).")
    if matter and task.matter_id != matter.id:
        task.matter = matter
        task.save(update_fields=["matter"])

    message = f"- Created task: **{task.description}**"
    if task.date_due:
        message += f" (Due: {task.date_due})"
    return {
        "id": task.id,
        "matter": task.matter.name if task.matter else "Admin",
        "message": message,
    }


def create_time_entry(user, matter_id, entry):
    """Create one time entry on an hourly matter, as the acting user, at the
    user's rate for that matter (the matter's override, else the firm
    default). The entry is unbilled; the model never sets rate, comp or an
    invoice. Abbreviation codes are not expanded: the narrative is taken
    as written.
    """
    matter = _matter_or_404(user, matter_id)
    entry = _entry_or_400(entry)
    if matter.billing_type != "HOURLY":
        raise ApiError(
            400,
            f"{matter.name} is billed as {matter.get_billing_type_display()}; "
            "time entries are for hourly matters.",
        )
    actions = _text(entry, "actions", 2000, minimum=4, required=True)
    hours = _hours_or_400(entry.get("hours"))
    when = _date_or_400(entry, "date") or timezone.localdate()
    category = None
    category_name = _text(entry, "category", 100)
    if category_name:
        category = ActivityCategory.objects.filter(
            matter=matter, name__iexact=category_name
        ).first()
        if category is None:
            names = list(matter.activity_categories.values_list("name", flat=True))
            raise ApiError(
                400,
                f"No category {category_name!r} on this matter. "
                + (
                    f"Its categories: {', '.join(names)}."
                    if names
                    else "It has no categories; leave category out."
                ),
            )
    rate = calculate_rate_for_matter(matter, user)
    time_entry = TimeEntry.objects.create(
        matter=matter,
        user=user,
        date=when,
        actions=actions,
        hours=hours,
        rate=rate,
        category=category,
    )
    coded = f" [{category.name}]" if category else ""
    return {
        "id": time_entry.id,
        "matter": matter.name,
        "message": (
            f"- Logged {hours}h on {when}{coded}: **{actions}** "
            f"(${rate}/hr, ${hours * rate:,.2f}) [{matter.name}]"
        ),
    }


EVENT_TYPES = [value for value, _label in Event.EVENT_TYPE_CHOICES]


def create_event(user, entry):
    """Create one calendar event, on a matter or (with no matter_id) the
    firm's. Nobody is assigned unless ``assigned_to_me`` is true: an event
    with no assignee is everyone's, as the calendar treats it. The same
    rules as the event form: a start with no end runs an hour; an end date
    on the start date is dropped; times must run forward within one day.
    """
    entry = _entry_or_400(entry)
    matter = None
    if entry.get("matter_id") is not None:
        matter = _matter_or_404(user, _matter_id_or_404(entry["matter_id"]))
    description = _text(entry, "description", 255, minimum=4, required=True)
    when = _date_or_400(entry, "date", required=True)
    end_date = _date_or_400(entry, "end_date")
    if end_date is not None:
        if end_date < when:
            raise ApiError(400, "end_date must be on or after date.")
        if end_date == when:
            end_date = None
    start = _time_or_400(entry, "start_time")
    end = _time_or_400(entry, "end_time")
    if start and not end:
        end = default_end_time(start)
    if start and end and start >= end and not end_date:
        raise ApiError(400, "end_time must be after start_time.")
    event_type = _text(entry, "event_type", 50) or None
    if event_type and event_type not in EVENT_TYPES:
        raise ApiError(400, f"event_type must be one of: {', '.join(EVENT_TYPES)}.")
    event = Event.objects.create(
        user=user,
        matter=matter,
        date=when,
        end_date=end_date,
        start_time=start,
        end_time=end,
        status="Pending",
        party=_text(entry, "party", 50) or None,
        description=description,
        event_type=event_type,
        location=_text(entry, "location", 255) or None,
        details=_text(entry, "details", 10_000),
    )
    if entry.get("assigned_to_me") is True:
        event.assignees.add(user)

    label = matter.name if matter else "Firm"
    message = f"- Added event: **{description}** on {when}"
    if end_date:
        message += f" through {end_date}"
    if start:
        message += f" {start:%H:%M}"
        if end:
            message += f"-{end:%H:%M}"
    if event.party:
        message += f" with {event.party}"
    if event.location:
        message += f" ({event.location})"
    message += f" [{label}]"
    return {"id": event.id, "matter": label, "message": message}


def complete_task(user, task_id):
    """Mark one task complete, as the tasks page does: a task on a matter
    the user cannot see is a 404; an incomplete checklist blocks it; a
    task already complete is reported, not failed. The model stamps
    date_completed.
    """
    task = Task.objects.select_related("matter").filter(pk=task_id).first()
    if task is None or (task.matter_id and not user.has_matter_access(task.matter)):
        raise ApiError(404, TASK_404)
    label = task.matter.name if task.matter else "Admin"
    if task.status == STATUS_COMPLETE:
        return {
            "id": task.id,
            "matter": label,
            "changed": False,
            "message": f"- Already complete: **{task.description}** [{label}]",
        }
    if not can_complete_task(task):
        raise ApiError(400, CHECKLIST_INCOMPLETE_MESSAGE)
    task.status = STATUS_COMPLETE
    task.save()
    return {
        "id": task.id,
        "matter": label,
        "changed": True,
        "message": f"- Completed: **{task.description}** [{label}]",
    }


def create_contact(user, entry):
    """Create one contact in the firm's address book (name-deduped: a
    same-named contact is reported and its details left as they were) and,
    given matter_id with a role and a group, put the contact on that
    matter. The matter link is validated before anything is created, so a
    bad role leaves no orphan. Returns the payload and whether a contact
    row was created.
    """
    entry = _entry_or_400(entry)
    name = _text(entry, "name", 100, minimum=2, required=True)
    if len(name) > 50:
        raise ApiError(400, "name must be 50 characters or fewer.")
    matter = role = group = None
    if entry.get("matter_id") is not None:
        matter = _matter_or_404(user, _matter_id_or_404(entry["matter_id"]))
        role_name = _text(entry, "role", 50)
        role = assignable_roles().filter(name__iexact=role_name).first()
        if role is None:
            names = ", ".join(r.name for r in assignable_roles())
            raise ApiError(400, f"role is required with matter_id. Roles: {names}.")
        group_name = _text(entry, "group", 50)
        groups = _assignable_groups(matter)
        group = groups.filter(name__iexact=group_name).first()
        if group is None:
            names = ", ".join(g.name for g in groups)
            raise ApiError(
                400,
                f"group is required with matter_id. Groups on this matter: {names}.",
            )

    contact = Contact.objects.filter(name__iexact=name).first()
    created = False
    if contact is None:
        email = _text(entry, "email", 100).lower()
        if email:
            try:
                validate_email(email)
            except ValidationError:
                raise ApiError(400, "email is not a valid address.")
        phone = _text(entry, "phone", 50)
        if phone:
            phone, valid = normalize_phone(phone)
            if not valid:
                raise ApiError(400, "phone must be a 10-digit US number.")
        contact = Contact.objects.create(
            user=user,
            name=name,
            company=_text(entry, "company", 49) or None,
            email=email or None,
            phone1=phone or None,
            address=_text(entry, "address", 250) or None,
            notes=_text(entry, "notes", 249) or None,
        )
        created = True
        message = f"- Added contact: **{contact.name}**"
    else:
        message = (
            f"- Already in contacts: **{contact.name}** (details left as they were)"
        )

    if matter:
        if already_assigned(matter, contact, group, role):
            message += f"; already on {matter.name} as {role.name} in {group.name}"
        else:
            Relationship.objects.create(
                matter=matter, contact=contact, group=group, role=role
            )
            message += f"; assigned to {matter.name} as {role.name} in {group.name}"
    return {"id": contact.id, "created": created, "message": message}, created


# ---------------------------------------------------------------------------
# The token-authenticated JSON views: one per service function, each a
# serialisation of its result or of its ApiError.
# ---------------------------------------------------------------------------


def _json_api(view):
    """Answer an ApiError raised inside the view as its JSON error."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except ApiError as exc:
            return JsonResponse({"error": exc.message}, status=exc.status)

    return wrapper


@kosmos_api_auth
@require_GET
@_json_api
def api_matters(request):
    return JsonResponse(
        {"matters": list_matters(request.api_user, request.GET.get("q"))}
    )


@kosmos_api_auth
@require_GET
@_json_api
def api_matter_section(request, matter_id, section):
    return JsonResponse(read_section(request.api_user, matter_id, section))


@kosmos_api_auth
@require_GET
@_json_api
def api_document(request, document_id):
    return JsonResponse(read_document(request.api_user, document_id))


@kosmos_api_auth
@require_GET
@_json_api
def api_email_thread(request, matter_id, thread_id):
    return JsonResponse(read_email_thread(request.api_user, matter_id, thread_id))


@kosmos_api_auth
@require_http_methods(["POST"])
@_json_api
def api_search_materials(request, matter_id):
    return JsonResponse(
        search_materials(request.api_user, matter_id, _json_body(request))
    )


@kosmos_api_auth
@require_GET
@_json_api
def api_conversation(request, matter_id, conversation_id):
    return JsonResponse(read_conversation(request.api_user, matter_id, conversation_id))


@kosmos_api_auth
@require_GET
@_json_api
def api_invoice(request, invoice_id):
    return JsonResponse(read_invoice(request.api_user, invoice_id))


# GET on facts/ and witnesses/ serves the matching read section, so every
# documented section name works even though these paths are matched before
# the <str:section> route.


@kosmos_api_auth
@require_http_methods(["GET", "POST"])
@_json_api
def api_matter_facts(request, matter_id):
    """GET: the timeline section. POST: create one timeline fact."""
    if request.method == "GET":
        return JsonResponse(read_section(request.api_user, matter_id, "timeline"))
    return JsonResponse(
        create_fact(request.api_user, matter_id, _json_body(request)), status=201
    )


@kosmos_api_auth
@require_http_methods(["GET", "POST"])
@_json_api
def api_matter_witnesses(request, matter_id):
    """GET: the witnesses section. POST: create one witness (name-deduped)."""
    if request.method == "GET":
        return JsonResponse(read_section(request.api_user, matter_id, "witnesses"))
    payload, created = create_witness(request.api_user, matter_id, _json_body(request))
    return JsonResponse(payload, status=201 if created else 200)


@kosmos_api_auth
@require_http_methods(["POST"])
@_json_api
def api_create_task(request):
    return JsonResponse(create_task(request.api_user, _json_body(request)), status=201)


@kosmos_api_auth
@require_http_methods(["POST"])
@_json_api
def api_matter_time(request, matter_id):
    return JsonResponse(
        create_time_entry(request.api_user, matter_id, _json_body(request)),
        status=201,
    )


@kosmos_api_auth
@require_http_methods(["POST"])
@_json_api
def api_create_event(request):
    return JsonResponse(create_event(request.api_user, _json_body(request)), status=201)


@kosmos_api_auth
@require_http_methods(["POST"])
@_json_api
def api_complete_task(request, task_id):
    return JsonResponse(complete_task(request.api_user, task_id))


@kosmos_api_auth
@require_http_methods(["POST"])
@_json_api
def api_create_contact(request):
    payload, created = create_contact(request.api_user, _json_body(request))
    return JsonResponse(payload, status=201 if created else 200)

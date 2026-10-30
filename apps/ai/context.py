"""
Context assembly for AI chat.

Gathers matter data for the system prompt, organized by importance
(a 1-7 scale on the records; get_importance_tier maps it to four tiers):
1. Matter overview, contacts, proceedings (always included)
2. Critical evidence (importance 5-7) - across all content types
3. High importance (importance 4) - across all content types
4. Medium importance (importance 3) - across all content types
5. Reference materials (importance 1-2) - across all content types
6. Administrative info (tasks, events, settlement)

Content types with importance ratings:
- Documents, Highlights, Facts, Emails
- Reference Conversations (automatically HIGH importance since explicitly flagged)
- Case Law (ai_context field controls inclusion)

Documents, Case Law, Emails and Conversations have a three-state ai_context
field:
- "always": Always included with full content
- "auto": Included by intelligent selector based on relevance to user's question
- "never": Completely excluded from context

Time entries are included as administrative data with invoice relationships.
"""

import logging
from pathlib import Path

from django.db.models import F
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.activity.time.models import TimeEntry
from apps.calendar.models import Event
from apps.matters.proceedings.models import Proceeding
from apps.matters.settlement.models import SettlementEntry
from apps.settings.models import Firm
from apps.tasks.models import Task

logger = logging.getLogger(__name__)

# Path to the legal AI instructions file
LEGAL_PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "legal.md"


REQUEST_INFO_TEMPLATE = """## Current Date

Today is {request_date}. Treat this as the current date when reasoning
about deadlines, elapsed time, or anything time-sensitive.

Messages in the conversation history are prefixed with a bracketed
date-time stamp (e.g. [Jul 04, 2026 02:15 PM]) showing when each was
sent, so you can follow the chronology. The stamps are metadata added by
the system. Never begin your own replies with one.

## Requesting Party

- Name: {user_name}
- Email: {user_email}
- Title: {role_title}
- Law Firm: {firm_name}

## Firm Team

Firm personnel and their titles. These are authoritative — when any of these
names appears in the matter record (time entries, notes, correspondence), use
the title listed here; do not infer anyone's role:

{team_lines}
"""


def build_request_info(user):
    """The Requesting Party + Firm Team sections of the system prompt.

    The roster anchors every firm name the model may meet in the matter
    record to an authoritative title, so it never guesses a colleague's
    role. Titles come from CustomUser.title, falling back to the attorney
    flag (see title_display)."""
    if not user:
        return ""
    company = Firm.objects.first()
    team_lines = "\n".join(
        f"- {u.full_name} — {u.title_display}"
        for u in CustomUser.objects.filter(is_active=True).order_by(
            "first_name", "username"
        )
    )
    return REQUEST_INFO_TEMPLATE.format(
        request_date=timezone.localdate().strftime("%A, %B %d, %Y"),
        user_name=user.get_full_name(),
        user_email=user.email,
        role_title=user.title_display,
        firm_name=company.name if company else "",
        team_lines=team_lines,
    )


def build_chat_history(conversation) -> list[dict]:
    """Provider-ready history for a conversation, shared by the case
    and intake chats.

    Every message is prefixed with its sent date-time so the model can
    follow the chronology (REQUEST_INFO_TEMPLATE tells it the stamps are
    system metadata). When more than one person has participated, user
    messages also carry the sender's name.
    """
    messages = list(conversation.messages.select_related("user"))

    user_names = {
        (msg.user.get_full_name() or msg.user.username)
        for msg in messages
        if msg.role == "user" and msg.user
    }
    multi_user = len(user_names) > 1

    history = []
    for msg in messages:
        stamp = timezone.localtime(msg.created_at).strftime("%b %d, %Y %I:%M %p")
        content = msg.content
        if multi_user and msg.role == "user" and msg.user:
            name = msg.user.get_full_name() or msg.user.username
            content = f"[{name}]: {content}"
        history.append({"role": msg.role, "content": f"[{stamp}] {content}"})
    return history


# Conventions for citing matter sources in chat prose. Appended to the
# classic chat context in tasks.py alongside the write protocols; chat
# messages render as markdown, so the links are clickable.
SOURCE_LINKING = """CITING SOURCES. Documents and highlights in the context above carry
[doc:ID] and [hl:ID] handles next to their names. When your answer
draws on one, cite it inline as a markdown link:
- highlight: [Smith Dep. p.34](/case/highlights/88/link/) - the link
  opens the source document positioned at the highlight; use the
  highlight's citation as the link text.
- document: [Engagement Letter](/case/documents/17/view/) - only when
  no highlight covers the point.
Place each citation AFTER the sentence it supports: end the sentence
with its period, then the citation. ("The contract was signed on
March 3. [Smith Dep. p.34](/case/highlights/88/link/)")
Prefer the highlight whenever one supports the point. A highlight link
already identifies its document, so never add a second link to the
document itself for the same point. Documents and highlights are the
ONLY citable sources: never cite tasks, time entries, timeline facts,
events, or other case records as authority for a point. Use
only ids whose handles appear in this context; never invent or guess
an id, and never write the raw [doc:ID] or [hl:ID] handles
in your reply."""


def load_legal_prompt(jurisdiction: str = "") -> str:
    """
    Load the legal AI instructions from apps/ai/prompts/legal.md.

    This file is read fresh on each call so edits take effect immediately.
    If *jurisdiction* is provided, ``[JURISDICTION]`` placeholders are replaced.
    """
    try:
        if LEGAL_PROMPT_FILE.exists():
            text = LEGAL_PROMPT_FILE.read_text(encoding="utf-8")
        else:
            logger.warning(f"Legal prompt file not found: {LEGAL_PROMPT_FILE}")
            return "You are a legal assistant. Be accurate and cite sources."
    except Exception as e:
        logger.error(f"Error reading legal prompt file: {e}")
        return "You are a legal assistant. Be accurate and cite sources."

    if jurisdiction:
        text = text.replace("[JURISDICTION]", jurisdiction)

    return text


def format_matter_overview(matter) -> str:
    """Format basic matter information."""
    lines = [
        f"Name: {matter.name}",
        f"Status: {matter.status}",
        f"Work Status: {matter.work_status or 'Not set'}",
        f"Practice Area: {matter.practice_area.name if matter.practice_area else 'Not specified'}",
        f"Description: {matter.description or 'No description'}",
        f"Start Date: {matter.date_start}",
        f"Client Reference: {matter.client_reference_id or 'None'}",
    ]
    if matter.client:
        lines.append(f"Primary Client: {matter.client.name}")
    return "\n".join(lines)


def format_witnesses(matter) -> str:
    """Format the witness list."""
    witnesses = matter.witnesses.all()

    if not witnesses:
        return "No witnesses recorded."

    lines = []
    for witness in witnesses:
        line = (
            f"- {witness.name} ({witness.get_alignment_display()},"
            f" importance {witness.importance})"
        )
        if witness.affiliation:
            line += f" - {witness.affiliation}"
        if witness.knowledge:
            line += f"\n  Knows: {witness.knowledge[:300]}"
        lines.append(line)

    return "\n".join(lines)


def format_proceedings(matter) -> str:
    """Format court proceedings."""
    proceedings = Proceeding.objects.filter(matter=matter)

    if not proceedings:
        return "No court proceedings."

    lines = []
    for proc in proceedings:
        primary = " [PRIMARY]" if proc.primary else ""
        lines.append(
            f"- {proc.forum}: Case #{proc.case_number}{primary}\n"
            f"  Filed: {proc.date_filed}, Status: {proc.status}"
        )

    return "\n".join(lines)


def format_tasks(matter) -> str:
    """Format tasks, pending first."""
    # Pending tasks have no completion date, and PostgreSQL sorts NULLs last
    # in ascending order: say so explicitly, or the 20-row cut is filled with
    # finished work. Within each group the most important come first (7 is
    # the top of the scale), then the soonest due.
    tasks = Task.objects.filter(matter=matter).order_by(
        F("date_completed").desc(nulls_first=True),
        "-importance",
        F("date_due").asc(nulls_last=True),
    )[:20]

    if not tasks:
        return "No tasks."

    lines = []
    for task in tasks:
        status_icon = "[DONE]" if task.date_completed else "[PENDING]"
        line = f"- {status_icon} P{task.importance}: {task.description}"
        if task.date_due:
            line += f" (Due: {task.date_due})"
        lines.append(line)

    return "\n".join(lines)


def format_events(matter) -> str:
    """Format events, upcoming first."""
    # Upcoming events
    events = Event.objects.filter(
        matter=matter, date__gte=timezone.now().date()
    ).order_by("date")[:15]

    # Also get recent past events
    past_events = Event.objects.filter(
        matter=matter, date__lt=timezone.now().date()
    ).order_by("-date")[:5]

    all_events = list(events) + list(past_events)

    if not all_events:
        return "No events scheduled."

    lines = []
    for event in all_events:
        line = f"- [{event.date}] {event.description}"
        if event.party:
            line += f" with {event.party}"
        if event.location:
            line += f" ({event.location})"
        lines.append(line)

    return "\n".join(lines)


def format_time_entries(matter, include_billing=False) -> str:
    """Format time entries: the work done, by whom and for how long.

    With ``include_billing`` each entry also carries its rate, fee, comp
    flag and the invoice it sits on. The Activity screens show those to
    every user who can see the matter, so every requesting user gets them;
    only a run for no user leaves them out.
    """
    entries = (
        TimeEntry.objects.filter(matter=matter)
        .select_related("user", "invoice")
        .order_by("-date")
    )

    if not entries:
        return "No time entries."

    lines = []
    for entry in entries:
        user_name = entry.user.get_full_name() if entry.user else "Unknown"
        if not include_billing:
            lines.append(
                f"- [{entry.date}] {entry.actions} — {entry.hours}h by {user_name}"
            )
            continue
        fee = entry.hours * entry.rate if entry.rate else 0
        line = f"- [{entry.date}] {entry.actions} — {entry.hours}h @ ${entry.rate}/hr (${fee:,.2f})"
        line += f" by {user_name}"
        if entry.comp:
            line += " [COMP]"
        if entry.invoice:
            line += f" [Invoice #{entry.invoice.id}, {entry.invoice.status}]"
        lines.append(line)

    return "\n".join(lines)


def format_invoice(invoice) -> str:
    """Format a single invoice with totals, balance, and metadata."""
    from apps.activity.expenses.models import ExpenseEntry
    from apps.activity.flat_fees.models import FlatFeeEntry
    from apps.activity.time.models import TimeEntry

    value = invoice.value
    lines = [
        f"**Invoice #{invoice.id}** — {invoice.status_display}",
        f"Period covered: through {invoice.date_limit}",
        f"Date issued: {invoice.date_issued}",
    ]

    lines.append(
        f"Fees: ${value['net_fees']:,.2f} (gross ${value['gross_fees']:,.2f}, "
        f"comp ${value['comp_fees']:,.2f})"
    )
    lines.append(
        f"Expenses: ${value['net_expenses']:,.2f} (gross ${value['gross_expenses']:,.2f}, "
        f"comp ${value['comp_expenses']:,.2f})"
    )
    lines.append(
        f"Flat fees: ${value['net_flat_fees']:,.2f} (gross ${value['gross_flat_fees']:,.2f}, "
        f"comp ${value['comp_flat_fees']:,.2f})"
    )
    if invoice.discount:
        lines.append(f"Discount: ${invoice.discount:,.2f}")
    lines.append(f"Total: ${value['final_total']:,.2f}")
    lines.append(f"Balance remaining: ${invoice.amount_remaining:,.2f}")

    time_count = TimeEntry.objects.filter(invoice=invoice).count()
    expense_count = ExpenseEntry.objects.filter(invoice=invoice).count()
    flat_count = FlatFeeEntry.objects.filter(invoice=invoice).count()
    lines.append(
        f"Line items: {time_count} time, {expense_count} expense, {flat_count} flat fee"
    )

    if invoice.message:
        lines.append(f"Message: {invoice.message}")
    if invoice.comment:
        lines.append(f"Comment: {invoice.comment}")

    return "\n".join(lines)


def format_settlement(matter) -> str:
    """Format settlement information."""
    entries = SettlementEntry.objects.filter(matter=matter).order_by("-date")

    if not entries:
        return "No settlement information."

    lines = []
    for entry in entries:
        line = f"- [{entry.date}] {entry.type}: ${entry.amount:,.2f}"
        if entry.notes:
            line += f" - {entry.notes}"
        lines.append(line)

    return "\n".join(lines)

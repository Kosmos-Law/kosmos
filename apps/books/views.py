"""Books: the chart of accounts, the journal and the statements.

Every page sets app "books" for the sidebar and a subapp for the Books
sub-navigation (templates/books/main.html). Lists follow the practice
apps' shape: a full page that includes a list partial, and the partial
re-fetched on an HX-Trigger (`booksChanged`) after a change.
"""

import json
from collections import OrderedDict

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.books import intuit, ledger, sync
from apps.books.chart import seed_default_chart
from apps.books.forms import (
    AccountForm,
    JournalEntryForm,
    JournalLineFormSet,
    PeriodForm,
)
from apps.books.models import ZERO, Account, JournalEntry
from apps.books.tax_lines import TAX_LINES, line_label
from apps.settings.models import Firm
from utils.toasts import toast_error, toast_success

BOOKS_TRIGGER = "booksChanged"


def _changed(extra=None):
    triggers = {BOOKS_TRIGGER: ""}
    if extra:
        triggers.update(extra)
    return HttpResponse(status=204, headers={"HX-Trigger": json.dumps(triggers)})


def _firm():
    return Firm.objects.first()


MIRROR_MSG = (
    "Books mirrors QuickBooks Online while the firm's books are kept there; "
    "make the change in QuickBooks and it arrives with the next sync."
)


def _mirrored():
    """A refusal for a write while the mirror is on, else None."""
    if intuit.connection() is not None:
        return HttpResponseBadRequest(MIRROR_MSG)
    return None


@login_required
@require_POST
def books_sync(request):
    """Mirror the company now. From Books (htmx) the lists reload and a
    toast says what happened; from Settings > Integrations (a form) the
    page comes back with the same in a toast."""
    try:
        summary = sync.run().summary
        kind, message = "success", summary
    except intuit.NotConnected:
        kind, message = "error", "QuickBooks is not connected."
    except (intuit.QuickBooksError, ValidationError, KeyError, ValueError) as exc:
        kind, message = "error", f"QuickBooks sync failed: {exc}"
    if request.headers.get("HX-Request"):
        response = _changed()
        (toast_success if kind == "success" else toast_error)(response, message)
        return response
    from apps.settings.integrations import PENDING_TOAST_KEY

    request.session[PENDING_TOAST_KEY] = {"type": kind, "message": message}
    return redirect("settings:integrations-index")


@login_required
def books_index(request):
    return redirect("books:accounts-index")


# ------------------------------------------------------------ chart of accounts


TREE_COLLAPSED_KEY = "books_tree_collapsed"
TREE_INACTIVE_KEY = "books_tree_show_inactive"


def _nest(rows, collapsed):
    """Rows of one kind as a forest: each node is {row, total, children,
    key, collapsed}, the total being the account's own balance plus its
    descendants'. A child whose parent is not among the rows (inactive
    and hidden, say) is shown at the top."""
    by_id = {row.account.id: row for row in rows}
    children = {}
    roots = []
    for row in rows:
        parent_id = row.account.parent_id
        if parent_id in by_id:
            children.setdefault(parent_id, []).append(row)
        else:
            roots.append(row)

    def node(row):
        kids = [node(child) for child in children.get(row.account.id, [])]
        key = f"account_{row.account.id}"
        return {
            "row": row,
            "children": kids,
            "total": row.amount + sum((k["total"] for k in kids), ZERO),
            "key": key,
            "collapsed": key in collapsed,
        }

    return [node(row) for row in roots]


def _accounts_context(request):
    """The chart as a tree: type, then kind (the subtype), then account,
    with a total on every branch. Which branches are folded and whether
    inactive accounts show are remembered in the session."""
    collapsed = request.session.get(TREE_COLLAPSED_KEY, {})
    show_inactive = request.session.get(TREE_INACTIVE_KEY, False)
    rows = ledger.balances(as_of=timezone.localdate(), include_inactive=show_inactive)
    by_subtype = {}
    for row in rows:
        by_subtype.setdefault(row.account.subtype, []).append(row)
    types = []
    for type_key, type_label in Account.TYPE_CHOICES:
        kinds = []
        for subtype, label, kind_type in Account.SUBTYPES:
            if kind_type != type_key or subtype not in by_subtype:
                continue
            accounts = by_subtype[subtype]
            kinds.append(
                {
                    "key": f"kind_{subtype}",
                    "label": label,
                    "nodes": _nest(accounts, collapsed),
                    "total": sum((r.amount for r in accounts), ZERO),
                    "collapsed": f"kind_{subtype}" in collapsed,
                }
            )
        if kinds:
            types.append(
                {
                    "key": f"type_{type_key}",
                    "label": type_label,
                    "kinds": kinds,
                    "total": sum((k["total"] for k in kinds), ZERO),
                    "collapsed": f"type_{type_key}" in collapsed,
                }
            )
    return {
        "types": types,
        "empty": not Account.objects.exists(),
        "any_collapsed": bool(collapsed),
        "show_inactive": show_inactive,
    }


@login_required
def accounts_index(request):
    return render(
        request,
        "books/accounts/main.html",
        {"app": "books", "subapp": "accounts"} | _accounts_context(request),
    )


@login_required
def accounts_list(request):
    return render(request, "books/accounts/list.html", _accounts_context(request))


@login_required
@require_POST
def tree_toggle(request):
    """Fold or unfold one branch; the page already swapped it, so nothing
    is rendered."""
    node = request.POST.get("node", "")
    if not node.startswith(("type_", "kind_", "account_")):
        return HttpResponseBadRequest()
    collapsed = request.session.get(TREE_COLLAPSED_KEY, {})
    if node in collapsed:
        del collapsed[node]
    else:
        collapsed[node] = True
    request.session[TREE_COLLAPSED_KEY] = collapsed
    return HttpResponse(status=204)


@login_required
@require_POST
def tree_fold(request, state):
    """Fold or unfold every branch at once, and re-render the tree."""
    if state == "collapse":
        request.session[TREE_COLLAPSED_KEY] = {
            key: True
            for key in [f"type_{t}" for t, _ in Account.TYPE_CHOICES]
            + [f"kind_{k}" for k, _, _ in Account.SUBTYPES]
        }
    else:
        request.session[TREE_COLLAPSED_KEY] = {}
    return render(request, "books/accounts/list.html", _accounts_context(request))


@login_required
@require_POST
def tree_show_inactive(request):
    request.session[TREE_INACTIVE_KEY] = not request.session.get(
        TREE_INACTIVE_KEY, False
    )
    return render(request, "books/accounts/list.html", _accounts_context(request))


@login_required
@require_POST
def accounts_seed(request):
    if refused := _mirrored():
        return refused
    added = seed_default_chart()
    response = _changed()
    toast_success(response, f"{added} accounts added")
    return response


@login_required
def account_add(request):
    if refused := _mirrored():
        return refused
    form = AccountForm(request.POST or None, use_required_attribute=False)
    if request.method == "POST" and form.is_valid():
        form.save()
        return _changed()
    return render(request, "books/accounts/form.html", {"form": form})


@login_required
def account_edit(request, pk):
    account = get_object_or_404(Account, pk=pk)
    form = AccountForm(
        request.POST or None, instance=account, use_required_attribute=False
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return _changed()
    return render(
        request, "books/accounts/form.html", {"form": form, "account": account}
    )


@login_required
def account_ledger(request, pk):
    account = get_object_or_404(Account, pk=pk)
    period_form = PeriodForm(request.GET or None)
    start, end = period_form.period()
    context = {
        "app": "books",
        "subapp": "accounts",
        "account": account,
        "period_form": period_form,
        "start": start,
        "end": end,
    } | ledger.general_ledger(account, start, end)
    return render(request, "books/accounts/ledger.html", context)


# ------------------------------------------------------------------- journal


def _journal_context(request):
    period_form = PeriodForm(request.GET or None)
    start, end = period_form.period()
    entries = (
        JournalEntry.objects.filter(date__gte=start, date__lte=end)
        .prefetch_related("lines__account")
        .select_related("reverses")
    )
    return {
        "entries": entries,
        "period_form": period_form,
        "start": start,
        "end": end,
    }


@login_required
def journal_index(request):
    return render(
        request,
        "books/journal/main.html",
        {"app": "books", "subapp": "journal"} | _journal_context(request),
    )


@login_required
def journal_list(request):
    return render(request, "books/journal/list.html", _journal_context(request))


@login_required
def entry_detail(request, pk):
    entry = get_object_or_404(
        JournalEntry.objects.prefetch_related("lines__account"), pk=pk
    )
    return render(request, "books/journal/detail.html", {"entry": entry})


def _entry_form(request, entry=None):
    form = JournalEntryForm(
        request.POST or None, instance=entry, use_required_attribute=False
    )
    formset = JournalLineFormSet(request.POST or None, instance=entry)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        lines = [
            line_form.save(commit=False)
            for line_form in formset.forms
            if line_form.has_changed() and not line_form.is_blank
        ]
        try:
            with transaction.atomic():
                if entry is None:
                    ledger.post(
                        form.cleaned_data["date"], form.cleaned_data["memo"], lines
                    )
                else:
                    form.save()
                    ledger.replace_lines(entry, lines)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return _changed()
    return render(
        request,
        "books/journal/form.html",
        {"form": form, "formset": formset, "entry": entry},
    )


@login_required
def entry_add(request):
    if refused := _mirrored():
        return refused
    return _entry_form(request)


@login_required
def entry_edit(request, pk):
    if refused := _mirrored():
        return refused
    entry = get_object_or_404(JournalEntry, pk=pk)
    if not entry.is_manual:
        return HttpResponseBadRequest("Only a manual entry can be edited.")
    return _entry_form(request, entry)


@login_required
@require_POST
def entry_delete(request, pk):
    if refused := _mirrored():
        return refused
    entry = get_object_or_404(JournalEntry, pk=pk)
    if not entry.is_manual or hasattr(entry, "reversed_by"):
        return HttpResponseBadRequest("Reverse this entry instead of deleting it.")
    entry.delete()
    return _changed()


@login_required
@require_POST
def entry_reverse(request, pk):
    if refused := _mirrored():
        return refused
    entry = get_object_or_404(JournalEntry, pk=pk)
    try:
        ledger.reverse(entry, timezone.localdate())
    except ValidationError as exc:
        response = _changed()
        toast_error(response, "; ".join(exc.messages))
        return response
    return _changed()


# ---------------------------------------------------------------- statements


@login_required
def statements_index(request):
    return redirect("books:profit-and-loss")


def _statement(request, subapp, template, build):
    period_form = PeriodForm(request.GET or None)
    start, end = period_form.period()
    context = {
        "app": "books",
        "subapp": "statements",
        "statement": subapp,
        "period_form": period_form,
        "start": start,
        "end": end,
        "firm": _firm(),
    } | build(start, end)
    return render(request, template, context)


@login_required
def trial_balance_view(request):
    return _statement(
        request,
        "trial-balance",
        "books/statements/trial-balance.html",
        lambda start, end: ledger.trial_balance(end, end.replace(month=1, day=1)),
    )


@login_required
def profit_and_loss_view(request):
    return _statement(
        request,
        "profit-and-loss",
        "books/statements/profit-and-loss.html",
        ledger.profit_and_loss,
    )


@login_required
def balance_sheet_view(request):
    return _statement(
        request,
        "balance-sheet",
        "books/statements/balance-sheet.html",
        lambda start, end: ledger.balance_sheet(end, end.replace(month=1, day=1)),
    )


def _tax_summary(firm, start, end):
    """Income and expense totals folded onto the lines of the firm's
    return, in the return's order, with the accounts that fed each line
    and any account the return has no line for."""
    form = firm.tax_form if firm else "schedule_c"
    field = "schedule_c_line" if form == "schedule_c" else "form_1120s_line"
    statement = ledger.profit_and_loss(start, end)
    by_line = OrderedDict((line, []) for line, _ in TAX_LINES[form])
    unmapped = []
    for row in statement["income"] + statement["expenses"]:
        line = getattr(row.account, field)
        if line in by_line:
            by_line[line].append(row)
        else:
            unmapped.append(row)
    lines = []
    for line, rows in by_line.items():
        if rows:
            lines.append(
                {
                    "line": line,
                    "label": line_label(form, line),
                    "rows": rows,
                    "total": sum(r.amount for r in rows),
                }
            )
    return {
        "tax_form": form,
        "tax_form_label": dict(Firm._meta.get_field("tax_form").choices)[form],
        "lines": lines,
        "unmapped": unmapped,
    } | statement


@login_required
def tax_summary_view(request):
    firm = _firm()
    return _statement(
        request,
        "tax-summary",
        "books/statements/tax-summary.html",
        lambda start, end: _tax_summary(firm, start, end),
    )

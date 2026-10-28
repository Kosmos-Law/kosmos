"""The firm-wide feature switches an administrator sets under Settings >
Features. Each is a column on the Firm record; a server with no Firm row
yet has every feature on.

Accounting is the ledger behind invoicing and trust, under /accounting/
(apps/accounting). The case file is the case builder's matter workspace under /case/
(documents, highlights, timeline, witnesses, emails, labels, search and
the AI tab). The gates are in apps/accounts/middleware.py; the sidebar, the matter header, the
case shell's tabs and the firm-wide search read the same switches.
"""


def _firm():
    from apps.settings.models import Firm

    return Firm.objects.only("case_file_enabled", "accounting_enabled").first()


def case_file_enabled():
    firm = _firm()
    return firm is None or firm.case_file_enabled


def accounting_enabled():
    """Accounting is off by default, unlike the case builder: a firm that keeps
    its books elsewhere never sees it. A server with no Firm row has it
    off too."""
    firm = _firm()
    return firm is not None and firm.accounting_enabled

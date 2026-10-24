from urllib.parse import quote

from django.db import models
from django.urls import reverse

from utils.models import AuditMixin

# The returns the chart of accounts carries a tax-line mapping for.
TAX_FORM_CHOICES = (
    ("schedule_c", "Schedule C (Form 1040)"),
    ("1120s", "Form 1120-S"),
)
BASIS_CHOICES = (("cash", "Cash"), ("accrual", "Accrual"))

# Models offered for AI quick task entry - the cheap tier of each provider
# the app integrates. The picked model only matters when quick_task_ai is on;
# a missing API key just fails the call and the fuzzy matcher takes over.
QUICK_TASK_AI_MODELS = (
    ("gemini-flash", "Gemini Flash"),
    ("claude-sonnet", "Claude Sonnet"),
)


class Firm(AuditMixin):
    name = models.CharField(max_length=255)
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    billing_email = models.EmailField(blank=True)
    invoice_bcc = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Comma-separated addresses BCC'd on every invoice email.",
    )
    # Cc + Reply-To on template emails sent to intakes. Must be a human
    # inbox, not the Mailgun intake pipeline address - the pipeline would
    # log our own outbound copies as duplicate notes.
    intake_email = models.EmailField(blank=True)
    # One logo, ideally one mid-tone colour on a transparent ground. Such a
    # logo is a shape: the themed pages (sign-in, pay, intake) repaint it
    # in their text colour (components/firm-logo.html), the invoice PDF
    # takes a near-black copy, and email, which can't be repainted, shows
    # the mid-tone as uploaded. Both facts are worked out at upload
    # (apps/settings/logo.py). The email logo is an optional override for
    # logos that can't be repainted, such as several colours on a light
    # ground. Email falls back to the logo when it is blank.
    logo = models.ImageField(upload_to="company/", blank=True, null=True)
    logo_one_colour = models.BooleanField(default=False, editable=False)
    logo_print = models.ImageField(
        upload_to="company/", blank=True, null=True, editable=False
    )
    logo_email = models.ImageField(upload_to="company/", blank=True, null=True)
    jurisdiction = models.CharField(max_length=100, blank=True)
    # Wording that depends on a firm's own fee agreement. Blank leaves the
    # sentence out of the document.
    invoice_trust_note = models.TextField(blank=True, default="")
    payment_terms = models.CharField(max_length=255, blank=True, default="")
    # Quick task entry: the fuzzy "Matter - description" prefix matcher is
    # the default; AI interpretation of the whole line is an opt-in add-on.
    quick_task_ai = models.BooleanField(default=False)
    quick_task_ai_model = models.CharField(
        max_length=20, choices=QUICK_TASK_AI_MODELS, default="gemini-flash"
    )
    # AI provider keys entered under Settings > Integrations, encrypted
    # (apps/settings/ai.py). A key in config/.env takes precedence.
    gemini_api_key = models.TextField(blank=True, default="")
    anthropic_api_key = models.TextField(blank=True, default="")
    # Every user must sign in with an authenticator app. A user without one
    # is taken to Settings > Security after signing in and can go nowhere
    # else until it is set up (apps/accounts/middleware.py).
    require_authenticator = models.BooleanField(default=False)
    # The case builder's features, on or off for the whole firm (Settings >
    # Features, admins only). Read through apps/settings/features.py.
    case_file_enabled = models.BooleanField(default=True)
    library_enabled = models.BooleanField(default=True)
    # Books, the ledger behind invoicing and trust (apps/books). Off until
    # an administrator turns it on: a firm that keeps its books elsewhere
    # never sees it.
    books_enabled = models.BooleanField(default=False)
    # The return the firm files and the basis it keeps its books on. The
    # chart's tax lines are read by form (apps/books/tax_lines.py); the
    # basis decides when invoicing posts revenue.
    tax_form = models.CharField(
        max_length=12, choices=TAX_FORM_CHOICES, default="schedule_c"
    )
    accounting_basis = models.CharField(
        max_length=8, choices=BASIS_CHOICES, default="cash"
    )

    class Meta:
        verbose_name_plural = "firms"

    def __str__(self):
        return self.name

    @property
    def email_logo(self):
        """The logo to embed in outgoing email: the email slot, else the logo."""
        return self.logo_email or self.logo

    @property
    def pdf_logo(self):
        """The logo for invoice PDFs: the near-black copy of a one-colour
        logo, else the logo as uploaded."""
        if self.logo_one_colour and self.logo_print:
            return self.logo_print
        return self.logo


def logo_urls(firm):
    """Context for components/firm-logo.html on a themed page: the logo's
    URL, blank without one, and whether the page repaints it. It points at
    this site (accounts:firm-logo), not the media bucket, because the
    repaint is a CSS mask and a mask image must be same-origin. The file name in the query
    string busts the cache on a new upload."""
    if not firm or not firm.logo:
        return {"logo_url": "", "logo_one_colour": False}
    return {
        "logo_url": reverse("accounts:firm-logo") + "?v=" + quote(firm.logo.name),
        "logo_one_colour": firm.logo_one_colour,
    }

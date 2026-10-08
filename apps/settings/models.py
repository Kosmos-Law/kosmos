from django.db import models

from utils.models import AuditMixin

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
    # Three logo slots, one per surface. The logo is the master: light
    # themes, PDFs and the public intake pages. The other two stand in
    # for it where it would wash out - a light-ink twin on the dark
    # themes, and art on a solid ground in email, where the reader's
    # theme is unknowable. Each falls back to the logo when blank.
    logo = models.ImageField(upload_to="company/", blank=True, null=True)
    logo_dark = models.ImageField(upload_to="company/", blank=True, null=True)
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

    class Meta:
        verbose_name_plural = "firms"

    def __str__(self):
        return self.name

    @property
    def email_logo(self):
        """The logo to embed in outgoing email: the email slot, else the logo."""
        return self.logo_email or self.logo


def logo_urls(firm):
    """Context for components/firm-logo.html on a themed page: the logo's
    URL and, when uploaded, its dark-theme twin's. Both blank without a
    logo - the dark twin never stands alone."""
    if not firm or not firm.logo:
        return {"logo_url": "", "logo_dark_url": ""}
    return {
        "logo_url": firm.logo.url,
        "logo_dark_url": firm.logo_dark.url if firm.logo_dark else "",
    }

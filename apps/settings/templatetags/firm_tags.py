from django import template

from apps.settings.models import Firm, logo_urls

register = template.Library()


@register.inclusion_tag("components/auth-brand.html")
def auth_brand():
    """The auth-card title block (login, password reset, error pages): the
    firm's uploaded logo when one is set, the Kosmos wordmark otherwise.
    With a dark-theme logo uploaded too, both ship and the theme shows one
    (components/firm-logo.html).

    Swallows every lookup failure because the 500 page renders through
    this tag - when the database is the thing that's down, the brand
    block must still degrade to the wordmark instead of raising."""
    urls = logo_urls(None)
    firm_name = ""
    try:
        firm = Firm.objects.first()
        if firm:
            firm_name = firm.name
            urls = logo_urls(firm)
    except Exception:
        pass
    return {**urls, "firm_name": firm_name}

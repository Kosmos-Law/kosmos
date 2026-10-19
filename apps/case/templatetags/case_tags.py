from django import template

from apps.case import tabs

register = template.Library()


@register.simple_tag(takes_context=True)
def case_tabs(context, matter):
    """The tabs the case nav lists for this user and matter, in order."""
    request = context.get("request")
    user = getattr(request, "user", None)
    return tabs.listed_for(user, matter.id)

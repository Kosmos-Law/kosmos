from django import template

from apps.mail.google import emails_tab_available as _emails_tab_available

register = template.Library()


@register.simple_tag
def emails_tab_available(matter_id):
    """Whether the matter's case nav lists its Emails tab."""
    return _emails_tab_available(matter_id)

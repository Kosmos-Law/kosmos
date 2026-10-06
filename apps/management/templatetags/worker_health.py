from django import template

from config.health import worker_looks_down

register = template.Library()


@register.simple_tag
def background_worker_down():
    """True when the background worker (qcluster) looks stopped.

    Cached briefly (see config.health.worker_looks_down), so it is cheap to
    ask on every page render and every OCR badge poll.
    """
    return worker_looks_down()

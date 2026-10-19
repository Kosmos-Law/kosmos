"""The case shell's tab registry.

The shell in apps/case/views.py knows no tab by name. Every tab of the
matter's working file is registered here: the case app registers its own
in CaseConfig.ready() (apps/case/registrations.py), and the apps that
contribute a tab register theirs the same way, the AI tab from apps.ai
and the Emails tab from apps.mail, so the case builder never imports the
apps that sit on top of it. The nav lists the registered tabs in order,
the tab-content view dispatches to each tab's data function, and the
tab remembered in the session is checked against the registry.
"""

from dataclasses import dataclass
from typing import Callable


def _always(user, matter_id):
    return True


@dataclass(frozen=True)
class Tab:
    name: str
    label: str
    # URL names; both take the matter id as ``matter_id``.
    index_url: str  # the full page
    list_url: str  # the list partial the wrapper re-fetches
    template: str  # the tab's template, rendered inside the wrapper
    data: Callable  # (request, matter) -> template context
    order: int
    # Whether this server and user can open the tab at all: a remembered
    # tab that fails this falls back to Documents.
    available: Callable = _always
    # Whether the nav lists it; defaults to ``available``. A tab can stay
    # reachable while unlisted: saved case law is listed only while AI is
    # off and is a view inside the AI tab otherwise.
    listed: Callable | None = None
    # Other ``subapp`` values that light this tab in the nav.
    also_active: tuple = ()
    # The wrapper div's id and the HTMX trigger that refreshes it; default
    # to the tab's name and ``<name>Changed from:body``.
    wrapper_id: str | None = None
    refresh_trigger: str | None = None

    def is_available(self, user, matter_id):
        return bool(self.available(user, matter_id))

    def is_listed(self, user, matter_id):
        return bool((self.listed or self.available)(user, matter_id))

    @property
    def element_id(self):
        return self.wrapper_id or self.name

    @property
    def trigger(self):
        return self.refresh_trigger or f"{self.name}Changed from:body"


_TABS: dict[str, Tab] = {}


def register(tab):
    _TABS[tab.name] = tab
    return tab


def get(name):
    return _TABS.get(name)


def ordered():
    return sorted(_TABS.values(), key=lambda tab: tab.order)


def listed_for(user, matter_id):
    return [tab for tab in ordered() if tab.is_listed(user, matter_id)]

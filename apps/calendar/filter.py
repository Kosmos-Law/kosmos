import django_filters
from django import forms
from django.db.models import Q

from apps.accounts.models import CustomUser
from apps.calendar.access import events_for_user, matters_for_events
from apps.calendar.models import Event

PARTY_CHOICES = (
    ("All", "All"),
    ("Client", "Client"),
    ("Opposing", "Opposing"),
    ("Other", "Other"),
)

STATUS_CHOICES = (
    ("Pending", "Pending"),
    ("Complete", "Complete"),
    ("Missed", "Missed"),
)


FIRM = "unassigned"


def assignee_tokens(value):
    """The saved Assigned-to choices as a list: the session holds one
    choice as a string and several as a list, and an emptied one as ""."""
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [token for token in value if token]


class AssigneesFilter(django_filters.MultipleChoiceFilter):
    """The assignees to show, any number ticked: FIRM for the events on
    nobody in particular (the firm's), and users by id. An event shows
    when it is the firm's and Firm is ticked, or any of its assignees is.
    Nothing ticked shows everything."""

    def filter(self, qs, value):
        tokens = assignee_tokens(value)
        if not tokens:
            return qs
        wanted = Q()
        if FIRM in tokens:
            wanted |= Q(assignees=None)
        ids = []
        for token in tokens:
            try:
                ids.append(int(token))
            except (ValueError, TypeError):
                continue
        if ids:
            wanted |= Q(assignees__in=ids)
        if not wanted:
            return qs
        return qs.filter(wanted).distinct()


class MatterFilter(django_filters.ChoiceFilter):
    """Matter choice with the special 'unassigned' option."""

    def filter(self, qs, value):
        if not value:
            return qs
        if value == "unassigned":
            return qs.filter(matter__isnull=True)
        try:
            matter_id = int(value)
            return qs.filter(matter_id=matter_id)
        except (ValueError, TypeError):
            return qs


def _saved_matter_id(data):
    """The matter id held in filter data, or None when it holds none."""
    try:
        return int((data or {}).get("matter") or "")
    except (ValueError, TypeError):
        return None


class EventFilter(django_filters.FilterSet):
    """The calendar's filter, always for one user.

    The user is required: the events filtered are only the ones that user
    may see, and the Matter and "Assigned to" choices are built for them. A
    saved value that is not among the choices (a matter the user cannot see,
    a user since deactivated) is ignored rather than applied.
    """

    status = django_filters.ChoiceFilter(
        field_name="status",
        choices=STATUS_CHOICES,
        empty_label="All",
    )
    matter = MatterFilter(empty_label="All Matters")
    date = django_filters.DateFromToRangeFilter(
        widget=django_filters.widgets.RangeWidget(attrs={"type": "date"}),
        label="Date",
    )
    party = django_filters.ChoiceFilter(
        field_name="party", choices=PARTY_CHOICES, empty_label="All Parties"
    )
    assigned_to = AssigneesFilter(
        label="Assigned to", widget=forms.CheckboxSelectMultiple
    )
    order_by = django_filters.OrderingFilter(
        fields=(
            ("date", "date"),
            ("matter__name", "matter__name"),
            ("description", "description"),
            ("party", "party"),
            ("status", "status"),
        ),
        empty_label=None,
    )

    class Meta:
        model = Event
        fields = ["date", "matter", "party", "status", "assigned_to"]

    def __init__(self, data=None, *, user, **kwargs):
        kwargs.setdefault("queryset", Event.objects.all())
        kwargs["queryset"] = events_for_user(kwargs["queryset"], user)
        # The saved filter holds one ticked assignee as a string and several
        # as a list; the field takes a list
        if data and "assigned_to" in data:
            data = dict(data)
            data["assigned_to"] = assignee_tokens(data["assigned_to"])
        super().__init__(data, **kwargs)

        # The matter already chosen stays in the list when it has since left
        # Pending/Open, so the filter in force is always one that is shown.
        self.matters = matters_for_events(user, include_id=_saved_matter_id(data))
        self.users = CustomUser.objects.filter(is_active=True).order_by(
            "first_name", "last_name"
        )
        self.matter_choices = [("unassigned", "Unassigned")] + [
            (str(matter.id), matter.name) for matter in self.matters
        ]
        self.assigned_choices = [(FIRM, "Firm")] + [
            (str(u.id), u.get_short_name() or u.username) for u in self.users
        ]
        self.filters["matter"].extra["choices"] = self.matter_choices
        self.filters["assigned_to"].extra["choices"] = self.assigned_choices

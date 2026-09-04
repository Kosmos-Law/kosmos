import django_filters
from django import forms
from django.db.models import Q

from apps.case.models import Fact, Label
from config.helpers import MultipleOrderingFilter

LABELS_MODE_ANY = "any"
LABELS_MODE_ALL = "all"
LABELS_MODE_CHOICES = (
    (LABELS_MODE_ANY, "Any of these labels"),
    (LABELS_MODE_ALL, "All of these labels"),
)


def coerce_label_ids(value):
    """Normalize a stored labels value to a list of id strings."""
    if value in (None, ""):
        return []
    if isinstance(value, (str, int)):
        return [str(value)]
    return [str(item) for item in value if item not in (None, "")]


def normalize_facts_filter_data(data):
    """Return filter data with labels as a list, absorbing the legacy key.

    Session data is a plain dict: the retired single-label filter stored
    ``label``, and a plain string under ``labels`` would fail the multiple
    choice field's list check. QueryDicts (request.GET) already carry
    lists, so they pass through untouched.
    """
    if hasattr(data, "getlist"):
        return data
    data = dict(data)
    legacy = data.pop("label", None)
    labels = coerce_label_ids(data.get("labels"))
    if not labels:
        labels = coerce_label_ids(legacy)
    data["labels"] = labels
    return data


IMPORTANCE_CHOICES = (
    (7, "Highest"),
    (6, "Higher"),
    (5, "High"),
    (4, "Normal"),
    (3, "Low"),
    (2, "Lower"),
    (1, "Lowest"),
)


class FactsFilter(django_filters.FilterSet):
    date_start = django_filters.DateFilter(
        field_name="date",
        lookup_expr="gte",
        label="Start Date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_end = django_filters.DateFilter(
        field_name="date",
        lookup_expr="lte",
        label="End Date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    keyword = django_filters.CharFilter(method="filter_keyword", label="Keyword")
    labels = django_filters.ModelMultipleChoiceFilter(
        method="filter_labels",
        queryset=Label.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Labels",
    )
    labels_mode = django_filters.ChoiceFilter(
        method="filter_labels_mode",
        choices=LABELS_MODE_CHOICES,
        empty_label=None,
        label="Match",
    )
    importance = django_filters.ChoiceFilter(
        field_name="importance",
        choices=IMPORTANCE_CHOICES,
        lookup_expr="gte",
        label="Importance (≥)",
        empty_label="All",
    )
    order_by = MultipleOrderingFilter(
        fields=[
            (("date", "time"), "date"),
            ("description", "description"),
            ("importance", "importance"),
        ],
        field_labels={
            "date": "Date and Time",
            "description": "Description",
            "importance": "Importance",
        },
        label="Order By",
    )

    class Meta:
        model = Fact
        fields = [
            "date_start",
            "date_end",
            "keyword",
            "labels",
            "labels_mode",
            "importance",
            "order_by",
        ]

    def __init__(self, data=None, *args, matter=None, **kwargs):
        if data is not None:
            data = normalize_facts_filter_data(data)
        super().__init__(data, *args, **kwargs)
        if matter:
            self.filters["labels"].queryset = Label.objects.filter(
                Q(matter=matter) | Q(matter__isnull=True)
            ).order_by("name")

    def filter_keyword(self, queryset, name, value):
        if value:
            return queryset.filter(Q(description__icontains=value))
        return queryset

    def filter_labels(self, queryset, name, value):
        """Filter facts by label: any of the chosen labels, or all of them."""
        if not value:
            return queryset
        mode = self.form.cleaned_data.get("labels_mode") or LABELS_MODE_ANY
        if mode == LABELS_MODE_ALL:
            for label in value:
                queryset = queryset.filter(labels=label)
            return queryset
        return queryset.filter(labels__in=value).distinct()

    def filter_labels_mode(self, queryset, name, value):
        """No-op: the mode is consumed by filter_labels."""
        return queryset

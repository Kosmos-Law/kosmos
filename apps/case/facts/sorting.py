"""The sort keys a case list accepts.

A list's sort is kept in the session and reaches the query, so a key is
taken only if it names one of the list's own columns (optionally reversed
with a leading "-"). The same check is made when the stored key is read:
a session can already hold a key from before the check existed, or one
posted through the filter dialog.
"""


def sort_keys(fields):
    """Each field name and its reverse."""
    return frozenset(key for field in fields for key in (field, f"-{field}"))


def filterset_sort_keys(filterset_class):
    """The keys a FilterSet's own order_by filter accepts."""
    return sort_keys(filterset_class.base_filters["order_by"].param_map)


def stored_sort_key(filter_data, valid_keys, default):
    """The list's stored sort key, or the default when none is stored or
    the stored one is not a key the list accepts."""
    value = filter_data.get("order_by")
    if isinstance(value, list):
        value = value[0] if value else None
    return value if value in valid_keys else default


def with_valid_sort(filter_data, valid_keys):
    """A copy of the stored filter without a sort key the list rejects, so
    the rest of the filter still applies."""
    cleaned = dict(filter_data)
    if stored_sort_key(cleaned, valid_keys, None) is None:
        cleaned.pop("order_by", None)
    return cleaned

"""The importance scale shared by facts, witnesses, highlights and saved
cases: 1 (Lowest) to 7 (Highest), 4 (Normal) by default."""

IMPORTANCE_CHOICES = (
    (7, "Highest"),
    (6, "Higher"),
    (5, "High"),
    (4, "Normal"),
    (3, "Low"),
    (2, "Lower"),
    (1, "Lowest"),
)
IMPORTANCE_VALUES = frozenset(value for value, _ in IMPORTANCE_CHOICES)
DEFAULT_IMPORTANCE = 4


def parse_importance(raw):
    """The importance as an int when it is on the scale, else None."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value in IMPORTANCE_VALUES else None

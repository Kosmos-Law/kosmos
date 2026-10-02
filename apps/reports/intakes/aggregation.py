"""Intakes report context — shared by the index/list views.

Builds per-month practice-area and status tables plus three chart payloads (a
month-over-month volume bar, a practice-area donut, and an outcomes/conversion
donut) over a rolling 6-month window. The window's end month is held in the
session ("intakes_end") and stepped by the intakes_period view, mirroring the
Revenue / Realization reports.
"""

from collections import defaultdict

from dateutil.relativedelta import relativedelta
from django.db.models import Count
from django.db.models.functions import TruncMonth

from apps.intakes.models import Intake
from apps.matters.models import PracticeArea
from apps.reports.activity.aggregation import _window_months, resolve_end

# An intake with no practice area is counted under this heading.
UNSPECIFIED = "Unspecified"

# The statuses the intake form offers, in the order the table shows them. A
# status outside this list (set some other way) gets a column after them.
INTAKE_STATUSES = [
    "Open",
    "Pending",
    "Accepted",
    "Referred Out",
    "Client Declined",
    "Unresponsive",
]
# The status that represents a converted intake (signed client / accepted work).
CONVERTED_STATUS = "Accepted"


def _percentages(counts, total):
    if not total:
        return {}
    return {key: round(count / total * 100, 1) for key, count in counts.items()}


def _monthly_table(months, columns, counts, key):
    """One row a month with a count and a share for each column, and the
    column totals. ``counts`` maps ((year, month), column) to a number."""
    rows = []
    totals = defaultdict(int)
    for m in months:
        month = (m["year"], m["month"])
        cells = {column: counts.get((month, column), 0) for column in columns}
        total = sum(cells.values())
        for column, count in cells.items():
            totals[column] += count
        rows.append(
            {
                "month": m["date"].strftime("%B %Y"),
                key: cells,
                "total": total,
                "percentages": _percentages(cells, total),
            }
        )
    return rows, totals


def build_intakes_context(request):
    end, current_first = resolve_end(request.session.get("intakes_end"))
    months = _window_months(end)
    window_start = months[0]["date"]
    window_end = months[-1]["date"] + relativedelta(months=1)
    intakes = Intake.objects.filter(date__gte=window_start, date__lt=window_end)

    # One pass over the window: how many intakes each month, by practice
    # area and by status.
    by_area = defaultdict(int)
    by_status = defaultdict(int)
    for row in (
        intakes.annotate(m=TruncMonth("date"))
        .values("m", "practice_area__name", "status")
        .annotate(c=Count("id"))
    ):
        month = (row["m"].year, row["m"].month)
        by_area[(month, row["practice_area__name"] or UNSPECIFIED)] += row["c"]
        by_status[(month, row["status"] or UNSPECIFIED)] += row["c"]

    # The columns are the firm's own practice areas (Settings, Practice
    # Areas), plus any other area an intake in the window carries, so that
    # every intake is in the table and the totals are the real totals.
    used_areas = {area for (_month, area) in by_area}
    practice_areas = sorted(
        set(PracticeArea.objects.filter(is_active=True).values_list("name", flat=True))
        | (used_areas - {UNSPECIFIED})
    )
    if UNSPECIFIED in used_areas:
        practice_areas.append(UNSPECIFIED)
    used_statuses = {status for (_month, status) in by_status}
    statuses = INTAKE_STATUSES + sorted(used_statuses - set(INTAKE_STATUSES))

    intake_data, totals_by_practice_area = _monthly_table(
        months, practice_areas, by_area, "practice_areas"
    )
    status_data, totals_by_status = _monthly_table(
        months, statuses, by_status, "statuses"
    )
    total_intakes = sum(row["total"] for row in intake_data)
    percentages_by_practice_area = _percentages(totals_by_practice_area, total_intakes)
    percentages_by_status = _percentages(totals_by_status, total_intakes)

    # --- Month-over-month volume bar (0 for empty months) ---
    counts_by_month = {
        (r["m"].year, r["m"].month): r["c"]
        for r in intakes.exclude(date=None)
        .annotate(m=TruncMonth("date"))
        .values("m")
        .annotate(c=Count("id"))
    }
    flow_counts = [counts_by_month.get((m["year"], m["month"]), 0) for m in months]
    flow_chart = {
        "months": [m["name"] for m in months],
        "series": {"flow": [{"label": "Intakes", "count": flow_counts}]},
        "top_labels": [str(c) for c in flow_counts],
    }

    # --- Practice-area distribution donut (no area -> trailing grey "Unspecified") ---
    pa_rows = list(intakes.values("practice_area__name").annotate(c=Count("id")))
    named = sorted(
        (r for r in pa_rows if r["practice_area__name"]), key=lambda r: -r["c"]
    )
    unspecified = sum(r["c"] for r in pa_rows if not r["practice_area__name"])
    pa_labels = [r["practice_area__name"] for r in named]
    pa_counts = [r["c"] for r in named]
    if unspecified:
        pa_labels.append("Unspecified")
        pa_counts.append(unspecified)
    practice_donut = {
        "labels": pa_labels,
        "count": pa_counts,
        "hasOther": bool(unspecified),
    }

    # --- Outcomes / conversion donut ---
    st_counts = {
        r["status"]: r["c"] for r in intakes.values("status").annotate(c=Count("id"))
    }
    conv_labels = [s for s in INTAKE_STATUSES if st_counts.get(s)]
    conv_labels += [s for s in st_counts if s not in INTAKE_STATUSES and st_counts[s]]
    conversion_donut = {
        "labels": conv_labels,
        "count": [st_counts[s] for s in conv_labels],
    }
    total_all = sum(st_counts.values())
    converted_count = st_counts.get(CONVERTED_STATUS, 0)
    conversion_rate = round(converted_count / total_all * 100, 1) if total_all else 0

    return {
        "app": "reports",
        "subapp": "intakes",
        "intake_data": intake_data,
        "status_data": status_data,
        "total_intakes": total_intakes,
        "totals_by_practice_area": dict(totals_by_practice_area),
        "totals_by_status": dict(totals_by_status),
        "percentages_by_practice_area": percentages_by_practice_area,
        "percentages_by_status": percentages_by_status,
        "practice_areas": practice_areas,
        "intake_statuses": statuses,
        "flow_chart": flow_chart,
        "practice_donut": practice_donut,
        "conversion_donut": conversion_donut,
        "conversion_rate": conversion_rate,
        "converted_count": converted_count,
        "intakes_total_all": total_all,
        "period_label": end.strftime("%b %Y"),
        "can_go_next": end < current_first,
    }

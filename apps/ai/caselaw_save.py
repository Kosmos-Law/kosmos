"""Saving a researched authority to the matter's case law library.

The session's ``save_caselaw`` tool (session_tools.py) lands here: a
case the agent read on CourtListener persists as a ``CaseLaw`` row with
the proposition it was cited for in its notes, instead of living only
in the transcript. The row is built from the cluster, so a citation-less
slip opinion saves too; an authority already in the library gets the
proposition appended to its notes rather than a duplicate row
((matter, cluster_id) is unique).
"""

from datetime import date as date_cls

from apps.case.models import CaseLaw


def save_authority(matter, cluster_id, proposition, court, user):
    """Save one authority; None when the cluster cannot be fetched."""
    from apps.case.courtlistener import fetch_cluster, format_citations_with_year
    from apps.case.services import generate_caselaw_summary

    proposition = str(proposition or "").strip()[:500]
    existing = CaseLaw.objects.filter(matter=matter, cluster_id=cluster_id).first()
    if existing is not None:
        if proposition and proposition not in (existing.notes or ""):
            existing.notes = (
                f"{existing.notes}\n{proposition}" if existing.notes else proposition
            )
            existing.save(update_fields=["notes"])
        return existing

    cluster = fetch_cluster(cluster_id)
    if not cluster:
        return None

    date_filed = None
    if cluster.get("date_filed"):
        try:
            date_filed = date_cls.fromisoformat(cluster["date_filed"])
        except ValueError:
            date_filed = None

    # The cluster's "court" field is an API URL; keep the id from its tail.
    # The display name is not in the cluster, so the tool call may carry
    # it from the search hit; the id stands in when it does not.
    court_id = str(cluster.get("court") or "").rstrip("/").split("/")[-1]
    court_name = str(court or "").strip()[:255] or court_id

    opinion_id = None
    sub_opinions = cluster.get("sub_opinions", [])
    if sub_opinions:
        try:
            opinion_id = int(sub_opinions[0].rstrip("/").split("/")[-1])
        except (ValueError, IndexError):
            opinion_id = None

    case_law = CaseLaw.objects.create(
        matter=matter,
        case_name=cluster.get("case_name") or f"Cluster {cluster_id}",
        citation=format_citations_with_year(cluster.get("citations", []), None),
        court=court_name,
        court_id=court_id,
        date_filed=date_filed,
        docket_number=str(cluster.get("docket_number") or ""),
        cluster_id=cluster_id,
        opinion_id=opinion_id,
        courtlistener_url=(
            f"https://www.courtlistener.com{cluster['absolute_url']}"
            if cluster.get("absolute_url")
            else ""
        ),
        notes=proposition,
        created_by=user,
        updated_by=user,
    )
    generate_caselaw_summary(case_law.id)
    return case_law

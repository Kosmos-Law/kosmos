"""Background work for a matter's saved case law."""

import logging

from apps.case.ai.gemini_client import send_to_gemini
from apps.case.courtlistener import fetch_cluster, fetch_opinion

logger = logging.getLogger(__name__)


def generate_caselaw_summary(caselaw_id):
    """Queue the 200-word AI summary for a CaseLaw entry."""
    from django_q.tasks import async_task

    async_task(
        "apps.case.caselaws.tasks._generate_caselaw_summary",
        caselaw_id,
        task_name=f"CaseLawSummary-{caselaw_id}",
        group="caselaw",
    )


def _generate_caselaw_summary(caselaw_id):
    """Fetch opinion text and generate a 200-word summary."""
    from apps.case.models import CaseLaw

    try:
        caselaw = CaseLaw.objects.get(pk=caselaw_id)
    except CaseLaw.DoesNotExist:
        return

    try:
        opinion_text = ""
        if caselaw.opinion_id:
            opinion = fetch_opinion(caselaw.opinion_id)
            if opinion.found:
                opinion_text = opinion.plain_text
        elif caselaw.cluster_id:
            opinion_text = _get_opinion_text(caselaw.cluster_id)

        if not opinion_text:
            return

        truncated = opinion_text[:15000]

        system_prompt = (
            "You are a legal research assistant. Write clear, concise prose."
        )
        user_prompt = (
            f"Write a 200-word summary of this case. Focus on the key facts, "
            f"the legal issue, and the court's holding.\n\n"
            f"Case: {caselaw.case_name}\n"
            f"Citation: {caselaw.citation}\n"
            f"Court: {caselaw.court}\n"
            f"Date: {caselaw.date_filed}\n\n"
            f"Opinion Text:\n{truncated}"
        )

        response_text, _, _ = send_to_gemini(
            system_prompt, [{"role": "user", "content": user_prompt}]
        )

        CaseLaw.objects.filter(pk=caselaw_id).update(summary=response_text.strip())

    except Exception:
        logger.exception("Error generating summary for case law %s", caselaw_id)


def _get_opinion_text(cluster_id):
    """Fetch opinion plain text from CourtListener given a cluster_id."""
    cluster = fetch_cluster(cluster_id)
    if not cluster:
        return ""

    sub_opinions = cluster.get("sub_opinions", [])
    if not sub_opinions:
        return ""

    try:
        opinion_id = int(sub_opinions[0].rstrip("/").split("/")[-1])
    except (ValueError, IndexError):
        return ""

    opinion = fetch_opinion(opinion_id)
    return opinion.plain_text if opinion.found else ""

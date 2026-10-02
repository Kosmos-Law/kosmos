from tempfile import NamedTemporaryFile

from django.http.response import Http404
from django.template.loader import render_to_string
from weasyprint import HTML

from apps.case.models import Fact
from apps.matters.models import Matter
from apps.matters.proceedings.models import Proceeding


def generate_facts_pdf(matter_id, request, facts=None, filter_summary=None):
    """
    Generate a facts PDF for the given matter.

    ``facts`` is the list to print (the Facts tab passes what is on screen:
    its filter and its order); every fact of the matter when omitted.
    ``filter_summary`` is the wording of the filter in force, one string
    per condition, printed under the heading so a partial timeline says
    that it is one.
    """
    try:
        matter = Matter.objects.get(pk=matter_id)
    except Matter.DoesNotExist:
        raise Http404("Matter does not exist")

    proceeding = Proceeding.objects.filter(matter=matter.id).order_by("-id").first()
    all_facts = Fact.objects.filter(matter=matter.id)
    if facts is None:
        # The screen's default order (date, then time).
        facts = all_facts.order_by("date", "time")
    facts = facts.prefetch_related(
        "highlights__document", "highlights__caselaw", "documents"
    )

    context = {
        "matter": matter,
        "proceeding": proceeding,
        "facts": facts,
        "filter_summary": filter_summary or [],
        "total_count": all_facts.count(),
    }

    html_string = render_to_string("case/facts/pdf.html", context)
    html = HTML(string=html_string, base_url=request.build_absolute_uri())

    with NamedTemporaryFile(suffix=".pdf", delete=False) as pdf_file:
        html.write_pdf(target=pdf_file.name)
        pdf_file.seek(0)

    return pdf_file

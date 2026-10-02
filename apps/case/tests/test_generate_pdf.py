from unittest.mock import MagicMock, patch

import pytest
from django.http import Http404

from apps.case.facts.generate_pdf import generate_facts_pdf

pytestmark = pytest.mark.django_db


class TestGenerateFactsPdf:
    def test_nonexistent_matter_raises_404(self):
        """Generating PDF for non-existent matter should raise Http404."""
        mock_request = MagicMock()
        with pytest.raises(Http404):
            generate_facts_pdf(99999, mock_request)

    @patch("apps.case.facts.generate_pdf.HTML")
    @patch("apps.case.facts.generate_pdf.render_to_string")
    def test_generates_pdf(self, mock_render, mock_html, matter, fact, client):
        """PDF should be generated for valid matter."""
        mock_render.return_value = "<html>Test PDF</html>"
        mock_html_instance = MagicMock()
        mock_html.return_value = mock_html_instance

        # Create a mock request
        mock_request = MagicMock()
        mock_request.build_absolute_uri.return_value = "http://testserver/"

        result = generate_facts_pdf(matter.id, mock_request)

        mock_render.assert_called_once()
        mock_html.assert_called_once()
        mock_html_instance.write_pdf.assert_called_once()
        assert result is not None

    @patch("apps.case.facts.generate_pdf.HTML")
    @patch("apps.case.facts.generate_pdf.render_to_string")
    def test_includes_matter_in_context(self, mock_render, mock_html, matter, client):
        """Context should include matter."""
        mock_render.return_value = "<html></html>"
        mock_html.return_value = MagicMock()

        mock_request = MagicMock()
        mock_request.build_absolute_uri.return_value = "http://testserver/"

        generate_facts_pdf(matter.id, mock_request)

        call_args = mock_render.call_args
        context = call_args[0][1]
        assert context["matter"] == matter

    @patch("apps.case.facts.generate_pdf.HTML")
    @patch("apps.case.facts.generate_pdf.render_to_string")
    def test_includes_facts_in_context(
        self, mock_render, mock_html, matter, fact, client
    ):
        """Context should include facts for the matter."""
        mock_render.return_value = "<html></html>"
        mock_html.return_value = MagicMock()

        mock_request = MagicMock()
        mock_request.build_absolute_uri.return_value = "http://testserver/"

        generate_facts_pdf(matter.id, mock_request)

        call_args = mock_render.call_args
        context = call_args[0][1]
        assert fact in context["facts"]

    @patch("apps.case.facts.generate_pdf.HTML")
    @patch("apps.case.facts.generate_pdf.render_to_string")
    def test_includes_proceeding_in_context(
        self, mock_render, mock_html, matter, proceeding, client
    ):
        """Context should include proceeding for the matter."""
        mock_render.return_value = "<html></html>"
        mock_html.return_value = MagicMock()

        mock_request = MagicMock()
        mock_request.build_absolute_uri.return_value = "http://testserver/"

        generate_facts_pdf(matter.id, mock_request)

        call_args = mock_render.call_args
        context = call_args[0][1]
        assert context["proceeding"] == proceeding

    @patch("apps.case.facts.generate_pdf.HTML")
    @patch("apps.case.facts.generate_pdf.render_to_string")
    def test_uses_correct_template(self, mock_render, mock_html, matter, client):
        """Should render the correct template."""
        mock_render.return_value = "<html></html>"
        mock_html.return_value = MagicMock()

        mock_request = MagicMock()
        mock_request.build_absolute_uri.return_value = "http://testserver/"

        generate_facts_pdf(matter.id, mock_request)

        call_args = mock_render.call_args
        template_name = call_args[0][0]
        assert template_name == "case/facts/pdf.html"


class TestTimelinePdfContent:
    """What the PDF prints, with only the PDF engine stubbed out."""

    def _html(self, matter):
        mock_request = MagicMock()
        mock_request.build_absolute_uri.return_value = "http://testserver/"
        with patch("apps.case.facts.generate_pdf.HTML") as mock_html:
            mock_html.return_value = MagicMock()
            generate_facts_pdf(matter.id, mock_request)
        return mock_html.call_args.kwargs["string"]

    def test_prints_each_facts_sources(self, matter, fact, document, highlight):
        fact.documents.add(document)
        fact.highlights.add(highlight)

        html = self._html(matter)

        assert document.citation in html
        assert highlight.citation in html

    def test_a_fact_without_sources_prints_none(self, matter, fact):
        html = self._html(matter)

        assert fact.description in html
        assert "(" not in html.split(fact.description)[1].split("</td>")[0]

    def test_orders_by_date_then_time_as_the_screen_does(self, matter, user):
        from apps.case.models import Fact

        for description, time in (("Afternoon", "15:00"), ("Morning", "09:00")):
            Fact.objects.create(
                user=user,
                matter=matter,
                date="2024-03-01",
                time=time,
                description=description,
            )
        Fact.objects.create(
            user=user, matter=matter, date="2024-02-01", description="Earlier day"
        )

        html = self._html(matter)

        positions = [
            html.index(text) for text in ("Earlier day", "Morning", "Afternoon")
        ]
        assert positions == sorted(positions)


class TestTimelinePdfFollowsTheFilter:
    """Download PDF sits on the filtered Facts list, so it prints that
    list and says so. With no filter it prints every fact, unmarked."""

    @pytest.fixture
    def facts(self, matter, user):
        from apps.case.models import Fact

        return [
            Fact.objects.create(
                user=user,
                matter=matter,
                date=day,
                description=description,
                importance=importance,
            )
            for day, description, importance in (
                ("2024-01-10", "Contract signed", 6),
                ("2024-02-10", "Contract breached", 4),
                ("2024-03-10", "Demand letter sent", 2),
            )
        ]

    def _pdf_html(self, client, matter, **filter_data):
        session = client.session
        session[f"facts_filter_{matter.id}"] = filter_data
        session.save()
        with patch("apps.case.facts.generate_pdf.HTML") as mock_html:
            mock_html.return_value = MagicMock()
            response = client.get(f"/case/{matter.id}/facts/pdf/")
        assert response.status_code == 200
        return mock_html.call_args.kwargs["string"]

    def test_no_filter_prints_everything_with_a_plain_heading(
        self, client, matter, facts
    ):
        html = self._pdf_html(client, matter)

        for fact in facts:
            assert fact.description in html
        assert "(filtered)" not in html
        assert "Showing" not in html

    def test_a_keyword_filter_limits_the_facts_and_is_named(
        self, client, matter, facts
    ):
        html = self._pdf_html(client, matter, keyword="contract")

        assert "Contract signed" in html and "Contract breached" in html
        assert "Demand letter sent" not in html
        assert "(filtered)" in html
        assert "Showing 2 of 3 facts." in html
        assert "keyword &quot;contract&quot;" in html

    def test_dates_importance_and_labels_are_named(self, client, matter, facts, label):
        facts[0].labels.add(label)

        html = self._pdf_html(
            client,
            matter,
            date_start="2024-01-01",
            date_end="2024-02-28",
            importance="5",
            labels=[str(label.id)],
        )

        assert "Contract signed" in html
        assert "Contract breached" not in html
        assert "Showing 1 of 3 facts." in html
        assert (
            "Filter: from 2024-01-01; to 2024-02-28; label Important; "
            "importance High or higher." in html
        )

    def test_the_screens_sort_is_followed_and_is_not_a_filter(
        self, client, matter, facts
    ):
        html = self._pdf_html(client, matter, order_by="-date")

        positions = [html.index(fact.description) for fact in facts]
        assert positions == sorted(positions, reverse=True)
        assert "(filtered)" not in html

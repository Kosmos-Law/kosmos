"""Tests for the matter-scope JSON API, whose service functions the MCP
server's tools share: auth, section reads, full-content reads, and the
create-only fact/witness/task writes."""

import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts.models import ApiToken, CustomUser
from apps.activity.expenses.models import ExpenseEntry
from apps.activity.flat_fees.models import FlatFeeEntry
from apps.activity.models import ActivityCategory
from apps.activity.time.models import TimeEntry
from apps.ai.models import Conversation, Message
from apps.calendar.models import Event
from apps.case.models import Fact, Witness
from apps.invoicing.invoices.models import Invoice
from apps.invoicing.payments.models import Payment
from apps.mail.models import Email
from apps.matters.models import Matter
from apps.matters.rates.models import Rate
from apps.matters.settlement.models import SettlementEntry
from apps.tasks.models import Task
from apps.trust.models import Transaction

pytestmark = pytest.mark.django_db


@pytest.fixture
def api(user):
    return Client(HTTP_X_KOSMOS_TOKEN=ApiToken.for_user(user).key)


@pytest.fixture
def restricted_api():
    """Token client for a non-admin user with no matter memberships."""
    outsider = CustomUser.objects.create(
        username="case-outsider",
        email="case-outsider@example.com",
        user_rate=100,
        perm_all_matters=False,
    )
    return Client(HTTP_X_KOSMOS_TOKEN=ApiToken.for_user(outsider).key)


def section_url(matter, section):
    return f"/case/api/matter/{matter.id}/{section}/"


def post_json(api, url, payload):
    return api.post(url, json.dumps(payload), content_type="application/json")


def section_text(api, matter, section):
    response = api.get(section_url(matter, section))
    assert response.status_code == 200
    return response.json()["text"]


class TestAccess:
    def test_missing_token_is_401(self, matter):
        response = Client().get(section_url(matter, "overview"))
        assert response.status_code == 401

    def test_denied_matter_is_404(self, restricted_api, matter):
        response = restricted_api.get(section_url(matter, "overview"))
        assert response.status_code == 404

    def test_closed_matter_is_404(self, api, matter):
        matter.status = "Closed"
        matter.save()
        response = api.get(section_url(matter, "overview"))
        assert response.status_code == 404

    def test_unknown_section_is_400_listing_sections(self, api, matter):
        response = api.get(section_url(matter, "bogus"))
        assert response.status_code == 400
        assert "overview" in response.json()["error"]


class TestSections:
    def test_overview(self, api, matter):
        text = section_text(api, matter, "overview")
        assert "Test Matter" in text
        assert "Test Client" in text

    def test_rates_with_matter_and_firm_rows(self, api, matter, user):
        Rate.objects.create(user=user, matter=matter, matter_rate=250)
        Rate.objects.create(user=user, matter=None, matter_rate=100)
        text = section_text(api, matter, "rates")
        assert "$250/hr" in text
        assert "Firm default rates:" in text
        assert "$100/hr" in text

    def test_activity_with_categories_and_totals(self, api, matter, user):
        category = ActivityCategory.objects.create(matter=matter, name="Drafting")
        TimeEntry.objects.create(
            matter=matter,
            user=user,
            date="2026-01-05",
            actions="Draft complaint",
            hours=2,
            rate=200,
            category=category,
        )
        ExpenseEntry.objects.create(
            matter=matter,
            user=user,
            date="2026-01-06",
            category="Filing fee",
            description="Clerk of court",
            amount=100,
        )
        FlatFeeEntry.objects.create(
            matter=matter,
            user=user,
            date="2026-01-07",
            description="Initial consult",
            amount=500,
        )
        text = section_text(api, matter, "activity")
        assert "[Drafting] Draft complaint" in text
        assert "$400.00" in text  # 2h @ $200
        assert "Filing fee: Clerk of court ($100.00)" in text
        assert "Initial consult ($500.00)" in text

    def test_events(self, api, matter, user):
        Event.objects.create(
            user=user,
            matter=matter,
            date=(timezone.now() + timedelta(days=7)).date(),
            description="Status hearing",
        )
        assert "Status hearing" in section_text(api, matter, "events")

    def test_tasks(self, api, matter, user):
        Task.objects.create(
            user=user, matter=matter, description="call the expert", status="Pending"
        )
        assert "Call the expert" in section_text(api, matter, "tasks")

    def test_settlement(self, api, matter, user):
        SettlementEntry.objects.create(
            user=user, matter=matter, date="2026-02-01", type="Demand", amount=50000
        )
        text = section_text(api, matter, "settlement")
        assert "Demand: $50,000.00" in text

    def test_documents_manifest_without_ocr_text(self, api, matter, document):
        document.ocr_text = "SECRET EXTRACTED TEXT"
        document.save(update_fields=["ocr_text"])
        text = section_text(api, matter, "documents")
        assert f"[doc:{document.id}] Test Document" in text
        assert "SECRET EXTRACTED TEXT" not in text

    def test_highlights_manifest(self, api, matter, highlight):
        text = section_text(api, matter, "highlights")
        assert f"[hl:{highlight.id}]" in text
        assert "highlighted text" in text

    def test_timeline(self, api, matter, fact):
        text = section_text(api, matter, "timeline")
        assert "Important event occurred" in text

    def test_witnesses(self, api, matter, user):
        Witness.objects.create(
            matter=matter, user=user, name="Jordan Reeves", alignment="friendly"
        )
        assert "Jordan Reeves" in section_text(api, matter, "witnesses")

    def test_emails_thread_manifest(self, api, matter):
        for i, gmail_id in enumerate(["m1", "m2"]):
            Email.objects.create(
                matter=matter,
                gmail_id=gmail_id,
                thread_id="t100",
                sender="Opposing Counsel <oc@example.com>",
                recipients="james@example.com",
                subject="Discovery schedule",
                snippet="Proposed dates attached",
                body_text=f"Message body {i}",
                date=timezone.now() - timedelta(days=2 - i),
            )
        text = section_text(api, matter, "emails")
        assert "[thread t100] Discovery schedule (2 messages" in text

    def test_emails_manifest_lists_latest_activity_first(self, api, matter):
        # An old thread with a recent reply outranks a newer, quiet thread.
        for gmail_id, thread_id, subject, days_ago in [
            ("a1", "old", "Old thread", 300),
            ("b1", "mid", "Middle thread", 100),
            ("a2", "old", "Old thread", 1),
        ]:
            Email.objects.create(
                matter=matter,
                gmail_id=gmail_id,
                thread_id=thread_id,
                subject=subject,
                date=timezone.now() - timedelta(days=days_ago),
            )
        text = section_text(api, matter, "emails")
        assert text.index("[thread old]") < text.index("[thread mid]")


class TestFullReads:
    def test_document_text(self, api, document):
        document.ocr_text = "Full extracted document text."
        document.save(update_fields=["ocr_text"])
        response = api.get(f"/case/api/documents/{document.id}/")
        assert response.status_code == 200
        assert response.json()["text"] == "Full extracted document text."

    def test_document_denied_is_404(self, restricted_api, document):
        response = restricted_api.get(f"/case/api/documents/{document.id}/")
        assert response.status_code == 404

    def test_email_thread(self, api, matter):
        Email.objects.create(
            matter=matter,
            gmail_id="m1",
            thread_id="t200",
            sender="oc@example.com",
            recipients="james@example.com",
            subject="Depo dates",
            body_text="How about Tuesday?",
            date=timezone.now(),
        )
        response = api.get(f"/case/api/matter/{matter.id}/emails/t200/")
        assert response.status_code == 200
        body = response.json()
        assert body["subject"] == "Depo dates"
        assert "How about Tuesday?" in body["text"]

    def test_unknown_thread_is_404(self, api, matter):
        response = api.get(f"/case/api/matter/{matter.id}/emails/nope/")
        assert response.status_code == 404


class TestFactCreate:
    def test_create_links_in_matter_sources_only(self, api, matter, highlight):
        response = post_json(
            api,
            section_url(matter, "facts"),
            {
                "description": "Contract signed by both parties",
                "date": "2024-03-01",
                "highlights": [highlight.id],
                "documents": [999999],
            },
        )
        assert response.status_code == 201
        fact = Fact.objects.get(pk=response.json()["id"])
        assert fact.matter_id == matter.id
        assert list(fact.highlights.values_list("id", flat=True)) == [highlight.id]
        assert fact.documents.count() == 0
        assert response.json()["message"].startswith("- Added to timeline:")

    def test_short_description_is_400(self, api, matter):
        response = post_json(api, section_url(matter, "facts"), {"description": "ab"})
        assert response.status_code == 400

    def test_denied_matter_is_404(self, restricted_api, matter):
        response = post_json(
            restricted_api, section_url(matter, "facts"), {"description": "whatever"}
        )
        assert response.status_code == 404

    def test_get_serves_timeline_section(self, api, matter, fact):
        response = api.get(section_url(matter, "facts"))
        assert response.status_code == 200
        assert "Important event occurred" in response.json()["text"]


class TestWitnessCreate:
    def test_create_and_dedup(self, api, matter):
        url = section_url(matter, "witnesses")
        response = post_json(
            api, url, {"name": "Dana Whitfield", "alignment": "hostile"}
        )
        assert response.status_code == 201
        assert response.json()["created"] is True

        response = post_json(api, url, {"name": "dana whitfield"})
        assert response.status_code == 200
        assert response.json()["created"] is False
        assert Witness.objects.filter(matter=matter).count() == 1

    def test_missing_name_is_400(self, api, matter):
        response = post_json(api, section_url(matter, "witnesses"), {"name": "x"})
        assert response.status_code == 400


class TestTaskCreate:
    def test_admin_task_without_matter(self, api, user):
        response = post_json(api, "/case/api/tasks/", {"description": "file cabinet"})
        assert response.status_code == 201
        assert response.json()["matter"] == "Admin"
        task = Task.objects.get(pk=response.json()["id"])
        assert task.matter is None
        assert task.user_id == user.id

    def test_matter_task(self, api, matter):
        response = post_json(
            api,
            "/case/api/tasks/",
            {
                "description": "serve the subpoena",
                "matter_id": matter.id,
                "due": "2026-09-01",
            },
        )
        assert response.status_code == 201
        task = Task.objects.get(pk=response.json()["id"])
        assert task.matter_id == matter.id
        assert str(task.date_due) == "2026-09-01"

    def test_denied_matter_is_404(self, restricted_api, matter):
        response = post_json(
            restricted_api,
            "/case/api/tasks/",
            {"description": "should not exist", "matter_id": matter.id},
        )
        assert response.status_code == 404
        assert not Task.objects.filter(description__icontains="should not").exists()

    def test_duplicate_matter_name_resolves_to_requested_id(self, api, matter, user):
        twin = Matter.objects.create(
            user=user, name=matter.name, status="Open", date_start="2024-02-01"
        )
        response = post_json(
            api,
            "/case/api/tasks/",
            {"description": "task for the twin", "matter_id": twin.id},
        )
        assert response.status_code == 201
        task = Task.objects.get(pk=response.json()["id"])
        assert task.matter_id == twin.id


@pytest.fixture
def conversation(matter, user):
    conv = Conversation.objects.create(
        matter=matter, user=user, title="Damages theory", kind="agent"
    )
    Message.objects.create(
        conversation=conv, role="user", user=user, content="What are our damages?"
    )
    Message.objects.create(
        conversation=conv, role="assistant", content="Lost profits plus costs."
    )
    return conv


class TestConversations:
    def test_manifest_lists_handles_and_omits_never(self, api, matter, conversation):
        Conversation.objects.create(
            matter=matter, title="Private musings", ai_context="never"
        )
        text = section_text(api, matter, "conversations")
        assert f"[conv:{conversation.id}] Damages theory" in text
        assert "Agentic" in text
        assert "2 messages" in text
        assert "Private musings" not in text

    def test_transcript(self, api, matter, conversation):
        url = f"/case/api/matter/{matter.id}/conversations/{conversation.id}/"
        response = api.get(url)
        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "Damages theory"
        assert "What are our damages?" in body["text"]
        assert "**Assistant:** Lost profits plus costs." in body["text"]

    def test_never_conversation_is_404(self, api, matter):
        conv = Conversation.objects.create(matter=matter, ai_context="never")
        response = api.get(f"/case/api/matter/{matter.id}/conversations/{conv.id}/")
        assert response.status_code == 404

    def test_denied_matter_is_404(self, restricted_api, matter, conversation):
        url = f"/case/api/matter/{matter.id}/conversations/{conversation.id}/"
        assert restricted_api.get(url).status_code == 404


@pytest.fixture
def sent_invoice(matter, user):
    invoice = Invoice.objects.create(
        matter=matter, status="SENT", date_limit="2026-01-31", date_issued="2026-02-01"
    )
    TimeEntry.objects.create(
        matter=matter,
        user=user,
        date="2026-01-05",
        actions="Draft complaint",
        hours=2,
        rate=200,
        invoice=invoice,
    )
    ExpenseEntry.objects.create(
        matter=matter,
        user=user,
        date="2026-01-06",
        category="Filing fee",
        description="Clerk of court",
        amount=100,
        invoice=invoice,
    )
    return invoice


@pytest.fixture
def no_financial_api(user):
    user.perm_financial = False
    user.save()
    return Client(HTTP_X_KOSMOS_TOKEN=ApiToken.for_user(user).key)


class TestMoney:
    def test_ledger(self, api, matter, sent_invoice):
        Payment.objects.create(
            matter=matter, date="2026-02-10", amount=300, payment_method="CHECK"
        )
        Invoice.objects.create(
            matter=matter,
            status="DRAFT",
            date_limit="2025-12-31",
            date_issued="2026-03-01",
        )
        text = section_text(api, matter, "ledger")
        assert (
            f"[inv:{sent_invoice.id}] Invoice {sent_invoice.id} $500.00 (Sent)" in text
        )
        assert "Credit: Payment by Check $300.00 | balance $200.00" in text
        assert "Balance due: $200.00" in text
        assert "Payments received: $300.00" in text
        assert "Invoices not yet sent" in text

    def test_trust(self, api, matter):
        Transaction.objects.create(
            contact=matter.client,
            date="2026-01-02",
            type="Deposit",
            method="Check",
            description="Retainer",
            amount=1000,
            confirmed=True,
        )
        Transaction.objects.create(
            contact=matter.client,
            date="2026-01-20",
            type="Withdrawal",
            description="Invoice 1",
            amount=250,
        )
        text = section_text(api, matter, "trust")
        assert "for Test Client" in text
        assert "Trust balance: $750.00 (confirmed $1,000.00)" in text
        assert "- [2026-01-02] Deposit $1,000.00 by Check: Retainer" in text
        assert "- [2026-01-20] Withdrawal $250.00: Invoice 1 [unconfirmed]" in text

    def test_invoice_read(self, api, sent_invoice):
        response = api.get(f"/case/api/invoices/{sent_invoice.id}/")
        assert response.status_code == 200
        text = response.json()["text"]
        assert f"Invoice #{sent_invoice.id}" in text
        assert "Draft complaint — 2.0h @ $200/hr ($400.00)" in text
        assert "Filing fee: Clerk of court ($100.00)" in text

    def test_invoice_denied_is_404(self, restricted_api, sent_invoice):
        response = restricted_api.get(f"/case/api/invoices/{sent_invoice.id}/")
        assert response.status_code == 404

    @pytest.mark.parametrize("section", ["rates", "ledger", "trust"])
    def test_money_sections_need_financial_perm(
        self, no_financial_api, matter, section
    ):
        response = no_financial_api.get(section_url(matter, section))
        assert response.status_code == 403

    def test_invoice_needs_financial_perm(self, no_financial_api, sent_invoice):
        response = no_financial_api.get(f"/case/api/invoices/{sent_invoice.id}/")
        assert response.status_code == 403


class TestMaterialSearch:
    @pytest.fixture(autouse=True)
    def _no_semantic_pass(self, monkeypatch):
        monkeypatch.setattr("apps.ai.agent_tools.semantic_entries", lambda *a, **k: [])

    def test_hits(self, api, matter, document):
        from watson import search as watson

        document.ocr_text = "Alpha " * 50 + "spoliation letter " + "omega " * 50
        document.ocr_status = "completed"
        document.save(update_fields=["ocr_text", "ocr_status"])
        watson.default_search_engine.update_obj_index(document)
        response = post_json(
            api, f"/case/api/matter/{matter.id}/search/", {"query": "spoliation"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["queries"] == ["spoliation"]
        assert "budget" not in body
        hit = next(h for h in body["hits"] if h["kind"] == "document")
        assert hit["handle"] == f"doc:{document.id}"
        assert "spoliation" in hit["snippet"]

    def test_empty_query_is_400(self, api, matter):
        response = post_json(api, f"/case/api/matter/{matter.id}/search/", {})
        assert response.status_code == 400

    def test_denied_matter_is_404(self, restricted_api, matter):
        response = post_json(
            restricted_api, f"/case/api/matter/{matter.id}/search/", {"query": "x"}
        )
        assert response.status_code == 404


def firm_group(name):
    """A firm-wide party group by name. The migrations seed the firm's
    groups, but a flushed test database may have lost them, and a leaked
    row may have doubled them: take what is there, else make it."""
    from apps.matters.models import Group

    group = Group.objects.filter(name=name, matter__isnull=True).first()
    return group or Group.objects.create(name=name, order=2)


def firm_role(name):
    from apps.matters.models import Role

    return Role.objects.filter(name=name).first() or Role.objects.create(name=name)


class TestContactsSection:
    def test_lists_handles_groups_and_roles(self, api, matter, contact):
        from apps.matters.models import Relationship

        group, role = firm_group("Adversary"), firm_role("Counsel")
        Relationship.objects.create(
            matter=matter, contact=contact, group=group, role=role
        )
        text = section_text(api, matter, "contacts")
        assert f"[contact:{contact.id}] Test Client (Counsel, Adversary)" in text
        assert "- Test Company [client@example.com]" in text
        groups, roles = text.split("Groups add_contact may use on this matter: ")[
            1
        ].split(". Roles: ")
        assert "Adversary" in groups and "Client" not in groups
        assert "Counsel" in roles and "Client" not in roles


class TestTasksSection:
    def test_lists_handles_and_status(self, api, matter, user):
        task = Task.objects.create(
            user=user, matter=matter, description="call the expert", status="Pending"
        )
        text = section_text(api, matter, "tasks")
        assert f"[task:{task.id}] [Pending] P4: Call the expert" in text
        assert "Use complete_task" in text


class TestTimeEntryCreate:
    def time_url(self, matter):
        return f"/case/api/matter/{matter.id}/time/"

    def test_creates_at_the_matter_rate(self, api, matter, user):
        Rate.objects.create(user=user, matter=matter, matter_rate=250)
        ActivityCategory.objects.create(matter=matter, name="Discovery")
        response = post_json(
            api,
            self.time_url(matter),
            {
                "actions": "Review deposition transcript",
                "hours": 0.25,
                "date": "2026-10-01",
                "category": "discovery",
            },
        )
        assert response.status_code == 201, response.content
        entry = TimeEntry.objects.get(pk=response.json()["id"])
        assert entry.user == user and entry.matter == matter
        assert entry.rate == 250
        assert str(entry.hours) == "0.3"
        assert str(entry.date) == "2026-10-01"
        assert entry.category.name == "Discovery"
        assert entry.invoice is None and not entry.comp and not entry.entered
        assert entry.needs_approval is True
        assert "$250/hr, $75.00; needs approval" in response.json()["message"]

    def test_firm_rate_and_today_by_default(self, api, matter, user):
        response = post_json(
            api, self.time_url(matter), {"actions": "Call with client", "hours": 1}
        )
        assert response.status_code == 201
        entry = TimeEntry.objects.get(pk=response.json()["id"])
        assert entry.rate == user.user_rate == 100
        assert entry.date == timezone.localdate()

    def test_unknown_category_lists_the_matters(self, api, matter):
        ActivityCategory.objects.create(matter=matter, name="Pleadings")
        response = post_json(
            api,
            self.time_url(matter),
            {"actions": "Draft answer", "hours": 1, "category": "Motions"},
        )
        assert response.status_code == 400
        assert "Pleadings" in response.json()["error"]
        assert not TimeEntry.objects.exists()

    @pytest.mark.parametrize("hours", [0, -1, 100, "abc", True, None])
    def test_bad_hours_is_400(self, api, matter, hours):
        response = post_json(
            api, self.time_url(matter), {"actions": "Research", "hours": hours}
        )
        assert response.status_code == 400
        assert "hours" in response.json()["error"]

    def test_flat_fee_matter_is_400(self, api, matter):
        matter.billing_type = "FLAT_FEE"
        matter.save()
        response = post_json(
            api, self.time_url(matter), {"actions": "Research", "hours": 1}
        )
        assert response.status_code == 400
        assert "hourly" in response.json()["error"]

    def test_denied_matter_is_404(self, restricted_api, matter):
        response = post_json(
            restricted_api, self.time_url(matter), {"actions": "Research", "hours": 1}
        )
        assert response.status_code == 404
        assert not TimeEntry.objects.exists()


class TestEventCreate:
    def test_matter_event_with_default_end(self, api, matter, user):
        response = post_json(
            api,
            "/case/api/events/",
            {
                "matter_id": matter.id,
                "description": "Status hearing",
                "date": "2026-11-12",
                "start_time": "09:30",
                "party": "Judge Ortiz",
                "location": "Courtroom 4B",
                "event_type": "In-person",
            },
        )
        assert response.status_code == 201, response.content
        event = Event.objects.get(pk=response.json()["id"])
        assert event.matter == matter and event.user == user
        assert event.status == "Pending"
        assert str(event.start_time) == "09:30:00"
        assert str(event.end_time) == "10:30:00"
        assert event.end_date is None
        assert event.assignees.count() == 0
        message = response.json()["message"]
        assert "Status hearing" in message and "09:30-10:30" in message
        assert "[Test Matter]" in message

    def test_firm_event_assigned_to_me(self, api, user):
        response = post_json(
            api,
            "/case/api/events/",
            {
                "description": "Bar association lunch",
                "date": "2026-11-12",
                "assigned_to_me": True,
            },
        )
        assert response.status_code == 201
        event = Event.objects.get(pk=response.json()["id"])
        assert event.matter is None
        assert list(event.assignees.all()) == [user]
        assert response.json()["matter"] == "Firm"

    def test_multi_day_drops_same_day_end(self, api, matter):
        response = post_json(
            api,
            "/case/api/events/",
            {
                "matter_id": matter.id,
                "description": "Trial",
                "date": "2026-11-12",
                "end_date": "2026-11-12",
            },
        )
        assert response.status_code == 201
        assert Event.objects.get(pk=response.json()["id"]).end_date is None

    @pytest.mark.parametrize(
        "bad, needle",
        [
            ({"end_date": "2026-11-11"}, "end_date"),
            ({"start_time": "10:00", "end_time": "09:00"}, "end_time"),
            ({"date": "next tuesday"}, "date"),
            ({"event_type": "Carrier pigeon"}, "event_type"),
            ({"description": "x"}, "description"),
        ],
    )
    def test_bad_values_are_400(self, api, matter, bad, needle):
        payload = {
            "matter_id": matter.id,
            "description": "Hearing",
            "date": "2026-11-12",
        }
        payload.update(bad)
        response = post_json(api, "/case/api/events/", payload)
        assert response.status_code == 400
        assert needle in response.json()["error"]
        assert not Event.objects.exists()

    def test_denied_matter_is_404(self, restricted_api, matter):
        response = post_json(
            restricted_api,
            "/case/api/events/",
            {"matter_id": matter.id, "description": "Hearing", "date": "2026-11-12"},
        )
        assert response.status_code == 404
        assert not Event.objects.exists()


class TestTaskComplete:
    def complete_url(self, task):
        return f"/case/api/tasks/{task.id}/complete/"

    def test_completes_and_stamps_the_date(self, api, matter, user):
        task = Task.objects.create(
            user=user, matter=matter, description="serve the subpoena", status="Pending"
        )
        response = api.post(self.complete_url(task))
        assert response.status_code == 200, response.content
        assert response.json()["changed"] is True
        task.refresh_from_db()
        assert task.status == "Complete"
        assert task.date_completed == timezone.localdate()

    def test_already_complete_is_reported(self, api, user):
        task = Task.objects.create(user=user, description="done", status="Complete")
        response = api.post(self.complete_url(task))
        assert response.status_code == 200
        assert response.json()["changed"] is False
        assert "Already complete" in response.json()["message"]
        assert response.json()["matter"] == "Admin"

    def test_unfinished_checklist_blocks(self, api, user):
        from apps.checklists.models import Checklist, ChecklistItem

        task = Task.objects.create(user=user, description="onboard", status="Pending")
        checklist = Checklist.objects.create(task=task, name="Onboarding")
        ChecklistItem.objects.create(
            checklist=checklist, description="sign engagement letter", item_type="item"
        )
        response = api.post(self.complete_url(task))
        assert response.status_code == 400
        task.refresh_from_db()
        assert task.status == "Pending"

    def test_denied_matter_is_404(self, restricted_api, matter, user):
        task = Task.objects.create(
            user=user, matter=matter, description="private", status="Pending"
        )
        assert restricted_api.post(self.complete_url(task)).status_code == 404
        task.refresh_from_db()
        assert task.status == "Pending"

    def test_unknown_task_is_404(self, api):
        assert api.post("/case/api/tasks/999999/complete/").status_code == 404


class TestContactCreate:
    @pytest.fixture
    def parties(self):
        return firm_group("Adversary"), firm_role("Counsel")

    def test_creates_normalized(self, api, user):
        from apps.contacts.models import Contact

        response = post_json(
            api,
            "/case/api/contacts/",
            {
                "name": "Dana Whitfield",
                "company": "Whitfield & Co.",
                "email": "Dana@Whitfield.Example",
                "phone": "(404) 555-0133",
                "notes": "Opposing counsel",
            },
        )
        assert response.status_code == 201, response.content
        contact = Contact.objects.get(pk=response.json()["id"])
        assert contact.user == user
        assert contact.email == "dana@whitfield.example"
        assert contact.phone1 and "555" in contact.phone1 and "(" not in contact.phone1
        assert contact.company == "Whitfield & Co."

    def test_dedups_by_name(self, api, contact):
        response = post_json(
            api, "/case/api/contacts/", {"name": "test client", "email": "x@y.example"}
        )
        assert response.status_code == 200
        assert response.json()["created"] is False
        assert response.json()["id"] == contact.id
        contact.refresh_from_db()
        assert contact.email == "client@example.com"

    def test_links_to_matter(self, api, matter, parties):
        from apps.matters.models import Relationship

        group, role = parties
        response = post_json(
            api,
            "/case/api/contacts/",
            {
                "name": "Dana Whitfield",
                "matter_id": matter.id,
                "role": "counsel",
                "group": "adversary",
            },
        )
        assert response.status_code == 201, response.content
        rel = Relationship.objects.get(matter=matter, contact_id=response.json()["id"])
        assert rel.role.name == "Counsel" and rel.group == group
        assert (
            "assigned to Test Matter as Counsel in Adversary"
            in (response.json()["message"])
        )
        again = post_json(
            api,
            "/case/api/contacts/",
            {
                "name": "Dana Whitfield",
                "matter_id": matter.id,
                "role": "Counsel",
                "group": "Adversary",
            },
        )
        assert again.status_code == 200
        assert "already on Test Matter" in again.json()["message"]
        assert Relationship.objects.filter(matter=matter, group=group).count() == 1

    def test_bad_role_lists_roles_and_creates_nothing(self, api, matter, parties):
        from apps.contacts.models import Contact

        response = post_json(
            api,
            "/case/api/contacts/",
            {"name": "Dana Whitfield", "matter_id": matter.id, "role": "Wizard"},
        )
        assert response.status_code == 400
        assert "Counsel" in response.json()["error"]
        assert not Contact.objects.filter(name="Dana Whitfield").exists()

    def test_bad_group_lists_groups(self, api, matter, parties):
        response = post_json(
            api,
            "/case/api/contacts/",
            {
                "name": "Dana Whitfield",
                "matter_id": matter.id,
                "role": "Counsel",
                "group": "Client",
            },
        )
        assert response.status_code == 400
        assert "Adversary" in response.json()["error"]

    @pytest.mark.parametrize(
        "bad, needle",
        [
            ({"email": "not-an-address"}, "email"),
            ({"phone": "123"}, "phone"),
            ({"name": "D"}, "name"),
            ({"name": "D" * 51}, "name"),
        ],
    )
    def test_bad_values_are_400(self, api, bad, needle):
        payload = {"name": "Dana Whitfield"}
        payload.update(bad)
        response = post_json(api, "/case/api/contacts/", payload)
        assert response.status_code == 400
        assert needle in response.json()["error"]

    def test_denied_matter_is_404(self, restricted_api, matter, parties):
        from apps.contacts.models import Contact

        response = post_json(
            restricted_api,
            "/case/api/contacts/",
            {
                "name": "Dana Whitfield",
                "matter_id": matter.id,
                "role": "Counsel",
                "group": "Adversary",
            },
        )
        assert response.status_code == 404
        assert not Contact.objects.filter(name="Dana Whitfield").exists()

from django.db import models
from simple_history.models import HistoricalRecords

from apps.accounts.models import CustomUser
from apps.case.models import AI_CONTEXT_CHOICES
from apps.matters.models import Matter
from utils.models import AuditMixin


class Conversation(AuditMixin, models.Model):
    """A chat conversation within a matter context."""

    # The picker offers one entry per model family at its current version.
    # Superseded versions are retired from the picker (see RETIRED_LLMS in
    # views.py: "claude" is Sonnet 4.6, "claude-opus-5" / "claude-opus" /
    # "claude-opus-4-6" are Opus 5 / 4.8 / 4.6, "claude-fable" is Fable 5,
    # "gemini-pro" is Gemini 2.5 Pro) but stay wired through the dispatch,
    # selector and pricing tables so conversations started on them keep working and keep their
    # original pricing. Anthropic publishes no "latest" alias, so a new
    # version is a new key here plus rows in those tables (and a
    # migration for the choices). Fable (double Opus pricing) is available
    # in both Classic and Agentic mode.
    LLM_CHOICES = [
        ("claude-fable-5-1", "Claude Fable 5.1"),
        ("claude-opus-5-5", "Claude Opus 5.5"),
        ("claude-sonnet-5", "Claude Sonnet 5"),
        ("gemini-pro-latest", "Gemini Pro (Latest)"),
        ("gemini-flash", "Gemini 2.5 Flash"),
    ]

    # Chat modes, fixed when the conversation is created. "classic" is the
    # original single-completion chat over a preloaded matter context;
    # "agent" runs a tool loop that reads matter materials on demand and
    # narrates each step (apps/ai/agent.py). "research" was the
    # retired CourtListener research loop; it is not creatable any more
    # but its conversations still render.
    KIND_CHOICES = [
        ("classic", "Classic"),
        ("research", "Research"),
        ("agent", "Agentic"),
    ]

    # A conversation belongs to exactly one of: a matter (case chat) or an
    # intake (intake chat). Intake conversations are ephemeral: at most one
    # live per intake, deleted on end/discard.
    matter = models.ForeignKey(
        Matter,
        on_delete=models.CASCADE,
        related_name="ai_conversations",
        null=True,
        blank=True,
    )
    intake = models.ForeignKey(
        "intakes.Intake",
        on_delete=models.CASCADE,
        related_name="ai_conversations",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_conversations",
    )
    title = models.CharField(max_length=255, blank=True, default="")
    llm = models.CharField(
        max_length=20, choices=LLM_CHOICES, default="gemini-pro-latest"
    )
    ai_context = models.CharField(
        max_length=6,
        choices=AI_CONTEXT_CHOICES,
        default="auto",
        help_text="AI context inclusion: auto (selector decides), always, or never",
    )
    summary = models.TextField(
        blank=True,
        null=True,
        help_text="AI-generated summary for intelligent context selection",
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="classic")
    vet_citations = models.BooleanField(
        default=True,
        help_text=(
            "After each response, launch a Gemini Flash job per cited case to "
            "check whether the case actually supports what the AI claims."
        ),
    )
    history = HistoricalRecords(table_name="case_historicalconversation")

    class Meta:
        ordering = ["-created_at", "-id"]
        db_table = "matters_conversation"  # Keep same table name

    def save(self, *args, **kwargs):
        if self.title:
            self.title = self.title[0].upper() + self.title[1:]
        super().save(*args, **kwargs)

    def __str__(self):
        if self.matter_id:
            owner = self.matter.name
        elif self.intake_id:
            owner = self.intake.name
        else:
            owner = "Unattached"
        return f"{owner} - {self.title or 'Untitled'}"

    def get_participants(self):
        """Return distinct users who have sent messages in this conversation."""
        return CustomUser.objects.filter(ai_messages__conversation=self).distinct()


class Message(AuditMixin, models.Model):
    """Individual message in a conversation."""

    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()

    # Track which user sent this message (null for assistant messages)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_messages",
    )

    # Track token usage for monitoring
    input_tokens = models.IntegerField(null=True, blank=True)
    output_tokens = models.IntegerField(null=True, blank=True)

    # Verified citations for assistant messages
    verified_citations = models.JSONField(default=list, blank=True)

    # Research-kind assistant messages: the research trail (plan, searches,
    # opinions read, treatment checks) rendered as a collapsible section.
    research_trail = models.JSONField(default=list, blank=True)

    # Assistant messages: the live activity log preserved (context
    # assembly, material selection, model call, cite check) so past turns
    # stay inspectable. Rendered as a collapsible section like the trail;
    # research answers show their richer trail instead.
    activity_log = models.JSONField(default=list, blank=True)

    # Agent-kind assistant messages: the run record (typed steps, per-turn
    # token usage, elapsed time, stop reason) rendered as a collapsible
    # trail above the answer, and mined by later turns for the materials
    # already read. Shape documented in docs/dev/subsystems/ai/agent-chat.md.
    agent_run = models.JSONField(default=dict, blank=True)

    history = HistoricalRecords(table_name="case_historicalmessage")

    def cited_authorities(self):
        """Cases the answer actually cited, with their briefs.

        The grounding event's cited_clusters define the set; names,
        citations and briefs come from the abstract/read/skim/lookup
        events. Rendered under the answer (authorities belong with the
        response; the trail stays a process record)."""
        trail = self.research_trail or []
        cited = []
        for event in trail:
            if event.get("type") == "grounding":
                cited = event.get("cited_clusters") or []
        results = []
        for cluster_id in cited:
            entry = {
                "cluster_id": cluster_id,
                "case_name": "",
                "citation": "",
                "abstract": "",
            }
            for event in trail:
                if event.get("cluster_id") != cluster_id:
                    continue
                if event.get("type") in ("abstract", "read", "skim", "lookup"):
                    entry["case_name"] = entry["case_name"] or event.get(
                        "case_name", ""
                    )
                    entry["citation"] = entry["citation"] or event.get("citation", "")
                if event.get("type") == "abstract" and event.get("abstract"):
                    entry["abstract"] = event["abstract"]
            results.append(entry)
        return results

    class Meta:
        ordering = ["created_at"]
        db_table = "matters_message"  # Keep same table name

    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."


class Session(AuditMixin, models.Model):
    """A Claude Code session on a matter.

    The successor to ``Conversation``: one agentic session, run by the
    Claude Agent SDK from the matter's folder in the firm's files, on an
    Anthropic model. Kosmos is the system of record (per matter, shared by
    the firm); ``sdk_session_id`` is the harness's own id, kept so a later
    turn resumes the same transcript. Conversations stay as a read-only
    archive. Record: docs/decisions/2026-10-29-ai-chat-becomes-claude-code-sessions.md.
    """

    # Keys match apps/llm/pricing.py. Fable is for administrators only for
    # now (``model_choices_for``); the default is Opus.
    MODEL_CHOICES = [
        ("claude-fable-5-1", "Claude Fable 5.1"),
        ("claude-opus-5-5", "Claude Opus 5.5"),
        ("claude-sonnet-5", "Claude Sonnet 5"),
    ]
    ADMIN_ONLY_MODELS = {"claude-fable-5-1"}
    DEFAULT_MODEL = "claude-opus-5-5"

    matter = models.ForeignKey(
        Matter, on_delete=models.CASCADE, related_name="ai_sessions"
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_sessions",
        help_text="Who started it.",
    )
    title = models.CharField(max_length=255, blank=True, default="")
    model = models.CharField(
        max_length=40, choices=MODEL_CHOICES, default=DEFAULT_MODEL
    )
    # The harness's session id, set by the first turn; empty until then.
    sdk_session_id = models.CharField(max_length=64, blank=True, default="")
    # The matter folder the session runs in, relative to the firm's files,
    # as it was when the session started.
    folder = models.CharField(max_length=1024, blank=True, default="")
    summary = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at", "-id"]
        db_table = "ai_session"

    def __str__(self):
        return f"{self.matter.name} - {self.title or 'Untitled'}"

    @classmethod
    def model_choices_for(cls, user):
        """The models this user may pick."""
        if user.is_admin:
            return list(cls.MODEL_CHOICES)
        return [(k, v) for k, v in cls.MODEL_CHOICES if k not in cls.ADMIN_ONLY_MODELS]

    @classmethod
    def user_may_pick(cls, user, model):
        return model in dict(cls.model_choices_for(user))

    @property
    def display_title(self):
        return self.title or "New session"

    @staticmethod
    def title_from(prompt: str) -> str:
        """The first line of the first prompt, cut to a title."""
        line = prompt.strip().splitlines()[0].strip() if prompt.strip() else ""
        if len(line) > 80:
            line = line[:77].rsplit(" ", 1)[0] + "..."
        return line[0].upper() + line[1:] if line else ""

    def get_participants(self):
        return CustomUser.objects.filter(ai_session_messages__session=self).distinct()


class SessionMessage(AuditMixin, models.Model):
    """One message in a session: a user's prompt or the agent's answer.

    The agent's full transcript (every tool call and result) is the
    harness's; ``trail`` keeps the readable summary of what it did for the
    message's trail in the page, and the token counts are for the cost line.
    """

    ROLE_CHOICES = [("user", "User"), ("assistant", "Assistant")]
    # An assistant message is created with the prompt and filled by the
    # runtime: pending until the sessions service picks it up, running
    # while the turn streams, then done, failed or cancelled.
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("done", "Done"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_session_messages",
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="done")
    error = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    trail = models.JSONField(default=list, blank=True)
    input_tokens = models.IntegerField(null=True, blank=True)
    output_tokens = models.IntegerField(null=True, blank=True)
    cache_read_tokens = models.IntegerField(null=True, blank=True)
    cost_usd = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True
    )

    class Meta:
        ordering = ["created_at", "id"]
        db_table = "ai_session_message"

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"

    @property
    def is_open(self):
        return self.status in ("pending", "running")

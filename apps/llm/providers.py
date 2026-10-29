"""One call for the AI work that is not a matter session.

Summaries, intake extraction and assessment, the intake chat and
quick-add all ask for a tier ("fast" for cheap bulk work, "deep" for a
conversation) and run on whichever provider is configured, Gemini first.
Matter sessions run Claude Code through the Agent SDK (apps/ai/runtime.py).
"""

from apps.settings.ai import ANTHROPIC, GEMINI, configured_providers

FAST = "fast"
DEEP = "deep"

# Tier -> (Gemini model id, Claude model id).
MODELS = {
    FAST: ("gemini-2.5-flash", "claude-sonnet-4-6"),
    DEEP: ("gemini-pro-latest", "claude-sonnet-5"),
}

# Tier -> the Conversation.llm picker key a stored chat records.
CHAT_LLMS = {
    GEMINI: {FAST: "gemini-flash", DEEP: "gemini-pro-latest"},
    ANTHROPIC: {FAST: "claude-sonnet-5", DEEP: "claude-sonnet-5"},
}


class AINotConfigured(RuntimeError):
    """No AI provider has a key."""


def provider(prefer=None):
    """The provider to use: ``prefer`` when it is configured, else the
    first configured one. Raises AINotConfigured with none."""
    providers = configured_providers()
    if not providers:
        raise AINotConfigured("No AI provider is configured.")
    return prefer if prefer in providers else providers[0]


def chat_llm(tier=DEEP):
    """The picker key a background-created conversation should record."""
    return CHAT_LLMS[provider()][tier]


def complete(
    system_context,
    messages,
    tier=FAST,
    *,
    prefer=None,
    on_thought=None,
    is_cancelled=None,
    conversation_id=None,
):
    """Send ``messages`` and return ``(text, input_tokens, output_tokens)``."""
    chosen = provider(prefer)
    gemini_model, claude_model = MODELS[tier]
    if chosen == GEMINI:
        from .gemini_client import send_to_gemini_streaming

        return send_to_gemini_streaming(
            system_context,
            messages,
            model=gemini_model,
            on_thought=on_thought,
            is_cancelled=is_cancelled,
            conversation_id=conversation_id,
        )
    from .anthropic_client import send_to_claude

    return send_to_claude(
        system_context, messages, model=claude_model, is_cancelled=is_cancelled
    )

"""
Anthropic Claude API client for AI chat.

Uses streaming to support cancellation mid-request, and marks the system
prompt as cacheable so repeat messages in the same conversation benefit
from Anthropic's prompt-cache pricing (~10% of input cost on cache hits).
Serves ``providers.complete`` (the intake chat, summaries, extraction);
matter sessions run on the Claude Agent SDK instead (apps/ai/runtime.py).
"""

import logging
from typing import Callable

import anthropic

from apps.settings.ai import anthropic_key

logger = logging.getLogger(__name__)


# Anthropic's prompt cache has a per-model minimum prefix: 1024 tokens on
# Sonnet 4.6 and Opus 4.8, 4096 on Opus 4.6. We use a character heuristic
# (~4 chars/token) that clears the 1024 minimum and avoids marking small
# system prompts; below it we fall back to the plain string form. On Opus
# 4.6 a marked prompt under ~16k chars simply doesn't cache — the marker is
# ignored, not billed — so matter contexts that small show no cache lines in
# the log. Every real matter context clears it comfortably.
_ANTHROPIC_CACHE_MIN_CHARS = 5000

# Server-side refusal fallback. Fable runs safety classifiers that can
# decline benign-adjacent requests (an HTTP 200 with stop_reason
# "refusal", before any output or mid-stream); with `fallbacks` the API
# re-runs the same request on the fallback model inside the same call, so
# the user gets an answer instead of the refusal notice. Targets must be
# in the requested model's allowed_fallback_models: Opus 4.8 and Opus 5
# for both Fable models as of 2026-09-24 (Opus 5.5 is not yet allowed).
# The array form takes exactly this beta header. Once a conversation has
# fallen back, later turns are routed straight to the fallback model for
# about an hour ("sticky"); served_by_fallback catches those too. A
# fallback-served turn bills at the fallback model's rates; pricing.py
# still prices it at the picker rate, an overestimate.
FALLBACK_MODELS = {
    "claude-fable-5-1": "claude-opus-5",
    "claude-fable-5": "claude-opus-5",
}
_FALLBACK_BETA = "server-side-fallback-2026-06-01"


def _fallback_kwargs(model: str) -> dict:
    fallback = FALLBACK_MODELS.get(model)
    if not fallback:
        return {}
    return {"betas": [_FALLBACK_BETA], "fallbacks": [{"model": fallback}]}


def _messages_api(client, model: str):
    """The beta namespace when the request carries fallbacks (the parameter
    lives there); the stable one otherwise."""
    return client.beta.messages if model in FALLBACK_MODELS else client.messages


def served_by_fallback(final_message) -> str | None:
    """The fallback model's ID when it produced this message, else None.

    A fallback_message entry in usage.iterations is the served-by signal
    (sticky-routed turns carry no fallback content block); the top-level
    model names what answered.
    """
    usage = getattr(final_message, "usage", None)
    for entry in getattr(usage, "iterations", None) or []:
        if getattr(entry, "type", None) == "fallback_message":
            return getattr(final_message, "model", None) or "the fallback model"
    return None


def _note_fallback(on_note, model: str, served: str) -> None:
    logger.info("Claude refusal fallback: %s served for %s", served, model)
    if on_note:
        on_note(f"Served by {served} (safety fallback for {model})")


def _after_fallback(content: list) -> list:
    """The content blocks the served model actually stands behind.

    After a mid-output fallback, the declined partial's thinking and
    tool_use blocks before the final fallback marker were never acted on
    (only its text carried over as context) and must be neither executed
    nor echoed back; the marker itself is an audit block the API ignores.
    """
    boundary = -1
    for i, block in enumerate(content):
        if getattr(block, "type", "") == "fallback":
            boundary = i
    if boundary < 0:
        return list(content)
    dead = ("thinking", "redacted_thinking", "tool_use")
    kept = [b for b in content[:boundary] if getattr(b, "type", "") not in dead]
    return kept + list(content[boundary + 1 :])


def _build_system(system_context):
    """Return the `system=` argument for messages.stream.

    For large prompts, returns a content block list with an ephemeral
    cache_control marker so Anthropic caches the prefix for ~5 minutes and
    subsequent identical prefixes pay ~10% of the input rate. For smaller
    prompts, returns the plain string (no caching — the cache-write premium
    isn't justified below the minimum cacheable length).

    A list of segments (the agent turn's stable orientation followed by
    its per-turn tail) becomes one text block per segment, each marked
    when it is large enough, so the stable prefix keeps hitting the cache
    while the tail changes.
    """
    if isinstance(system_context, (list, tuple)):
        blocks = []
        for segment in system_context:
            if not segment:
                continue
            block = {"type": "text", "text": segment}
            if len(segment) >= _ANTHROPIC_CACHE_MIN_CHARS:
                block["cache_control"] = {"type": "ephemeral"}
            blocks.append(block)
        return blocks
    if system_context and len(system_context) >= _ANTHROPIC_CACHE_MIN_CHARS:
        return [
            {
                "type": "text",
                "text": system_context,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    return system_context


def _roll_message_cache_marker(convo: list[dict]) -> None:
    """Move the rolling cache breakpoint to the conversation's last block.

    The tool loop resends the whole conversation — including every
    accumulated tool result — on every model turn, and without a breakpoint
    in the messages Anthropic bills all of it at full input price each time
    (the system-prompt marker only covers the prefix up to the system
    block). Marking the newest block caches everything before it, so the
    next turn reads the prior turns at ~10% of the input rate and pays full
    price only for what was just appended.

    One marker rolls forward each turn (older ones are stripped so the
    4-breakpoint request limit is never hit); the cache lookup still finds
    the previous turn's entry by walking back from the new marker. Plain
    string content (the initial chat history) is left unmarked — the system
    marker already covers the prefix on the first turn.
    """
    for msg in convo:
        if isinstance(msg["content"], list):
            for block in msg["content"]:
                if isinstance(block, dict):
                    block.pop("cache_control", None)
    last_content = convo[-1]["content"]
    if isinstance(last_content, list) and last_content:
        last_block = last_content[-1]
        if isinstance(last_block, dict):
            last_block["cache_control"] = {"type": "ephemeral"}


def _format_messages(messages: list[dict]) -> list[dict]:
    """Reduce chat-history dicts to the role/content shape the API takes."""
    return [{"role": msg["role"], "content": msg["content"]} for msg in messages]


_MAX_TOKENS_RETRY_NUDGE = (
    "Your last turn hit the output limit before you wrote any answer "
    "(it was likely all spent on reasoning). Think less and answer "
    "directly and concisely."
)


def send_to_claude(
    system_context: str,
    messages: list[dict],
    model: str = "claude-sonnet-4-6",
    is_cancelled: Callable[[], bool] | None = None,
    max_tokens: int = 4096,
    on_note: Callable[[str], None] | None = None,
) -> tuple[str, int, int]:
    """
    Send a conversation to Claude and get a response using streaming.

    Uses streaming mode to allow cancellation mid-request. When cancelled,
    only tokens generated up to that point are billed.

    Sonnet 4.6, Opus 4.6 and Opus 4.8 all expose a 1M-token context window on
    this account without any beta header and at standard input pricing. The
    selector's MODEL_CONTEXT_LIMITS is a soft cap on auto-selected content;
    the assembler enforces a separate hard ceiling so the total prompt stays
    under the model window even when always-included content (highlights,
    facts, notes, reference convos) inflates the fixed portion.

    On some models (Fable) thinking is mandatory and always-on and can run
    deep enough to consume the whole turn before any visible text is
    written — stop_reason "max_tokens" with an empty response. When that
    happens the request is retried once with a nudge to think less and
    answer directly, rather than silently returning nothing (see
    send_to_claude_with_tools, which has the same retry for the agent
    loop).

    Args:
        system_context: The system prompt with matter context
        messages: List of {"role": "user"|"assistant", "content": str}
        model: Claude model to use — see CLAUDE_MODELS in tasks.py
        is_cancelled: Optional callback that returns True if request should be cancelled
        max_tokens: Output token ceiling for the turn — see CLASSIC_MAX_OUTPUT_TOKENS
            in tasks.py; models with mandatory thinking need more headroom.
        on_note: Optional callback for a line worth showing in the activity
            log (currently: the turn was served by the refusal fallback).

    Returns:
        tuple of (response_text, input_tokens, output_tokens). input_tokens
        is the whole prompt (Anthropic reports the uncached portion alone
        in usage.input_tokens; the cached portion is added back in here —
        see the cost-accounting note below).

    Raises:
        anthropic.APIError: If the API call fails
        InterruptedError: If the request was cancelled
    """
    client = anthropic.Anthropic(api_key=anthropic_key())

    formatted_messages = _format_messages(messages)

    def _stream_once(send_messages):
        response_parts = []
        with _messages_api(client, model).stream(
            model=model,
            max_tokens=max_tokens,
            system=_build_system(system_context),
            messages=send_messages,
            **_fallback_kwargs(model),
        ) as stream:
            for text in stream.text_stream:
                # Check for cancellation on each chunk
                if is_cancelled and is_cancelled():
                    raise InterruptedError("Request cancelled")
                response_parts.append(text)
            final_message = stream.get_final_message()

        served = served_by_fallback(final_message)
        if served:
            _note_fallback(on_note, model, served)

        usage = final_message.usage
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        if cache_write or cache_read:
            logger.info(
                "Claude prompt cache: created=%d read=%d uncached=%d model=%s",
                cache_write,
                cache_read,
                usage.input_tokens or 0,
                model,
            )
        # usage.input_tokens is the uncached portion alone; Message has no
        # column for the cache split (unlike agent_run.usage, which keeps
        # it), so fold the cached portion back in here. pricing.message_cost
        # then prices classic messages as fully uncached at the full input
        # rate — a deliberate overestimate (see its docstring) — but only
        # if this total is the true prompt size; returning the uncached
        # count alone silently dropped the (often much larger) cached
        # portion from the estimate entirely, undercounting real cost on
        # every turn after the first in a conversation.
        total_input = (usage.input_tokens or 0) + cache_read + cache_write
        return (
            "".join(response_parts),
            final_message,
            total_input,
            usage.output_tokens or 0,
        )

    response_text, final_message, input_tokens, output_tokens = _stream_once(
        formatted_messages
    )

    if final_message.stop_reason == "max_tokens" and not response_text.strip():
        logger.warning(
            "Claude classic turn hit max_tokens with no text (model=%s); retrying",
            model,
        )
        # The failed attempt still billed its (thinking-only) tokens; fold
        # them into the totals returned to the caller so cost reporting
        # isn't undercounted by a silently discarded call.
        retry_text, final_message, retry_input, retry_output = _stream_once(
            formatted_messages + [{"role": "user", "content": _MAX_TOKENS_RETRY_NUDGE}]
        )
        response_text = retry_text
        input_tokens += retry_input
        output_tokens += retry_output

    return response_text, input_tokens, output_tokens

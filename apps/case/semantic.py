"""
Semantic index over matter materials: documents, highlights and timeline
facts (registered by the case app) and emails (registered by apps.mail).

Text is chunked (~6k chars, paragraph-aware, overlapping), embedded
(embeddings.py) and stored as MaterialChunk rows with a pgvector column;
search_materials fuses cosine-nearest chunks with the keyword hits so
the agent finds meaning as well as words. Saves enqueue re-indexing on
qcluster (skipped when the content hash is unchanged); deletes clean up
inline. `manage.py build_semantic_index` backfills.
"""

import hashlib
import logging
from dataclasses import dataclass
from typing import Callable

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.db.models.signals import post_delete, post_save

from apps.llm.embeddings import embed_queries, embed_texts
from apps.settings.ai import gemini_key

logger = logging.getLogger(__name__)

CHUNK_CHARS = 6000
CHUNK_OVERLAP = 600
MAX_CHUNKS_PER_OBJECT = 200
# Cosine similarity floor: chunks below it are noise, not neighbors.
SIM_FLOOR = 0.30


def chunk_text(text):
    """Split ``text`` into overlapping ~CHUNK_CHARS pieces, preferring
    paragraph and word boundaries."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= CHUNK_CHARS:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_CHARS
        if end < len(text):
            floor = start + CHUNK_CHARS // 2
            cut = text.rfind("\n\n", floor, end)
            if cut == -1:
                cut = text.rfind("\n", floor, end)
            if cut == -1:
                cut = text.rfind(" ", floor, end)
            if cut != -1:
                end = cut
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks[:MAX_CHUNKS_PER_OBJECT]


# ---------------------------------------------------------------------------
# Kinds
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SemanticKind:
    """One kind of material in the index. The case app registers its own
    kinds (apps/case/registrations.py); an app whose rows the index should
    cover registers a kind of its own at start-up (apps.mail does for
    emails), so this module never imports the apps above it."""

    kind: str
    model: type
    source: Callable  # obj -> (matter_id, text); empty text means do not index
    signals: bool = True  # index on save, drop chunks on delete
    backfill: Callable | None = None  # matter -> queryset, for the backfill


_KINDS: dict[str, SemanticKind] = {}


def register_kind(kind, model, source, **options):
    entry = SemanticKind(kind, model, source, **options)
    _KINDS[kind] = entry
    if entry.signals:
        _connect(entry)
    return entry


def kinds():
    return list(_KINDS.values())


def kind_names():
    return tuple(_KINDS)


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------


def index_object(kind, obj):
    """(Re)index one object; returns the number of chunks written.

    Skips the embedding call when the content hash is unchanged.
    """
    from apps.case.models import MaterialChunk

    entry = _KINDS[kind]
    stale = MaterialChunk.objects.filter(kind=kind, object_id=obj.pk)

    matter_id, text = entry.source(obj)
    text = (text or "").strip()
    if not text:
        stale.delete()
        return 0

    content_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
    if (
        stale.filter(content_hash=content_hash).exists()
        and not stale.exclude(content_hash=content_hash).exists()
    ):
        return 0

    chunks = chunk_text(text)
    vectors = embed_texts(chunks)
    with transaction.atomic():
        stale.delete()
        MaterialChunk.objects.bulk_create(
            [
                MaterialChunk(
                    matter_id=matter_id,
                    kind=kind,
                    object_id=obj.pk,
                    chunk_index=i,
                    text=chunk,
                    content_hash=content_hash,
                    embedding=vector,
                )
                for i, (chunk, vector) in enumerate(zip(chunks, vectors))
            ]
        )
    return len(chunks)


def index_object_task(kind, pk):
    """qcluster entry point for save-time re-indexing."""
    obj = _KINDS[kind].model.objects.filter(pk=pk).first()
    if obj is None:
        return
    try:
        index_object(kind, obj)
    except Exception:
        logger.exception("Semantic indexing failed for %s %s", kind, pk)


# ---------------------------------------------------------------------------
# Save/delete hooks
# ---------------------------------------------------------------------------


def _enqueue(kind, pk):
    if not getattr(settings, "SEMANTIC_AUTO_INDEX", True) or not gemini_key():
        return
    try:
        from django_q.tasks import async_task

        async_task("apps.case.semantic.index_object_task", kind, pk, group="semantic")
    except Exception:
        # Broker down: the backfill command is the catch-up path.
        logger.exception("Could not enqueue semantic indexing for %s %s", kind, pk)


def _drop_chunks(kind, pk):
    from apps.case.models import MaterialChunk

    MaterialChunk.objects.filter(kind=kind, object_id=pk).delete()


def _connect(entry):
    """Wire one kind's save/delete hooks; the save hook enqueues, the delete
    hook cleans up inline."""
    kind = entry.kind

    def _saved(sender, instance, **kwargs):
        _enqueue(kind, instance.pk)

    def _deleted(sender, instance, **kwargs):
        try:
            _drop_chunks(kind, instance.pk)
        except Exception:
            logger.exception("Semantic chunk cleanup failed")

    post_save.connect(
        _saved, sender=entry.model, weak=False, dispatch_uid=f"semantic-save-{kind}"
    )
    post_delete.connect(
        _deleted, sender=entry.model, weak=False, dispatch_uid=f"semantic-del-{kind}"
    )


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def semantic_entries(queries, matter, kinds, limit):
    """Per query, the nearest distinct objects: [[{kind, object_id, text,
    similarity, query}, ...], ...]. Empty lists when embedding fails, so
    keyword search degrades gracefully."""
    from pgvector.django import CosineDistance

    from apps.case.models import MaterialChunk

    kinds = [k for k in kinds if k in _KINDS]
    # Embeddings are Gemini's: without its key, search is keyword-only.
    if not kinds or not gemini_key():
        return []
    try:
        query_vectors = embed_queries(list(queries))
    except Exception:
        logger.exception("Query embedding failed; semantic pass skipped")
        return []

    if matter is None:
        return [[] for _ in queries]
    scope = Q(matter=matter, kind__in=kinds)

    results = []
    for query, vector in zip(queries, query_vectors):
        rows = (
            MaterialChunk.objects.filter(scope)
            .annotate(distance=CosineDistance("embedding", vector))
            .order_by("distance")[: limit * 3]
        )
        ranked = []
        seen_objects = set()
        for row in rows:
            similarity = 1.0 - float(row.distance)
            if similarity < SIM_FLOOR:
                break
            key = (row.kind, row.object_id)
            if key in seen_objects:
                continue
            seen_objects.add(key)
            ranked.append(
                {
                    "kind": row.kind,
                    "object_id": row.object_id,
                    "text": row.text,
                    "similarity": round(similarity, 3),
                    "query": query,
                }
            )
            if len(ranked) >= limit:
                break
        results.append(ranked)
    return results

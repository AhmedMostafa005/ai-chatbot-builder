from __future__ import annotations

import re

import numpy as np
from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Chunk
from app.services.embeddings import embed_texts, rerank_scores

RRF_K = 60
_QUERY_NOISE = re.compile(r'["\'|!():&^]+')


def _keyword_query(question: str) -> str:
    clean = _QUERY_NOISE.sub(" ", question)[:500]
    return re.sub(r"\s+", " ", clean).strip()


def _safe_variant(variant: str) -> str:
    return " ".join(variant.split())[:500]


def _dense_candidates(db: Session, tenant_id: str, bot_id: str, vectors: list[list[float]], fetch_k: int) -> list[tuple[Chunk, float]]:
    best: dict[str, tuple[Chunk, float]] = {}
    for vector in vectors:
        stmt = (
            select(Chunk, (1 - Chunk.embedding.cosine_distance(vector)).label("score"))
            .where(Chunk.tenant_id == tenant_id, Chunk.bot_id == bot_id)
            .order_by(Chunk.embedding.cosine_distance(vector))
            .limit(fetch_k)
        )
        for chunk, score in db.execute(stmt).all():
            similarity = float(score)
            if chunk.id not in best or similarity > best[chunk.id][1]:
                best[chunk.id] = (chunk, similarity)
    return sorted(best.values(), key=lambda item: item[1], reverse=True)


def _keyword_candidates(db: Session, tenant_id: str, bot_id: str, question: str, fetch_k: int) -> list[tuple[Chunk, int]]:
    query = _keyword_query(question)
    if not query:
        return []
    tsv = func.to_tsvector("simple", Chunk.content)
    tsq = func.websearch_to_tsquery("simple", query)
    stmt = (
        select(Chunk)
        .where(Chunk.tenant_id == tenant_id, Chunk.bot_id == bot_id, tsv.op("@@")(tsq))
        .order_by(func.ts_rank(tsv, tsq).desc())
        .limit(fetch_k)
    )
    return [(chunk, i) for i, chunk in enumerate(db.scalars(stmt).all())]


def _fuse(dense: list[tuple[Chunk, float]], keyword: list[tuple[Chunk, int]]) -> list[dict]:
    entries: dict[str, dict] = {}
    for rank, (chunk, similarity) in enumerate(dense):
        entry = entries.setdefault(chunk.id, {"chunk": chunk, "dense": None, "kw_rank": None})
        if entry["dense"] is None or similarity > entry["dense"]:
            entry["dense"] = similarity
    for rank, (chunk, _) in enumerate(keyword):
        entry = entries.setdefault(chunk.id, {"chunk": chunk, "dense": None, "kw_rank": None})
        if entry["kw_rank"] is None:
            entry["kw_rank"] = rank
    fused = []
    for entry in entries.values():
        score = 0.0
        if entry["dense"] is not None:
            best_rank = min(
                (i for i, (chunk, _) in enumerate(dense) if chunk.id == entry["chunk"].id),
                default=None,
            )
            if best_rank is not None:
                score += 1 / (RRF_K + best_rank)
        if entry["kw_rank"] is not None:
            score += 1 / (RRF_K + entry["kw_rank"])
        entry["rrf"] = score
        fused.append(entry)
    fused.sort(key=lambda e: e["rrf"], reverse=True)
    return fused


def _apply_rerank(question: str, entries: list[dict], top_n: int | None = None) -> None:
    if not settings.enable_rerank:
        return
    subset = entries[:top_n] if top_n else entries
    if len(subset) < 2:
        return
    try:
        scores = rerank_scores(question, [e["chunk"].content for e in subset])
    except Exception:
        return
    for entry, score in zip(subset, scores):
        entry["rerank"] = score


def _passes_threshold(entry: dict, min_similarity: float) -> bool:
    if entry["dense"] is not None and entry["dense"] >= min_similarity:
        return True
    return entry["kw_rank"] is not None


def _relevance(entry: dict) -> float:
    return entry.get("rerank", entry["rrf"])


def _mmr_select(entries: list[dict], query_vector: list[float], k: int, lam: float) -> list[dict]:
    if len(entries) <= k:
        return sorted(entries, key=_relevance, reverse=True)
    candidates = list(entries)
    matrix = np.asarray([e["chunk"].embedding for e in candidates], dtype="float32")
    relevance = np.asarray([_relevance(e) for e in candidates], dtype="float32")
    if relevance.max() > relevance.min():
        relevance = (relevance - relevance.min()) / (relevance.max() - relevance.min())
    else:
        relevance = np.ones_like(relevance)
    available = np.ones(len(candidates), dtype=bool)
    chosen: list[int] = []
    sims_so_far: list[np.ndarray] = []
    while len(chosen) < k and available.any():
        if not chosen:
            idx = int(np.argmax(np.where(available, relevance, -np.inf)))
        else:
            penalty = np.max(np.asarray(sims_so_far), axis=0)
            utility = np.where(available, lam * relevance - (1 - lam) * penalty, -np.inf)
            idx = int(np.argmax(utility))
        sims = matrix @ matrix[idx]
        chosen.append(idx)
        sims_so_far.append(sims)
        available[idx] = False
    return [candidates[i] for i in chosen]


def _expand_neighbors(db: Session, tenant_id: str, bot_id: str, selected: list[Chunk], window: int, budget: int) -> list[Chunk]:
    if window <= 0 or budget <= 0 or not selected:
        return list(selected)
    chosen_ids = {c.id for c in selected}
    wanted: set[tuple[str, int]] = set()
    for chunk in selected:
        for offset in range(-window, window + 1):
            idx = chunk.chunk_index + offset
            if idx >= 0 and (chunk.document_id, idx) not in {(c.document_id, c.chunk_index) for c in selected}:
                wanted.add((chunk.document_id, idx))
    if not wanted:
        return list(selected)
    stmt = select(Chunk).where(
        Chunk.tenant_id == tenant_id,
        Chunk.bot_id == bot_id,
        tuple_(Chunk.document_id, Chunk.chunk_index).in_(list(wanted)),
    )
    neighbors: dict[tuple[str, int], Chunk] = {(c.document_id, c.chunk_index): c for c in db.scalars(stmt).all()}
    ordered: list[Chunk] = []
    used = 0
    for chunk in selected:
        if used + len(chunk.content) > budget:
            break
        ordered.append(chunk)
        used += len(chunk.content)
        for offset in range(-window, window + 1):
            if offset == 0:
                continue
            idx = chunk.chunk_index + offset
            neighbor = neighbors.get((chunk.document_id, idx))
            if neighbor and neighbor.id not in chosen_ids and used + len(neighbor.content) <= budget:
                ordered.append(neighbor)
                used += len(neighbor.content)
    return ordered


def retrieve(db: Session, tenant_id: str, bot_id: str, question: str, limit: int | None = None, variants: list[str] | None = None) -> list[Chunk]:
    top_k = limit if limit else settings.retrieval_top_k
    fetch_k = max(settings.retrieval_fetch_k, top_k * 2)
    queries = [question]
    for variant in variants or []:
        clean = _safe_variant(variant)
        if clean and clean not in queries:
            queries.append(clean)
    query_vectors = embed_texts(queries)
    question_vector = query_vectors[0]
    dense = _dense_candidates(db, tenant_id, bot_id, query_vectors, fetch_k)
    keyword = _keyword_candidates(db, tenant_id, bot_id, question, fetch_k)
    if not dense and not keyword:
        return []
    fused = _fuse(dense, keyword)
    candidates = [e for e in fused if _passes_threshold(e, settings.min_similarity)]
    if not candidates:
        return []
    _apply_rerank(question, candidates, settings.rerank_candidates)
    selected = _mmr_select(candidates, question_vector, top_k, settings.mmr_lambda)
    chunks = [e["chunk"] for e in sorted(selected, key=_relevance, reverse=True)]
    return _expand_neighbors(db, tenant_id, bot_id, chunks, settings.neighbor_window, settings.max_context_chars)

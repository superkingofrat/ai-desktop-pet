"""Semantic cache — embed queries and cache LLM responses with similarity matching."""

from __future__ import annotations

import difflib
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger("assistant.cache")

_EMBEDDING_MODEL = None


def _get_embedder():
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_MODEL
    try:
        old_to = socket.getdefaulttimeout()
        socket.setdefaulttimeout(5)
        from fastembed import TextEmbedding
        _EMBEDDING_MODEL = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
        socket.setdefaulttimeout(old_to)
        logger.info("Embedding model loaded: sentence-transformers/all-MiniLM-L6-v2")
    except Exception as e:
        logger.warning("Embedding unavailable (%s); using fuzzy + exact fallback", e)
        _EMBEDDING_MODEL = None
        try:
            socket.setdefaulttimeout(None)
        except Exception:
            pass
    return _EMBEDDING_MODEL


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(ai * bi for ai, bi in zip(a, b))
    na = sum(ai * ai for ai in a) ** 0.5
    nb = sum(bi * bi for bi in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class SemanticCache:
    """Cache LLM responses indexed by semantic embedding.

    Fallback order:
      1. Embedding (cosine similarity > threshold)
      2. difflib fuzzy match (ratio > 0.85)
      3. Exact text match
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS semantic_cache (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        query     TEXT NOT NULL,
        embedding BLOB,
        response  TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_cache_created ON semantic_cache(created_at DESC);
    """

    def __init__(self, db_path: str | Path = "data/cache.db", threshold: float = 0.95):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.threshold = threshold
        self._embedder = None
        self._init_db()

    # ── Public API ───────────────────────────────────────────────

    def lookup(self, query: str) -> str | None:
        """Return cached response if a semantically similar query exists."""
        vec = self._embed(query)
        if vec is not None:
            # ── Embedding-based lookup ─────
            best_sim, best_resp = 0.0, None
            for row_id, stored_vec, stored_resp in self._all_entries():
                if stored_vec is None:
                    continue
                sim = _cosine_sim(vec, stored_vec)
                if sim > best_sim:
                    best_sim, best_resp = sim, stored_resp
            if best_sim >= self.threshold and best_resp is not None:
                logger.info("Cache HIT  (embed sim=%.4f)  query=%.50s", best_sim, query)
                return best_resp
            logger.info("Cache MISS (embed best=%.4f < %.2f)", best_sim, self.threshold)
            return None

        # ── Fallback 1: difflib fuzzy match ──
        best = self._fuzzy_lookup(query)
        if best is not None:
            return best

        # ── Fallback 2: exact match ──
        return self._exact_lookup(query)

    def store(self, query: str, response: str) -> None:
        """Store a query and its response in the cache."""
        vec = self._embed(query)
        embedding_json = json.dumps(vec) if vec else None
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO semantic_cache (query, embedding, response) VALUES (?, ?, ?)",
                (query, embedding_json, response),
            )
        logger.debug("Cache STORE  query=%.50s", query)

    def clear(self) -> None:
        """Delete all cached entries."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM semantic_cache")

    # ── Internals ────────────────────────────────────────────────

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(self.SCHEMA)

    def _embed(self, text: str) -> list[float] | None:
        if self._embedder is None:
            self._embedder = _get_embedder()
        if self._embedder is None:
            return None
        try:
            for vec in self._embedder.embed([text]):
                return vec.tolist()
        except Exception as e:
            logger.warning("Embedding failed: %s", e)
            return None

    def _fuzzy_lookup(self, query: str) -> str | None:
        """difflib-based fuzzy match (handles small typos and rephrasings)."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute("SELECT query, response FROM semantic_cache").fetchall()
        best_ratio, best_resp = 0.0, None
        for q, r in rows:
            ratio = difflib.SequenceMatcher(None, query, q).ratio()
            if ratio > best_ratio:
                best_ratio, best_resp = ratio, r
        if best_ratio >= 0.85 and best_resp is not None:
            logger.info("Cache HIT  (fuzzy ratio=%.4f)  query=%.50s", best_ratio, query)
            return best_resp
        return None

    def _exact_lookup(self, query: str) -> str | None:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT response FROM semantic_cache WHERE query = ? ORDER BY id DESC LIMIT 1",
                (query,),
            ).fetchone()
        return row[0] if row else None

    def _all_entries(self) -> list[tuple[int, list[float] | None, str]]:
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT id, embedding, response FROM semantic_cache ORDER BY id"
            ).fetchall()
        result = []
        for row_id, emb_json, resp in rows:
            vec = json.loads(emb_json) if emb_json else None
            result.append((row_id, vec, resp))
        return result

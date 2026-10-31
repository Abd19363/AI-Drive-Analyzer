import asyncio
import hashlib
import logging
import threading
from typing import List
from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.future import select
from app.config import settings
from app.models import EmbeddingCache

logger = logging.getLogger(__name__)

# Global lazy-loaded embedding model
_model = None
_model_lock = threading.Lock()

def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    return _model

def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _encode_texts(texts: List[str]):
    return get_embedding_model().encode(texts, normalize_embeddings=True)

async def get_or_create_embeddings(texts: List[str], db: AsyncSession) -> List[List[float]]:
    """
    Retrieves embeddings from embedding_cache if already computed,
    otherwise calculates with all-MiniLM-L6-v2 (384-dim) and saves to cache.
    """
    if not texts:
        return []

    embeddings = [None] * len(texts)
    hashes = [compute_hash(t) for t in texts]
    missing_indices = []
    missing_texts = []

    # Check cache for existing hashes
    result = await db.execute(select(EmbeddingCache).where(EmbeddingCache.content_hash.in_(hashes)))
    cached_records = {rec.content_hash: rec.embedding for rec in result.scalars().all()}

    for i, h in enumerate(hashes):
        if h in cached_records:
            # PostgreSQL vector type to list of floats
            cached_val = cached_records[h]
            if hasattr(cached_val, "tolist"):
                embeddings[i] = cached_val.tolist()
            else:
                embeddings[i] = list(cached_val)
        else:
            missing_indices.append(i)
            missing_texts.append(texts[i])

    # If any texts are not in cache, compute their embeddings
    if missing_texts:
        # ── Deduplicate within this batch by content_hash ──
        seen_hashes: dict[str, int] = {}          # hash → first missing-list index
        deduped_indices: list[int] = []
        deduped_texts: list[str] = []
        dup_map: dict[int, str] = {}              # orig_idx → hash (for dupes)

        for pos, orig_idx in enumerate(missing_indices):
            h = hashes[orig_idx]
            if h not in seen_hashes:
                seen_hashes[h] = len(deduped_indices)
                deduped_indices.append(orig_idx)
                deduped_texts.append(missing_texts[pos])
            else:
                dup_map[orig_idx] = h              # will copy later

        computed = await asyncio.to_thread(
            _encode_texts, deduped_texts
        )

        # Map computed vectors back (unique entries)
        hash_to_vector: dict[str, list[float]] = {}
        for pos, orig_idx in enumerate(deduped_indices):
            emb_vector = computed[pos].tolist()
            embeddings[orig_idx] = emb_vector
            hash_to_vector[hashes[orig_idx]] = emb_vector

        # Copy vectors for duplicate entries
        for orig_idx, h in dup_map.items():
            embeddings[orig_idx] = hash_to_vector[h]

        # ── Bulk upsert with ON CONFLICT DO NOTHING ──
        if deduped_texts:
            rows = [
                {
                    "content_hash": hashes[orig_idx],
                    "model_name": settings.EMBEDDING_MODEL_NAME,
                    "embedding": hash_to_vector[hashes[orig_idx]],
                }
                for orig_idx in deduped_indices
            ]
            stmt = pg_insert(EmbeddingCache).values(rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=["content_hash"])
            await db.execute(stmt)
            await db.commit()
            logger.debug(
                "Cached %d new embeddings (%d duplicates skipped in batch)",
                len(deduped_texts),
                len(dup_map),
            )

    return embeddings

def embed_single_query(query: str) -> List[float]:
    """
    Synchronously embed a user query using all-MiniLM-L6-v2
    """
    model = get_embedding_model()
    return model.encode(query, normalize_embeddings=True).tolist()

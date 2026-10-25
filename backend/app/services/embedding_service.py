import asyncio
import hashlib
import threading
from typing import List
from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.config import settings
from app.models import EmbeddingCache

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
        computed = await asyncio.to_thread(
            _encode_texts, missing_texts
        )
        for idx_in_missing, orig_idx in enumerate(missing_indices):
            emb_vector = computed[idx_in_missing].tolist()
            embeddings[orig_idx] = emb_vector

            # Insert into database cache
            cache_entry = EmbeddingCache(
                content_hash=hashes[orig_idx],
                model_name=settings.EMBEDDING_MODEL_NAME,
                embedding=emb_vector
            )
            db.add(cache_entry)

        await db.commit()

    return embeddings

def embed_single_query(query: str) -> List[float]:
    """
    Synchronously embed a user query using all-MiniLM-L6-v2
    """
    model = get_embedding_model()
    return model.encode(query, normalize_embeddings=True).tolist()

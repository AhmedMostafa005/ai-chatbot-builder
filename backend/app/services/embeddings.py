from functools import lru_cache

from sentence_transformers import SentenceTransformer
from app.core.config import settings


@lru_cache(maxsize=1)
def model():
    return SentenceTransformer(settings.embedding_model)


@lru_cache(maxsize=1)
def reranker():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(settings.rerank_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors = model().encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def rerank_scores(question: str, texts: list[str]) -> list[float]:
    pairs = [(question, text[:1500]) for text in texts]
    scores = reranker().predict(pairs, batch_size=32, show_progress_bar=False)
    return [float(s) for s in scores]

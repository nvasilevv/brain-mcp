import uuid
from datetime import datetime, timezone

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from .config import settings

EMBEDDING_DIM = 384
MODEL_NAME = "all-MiniLM-L6-v2"

_client: QdrantClient | None = None
_model: SentenceTransformer | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_host)
    return _client


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def ensure_collection() -> None:
    client = get_client()
    existing = {c.name for c in client.get_collections().collections}
    if settings.collection_name not in existing:
        client.create_collection(
            collection_name=settings.collection_name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )


def push_thought(text: str, category: str = "general") -> str:
    client = get_client()
    model = get_model()
    vector = model.encode(text).tolist()
    point_id = str(uuid.uuid4())
    client.upsert(
        collection_name=settings.collection_name,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "text": text,
                    "category": category,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        ],
    )
    return point_id


def retrieve_thoughts(query: str, limit: int = 5) -> list[dict]:
    client = get_client()
    model = get_model()
    vector = model.encode(query).tolist()
    results = client.query_points(
        collection_name=settings.collection_name,
        query=vector,
        limit=limit,
        with_payload=True,
    ).points
    return [
        {
            "score": r.score,
            "text": r.payload.get("text", ""),
            "category": r.payload.get("category", ""),
            "timestamp": r.payload.get("timestamp", ""),
        }
        for r in results
    ]

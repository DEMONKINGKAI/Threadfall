"""
VectorStore — thin adapter over Qdrant or ChromaDB.

Configured via environment variables:
  VECTOR_DB_TYPE   "qdrant" | "chroma"   (default: "chroma")
  VECTOR_DB_URL    http://localhost:6333  (Qdrant) or http://localhost:8001 (Chroma server)
                   Omit to use in-process Chroma (dev mode — no Docker needed)
  VECTOR_DB_PATH   ./data/chroma         (in-process Chroma persistence directory)

Document schema (one document per action entry + one metadata doc per session):

  Entry document
  ──────────────
  id             : str   "{session_id}__entry__{index}"
  session_id     : str
  entry_index    : int   0-based, insertion order
  timestamp      : str   ISO-8601
  player_input   : str
  action_type    : str
  outcome        : str
  probability    : float
  relevant_stat  : str
  downstream     : str   JSON-encoded dict
  narrative      : str
  scene_text     : str
  world_state    : str   JSON-encoded dict
  current_act    : int
  doc_type       : "entry"

  Session metadata document
  ─────────────────────────
  id             : str   "{session_id}__meta"
  session_id     : str
  campaign_key   : str
  campaign_name  : str
  character      : str   JSON-encoded character dict
  act_titles     : str   JSON-encoded dict
  dag_meta       : str   JSON-encoded dict
  created_at     : str   ISO-8601
  final_outcome  : str | None
  doc_type       : "meta"

Vector payload: embedding of  player_input + " " + narrative
(used for RAG similarity retrieval in Phase 6)
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

# ── Embedding helper ─────────────────────────────────────────────────────────

_embedder = None  # lazy-loaded SentenceTransformer


def _embed(text: str) -> list[float]:
    """Return a 384-dim embedding vector using all-MiniLM-L6-v2."""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
            print("[storage] SentenceTransformer loaded (all-MiniLM-L6-v2)")
        except ImportError:
            print("[storage] sentence-transformers not installed — using zero vector")
            _embedder = "unavailable"

    if _embedder == "unavailable":
        return [0.0] * 384

    return _embedder.encode(text, normalize_embeddings=True).tolist()


# ── Protocol ─────────────────────────────────────────────────────────────────

class VectorStore(ABC):
    """Interface every backend must satisfy."""

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def save_session_meta(
        self,
        session_id: str,
        campaign_key: str,
        campaign_name: str,
        character: dict,
        act_titles: dict,
        dag_meta: dict,
    ) -> None: ...

    @abstractmethod
    def update_session_outcome(self, session_id: str, final_outcome: str) -> None: ...

    @abstractmethod
    def save_entry(self, session_id: str, entry_index: int, entry: dict) -> None: ...

    @abstractmethod
    def get_session_meta(self, session_id: str) -> dict | None: ...

    @abstractmethod
    def get_entries(self, session_id: str) -> list[dict]: ...

    @abstractmethod
    def list_sessions(self) -> list[dict]: ...

    @abstractmethod
    def delete_session(self, session_id: str) -> None: ...

    @abstractmethod
    def search_similar(self, session_id: str, query: str, k: int = 3) -> list[dict]: ...


# ── Qdrant backend ────────────────────────────────────────────────────────────

class QdrantStore(VectorStore):
    _COLLECTION = "threadfall"
    _DIM = 384

    def __init__(self, url: str = "http://localhost:6333"):
        self._url = url
        self._client = None

    def connect(self) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        self._client = QdrantClient(url=self._url)
        existing = {c.name for c in self._client.get_collections().collections}
        if self._COLLECTION not in existing:
            self._client.create_collection(
                collection_name=self._COLLECTION,
                vectors_config=VectorParams(size=self._DIM, distance=Distance.COSINE),
            )
            print(f"[storage/qdrant] created collection '{self._COLLECTION}'")
        else:
            print(f"[storage/qdrant] connected to existing collection '{self._COLLECTION}'")

    def _point_id(self, doc_id: str) -> str:
        # Qdrant point IDs must be UUID or unsigned int — use the string as a named alias
        # We store it as payload and use a deterministic UUID derived from the string
        import hashlib
        return str(uuid.UUID(hashlib.md5(doc_id.encode()).hexdigest()))

    def save_session_meta(self, session_id, campaign_key, campaign_name, character, act_titles, dag_meta):
        from qdrant_client.models import PointStruct
        import uuid
        doc_id = f"{session_id}__meta"
        payload = {
            "doc_id":        doc_id,
            "session_id":    session_id,
            "campaign_key":  campaign_key,
            "campaign_name": campaign_name,
            "character":     json.dumps(character),
            "act_titles":    json.dumps(act_titles),
            "dag_meta":      json.dumps(dag_meta),
            "created_at":    _now(),
            "final_outcome": None,
            "doc_type":      "meta",
        }
        self._client.upsert(
            collection_name=self._COLLECTION,
            points=[PointStruct(id=self._point_id(doc_id), vector=[0.0]*self._DIM, payload=payload)],
        )

    def update_session_outcome(self, session_id: str, final_outcome: str) -> None:
        from qdrant_client.models import PointIdsList
        doc_id = f"{session_id}__meta"
        self._client.set_payload(
            collection_name=self._COLLECTION,
            payload={"final_outcome": final_outcome},
            points=PointIdsList(points=[self._point_id(doc_id)]),
        )

    def save_entry(self, session_id: str, entry_index: int, entry: dict) -> None:
        from qdrant_client.models import PointStruct
        doc_id = f"{session_id}__entry__{entry_index}"
        vector = _embed(entry.get("player_input", "") + " " + entry.get("narrative", ""))
        payload = {
            "doc_id":       doc_id,
            "session_id":   session_id,
            "entry_index":  entry_index,
            "timestamp":    _now(),
            "doc_type":     "entry",
            **_serialise_entry(entry),
        }
        self._client.upsert(
            collection_name=self._COLLECTION,
            points=[PointStruct(id=self._point_id(doc_id), vector=vector, payload=payload)],
        )

    def get_session_meta(self, session_id: str) -> dict | None:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        results = self._client.scroll(
            collection_name=self._COLLECTION,
            scroll_filter=Filter(must=[
                FieldCondition(key="session_id",  match=MatchValue(value=session_id)),
                FieldCondition(key="doc_type",    match=MatchValue(value="meta")),
            ]),
            limit=1,
            with_payload=True,
        )[0]
        return _deserialise_meta(results[0].payload) if results else None

    def get_entries(self, session_id: str) -> list[dict]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        results, _ = self._client.scroll(
            collection_name=self._COLLECTION,
            scroll_filter=Filter(must=[
                FieldCondition(key="session_id", match=MatchValue(value=session_id)),
                FieldCondition(key="doc_type",   match=MatchValue(value="entry")),
            ]),
            limit=1000,
            with_payload=True,
        )
        entries = [_deserialise_entry(r.payload) for r in results]
        return sorted(entries, key=lambda e: e["entry_index"])

    def list_sessions(self) -> list[dict]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        results, _ = self._client.scroll(
            collection_name=self._COLLECTION,
            scroll_filter=Filter(must=[
                FieldCondition(key="doc_type", match=MatchValue(value="meta")),
            ]),
            limit=500,
            with_payload=True,
        )
        return [_deserialise_meta(r.payload) for r in results]

    def delete_session(self, session_id: str) -> None:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        self._client.delete(
            collection_name=self._COLLECTION,
            points_selector=Filter(must=[
                FieldCondition(key="session_id", match=MatchValue(value=session_id)),
            ]),
        )

    def search_similar(self, session_id: str, query: str, k: int = 3) -> list[dict]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        vector = _embed(query)
        results = self._client.search(
            collection_name=self._COLLECTION,
            query_vector=vector,
            query_filter=Filter(must=[
                FieldCondition(key="session_id", match=MatchValue(value=session_id)),
                FieldCondition(key="doc_type",   match=MatchValue(value="entry")),
            ]),
            limit=k,
            with_payload=True,
        )
        return [_deserialise_entry(r.payload) for r in results]


# ── ChromaDB backend ──────────────────────────────────────────────────────────

class ChromaStore(VectorStore):
    _COLLECTION = "threadfall"

    def __init__(self, url: str | None = None, path: str = "./data/chroma"):
        self._url  = url
        self._path = path
        self._col  = None

    def connect(self) -> None:
        import chromadb

        if self._url:
            client = chromadb.HttpClient(host=self._url.replace("http://", "").split(":")[0],
                                         port=int(self._url.split(":")[-1]))
            print(f"[storage/chroma] connected to server {self._url}")
        else:
            client = chromadb.PersistentClient(path=self._path)
            print(f"[storage/chroma] in-process mode, data at {self._path}")

        self._col = client.get_or_create_collection(
            name=self._COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    def _ensure(self):
        if self._col is None:
            raise RuntimeError("ChromaStore.connect() was not called")

    def save_session_meta(self, session_id, campaign_key, campaign_name, character, act_titles, dag_meta):
        self._ensure()
        doc_id = f"{session_id}__meta"
        meta = {
            "session_id":    session_id,
            "campaign_key":  campaign_key,
            "campaign_name": campaign_name,
            "character":     json.dumps(character),
            "act_titles":    json.dumps(act_titles),
            "dag_meta":      json.dumps(dag_meta),
            "created_at":    _now(),
            "final_outcome": "",
            "doc_type":      "meta",
        }
        self._col.upsert(ids=[doc_id], metadatas=[meta],
                         documents=[f"session {session_id} {campaign_name}"],
                         embeddings=[[0.0]*384])

    def update_session_outcome(self, session_id: str, final_outcome: str) -> None:
        self._ensure()
        doc_id = f"{session_id}__meta"
        existing = self._col.get(ids=[doc_id], include=["metadatas"])
        if existing["metadatas"]:
            meta = existing["metadatas"][0]
            meta["final_outcome"] = final_outcome
            self._col.update(ids=[doc_id], metadatas=[meta])

    def save_entry(self, session_id: str, entry_index: int, entry: dict) -> None:
        self._ensure()
        doc_id = f"{session_id}__entry__{entry_index}"
        text   = entry.get("player_input", "") + " " + entry.get("narrative", "")
        vector = _embed(text)
        meta = {
            "session_id":  session_id,
            "entry_index": entry_index,
            "timestamp":   _now(),
            "doc_type":    "entry",
            **_serialise_entry(entry),
        }
        self._col.upsert(ids=[doc_id], metadatas=[meta],
                         documents=[text], embeddings=[vector])

    def get_session_meta(self, session_id: str) -> dict | None:
        self._ensure()
        doc_id = f"{session_id}__meta"
        result = self._col.get(ids=[doc_id], include=["metadatas"])
        if result["metadatas"]:
            return _deserialise_meta(result["metadatas"][0])
        return None

    def get_entries(self, session_id: str) -> list[dict]:
        self._ensure()
        results = self._col.get(
            where={"$and": [{"session_id": session_id}, {"doc_type": "entry"}]},
            include=["metadatas"],
        )
        entries = [_deserialise_entry(m) for m in results["metadatas"]]
        return sorted(entries, key=lambda e: e["entry_index"])

    def list_sessions(self) -> list[dict]:
        self._ensure()
        results = self._col.get(where={"doc_type": "meta"}, include=["metadatas"])
        return [_deserialise_meta(m) for m in results["metadatas"]]

    def delete_session(self, session_id: str) -> None:
        self._ensure()
        # delete meta
        self._col.delete(ids=[f"{session_id}__meta"])
        # delete all entries
        existing = self._col.get(
            where={"$and": [{"session_id": session_id}, {"doc_type": "entry"}]},
        )
        if existing["ids"]:
            self._col.delete(ids=existing["ids"])

    def search_similar(self, session_id: str, query: str, k: int = 3) -> list[dict]:
        self._ensure()
        vector = _embed(query)
        results = self._col.query(
            query_embeddings=[vector],
            n_results=k,
            where={"$and": [{"session_id": session_id}, {"doc_type": "entry"}]},
            include=["metadatas"],
        )
        return [_deserialise_entry(m) for m in results["metadatas"][0]]


# ── Serialisation helpers ─────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialise_entry(entry: dict) -> dict:
    """Flatten an action entry to a JSON-safe flat dict for vector DB storage."""
    return {
        "player_input":  entry.get("player_input", ""),
        "action_type":   entry.get("action_type", ""),
        "outcome":       entry.get("outcome", ""),
        "probability":   float(entry.get("probability", 0.0)),
        "relevant_stat": entry.get("relevant_stat", ""),
        "downstream":    json.dumps(entry.get("downstream_changes", {})),
        "narrative":     entry.get("narrative", ""),
        "scene_text":    entry.get("scene_text", ""),
        "world_state":   json.dumps(entry.get("world_state", {})),
        "current_act":   int(entry.get("current_act", 1)),
    }


def _deserialise_entry(payload: dict) -> dict:
    return {
        "entry_index":        payload.get("entry_index", 0),
        "timestamp":          payload.get("timestamp", ""),
        "player_input":       payload.get("player_input", ""),
        "action_type":        payload.get("action_type", ""),
        "outcome":            payload.get("outcome", ""),
        "probability":        float(payload.get("probability", 0.0)),
        "relevant_stat":      payload.get("relevant_stat", ""),
        "downstream_changes": json.loads(payload.get("downstream", "{}")),
        "narrative":          payload.get("narrative", ""),
        "scene_text":         payload.get("scene_text", ""),
        "world_state":        json.loads(payload.get("world_state", "{}")),
        "current_act":        int(payload.get("current_act", 1)),
    }


def _deserialise_meta(payload: dict) -> dict:
    return {
        "session_id":    payload.get("session_id", ""),
        "campaign_key":  payload.get("campaign_key", ""),
        "campaign_name": payload.get("campaign_name", ""),
        "character":     json.loads(payload.get("character", "{}")),
        "act_titles":    json.loads(payload.get("act_titles", "{}")),
        "dag_meta":      json.loads(payload.get("dag_meta", "{}")),
        "created_at":    payload.get("created_at", ""),
        "final_outcome": payload.get("final_outcome") or None,
    }


# ── Singleton ─────────────────────────────────────────────────────────────────

import uuid  # noqa: E402  (needed inside methods above, imported here for module scope)

_store: VectorStore | None = None


def get_store() -> VectorStore:
    """Return the configured VectorStore singleton. Call connect() first."""
    if _store is None:
        raise RuntimeError("Vector store not initialised. Call init_store() at startup.")
    return _store


def init_store() -> VectorStore:
    """
    Read environment, instantiate the right backend, call connect(), cache as singleton.

    VECTOR_DB_TYPE   "qdrant" | "chroma"          default: "chroma"
    VECTOR_DB_URL    e.g. http://localhost:6333    if omitted → in-process Chroma
    VECTOR_DB_PATH   ./data/chroma                Chroma persistence dir
    """
    global _store

    db_type = os.environ.get("VECTOR_DB_TYPE", "chroma").lower().strip()
    db_url  = os.environ.get("VECTOR_DB_URL", "").strip() or None
    db_path = os.environ.get("VECTOR_DB_PATH", "./data/chroma")

    if db_type == "qdrant":
        _store = QdrantStore(url=db_url or "http://localhost:6333")
    else:
        _store = ChromaStore(url=db_url, path=db_path)

    _store.connect()
    return _store

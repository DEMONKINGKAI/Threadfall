"""
Threadfall storage layer.

Entry point: get_store() returns the configured VectorStore singleton.
"""

from backend.storage.vector_store import VectorStore, get_store

__all__ = ["VectorStore", "get_store"]

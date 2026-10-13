"""Compatibility wrapper around SMARTA's SQLite full-text retriever."""

from data_store import retrieve as _retrieve


def retrieve(query: str, k: int = 6) -> list[dict]:
    return _retrieve(query, limit=k)

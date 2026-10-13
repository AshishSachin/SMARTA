"""Load the documents that ship with SMARTA, plus an optional SQL source."""

from __future__ import annotations

import os
import logging
import json
from pathlib import Path
from typing import Any

import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"


def mysql_credentials_available() -> bool:
    if os.environ.get("SMARTA_DATABASE_URL"):
        return True
    try:
        import keyring
        return keyring.get_password("Mysql@localhost:3306", "root") is not None
    except Exception:
        return False


def _clean(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def load_spreadsheets() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    documents: list[dict[str, Any]] = []
    maintenance_rows: list[dict[str, str]] = []
    for path in sorted(DATA_DIR.rglob("*.xlsx")) + sorted(DATA_DIR.rglob("*.xls")):
        try:
            sheets = pd.read_excel(path, sheet_name=None)
        except Exception as exc:
            print(f"Skipping unreadable spreadsheet {path.name}: {exc}")
            continue
        for sheet_name, frame in sheets.items():
            for row_number, (_, row) in enumerate(frame.iterrows(), start=2):
                fields = {str(key).strip(): _clean(value) for key, value in row.items()}
                fields = {key: value for key, value in fields.items() if value}
                if not fields:
                    continue
                text = "\n".join(f"{key}: {value}" for key, value in fields.items())
                documents.append({
                    "text": text,
                    "source": path.name,
                    "locator": f"{sheet_name}, row {row_number}",
                    "metadata": fields,
                })
                normalized = {key.lower().replace(" ", "_"): value for key, value in fields.items()}
                maintenance_rows.append({
                    "machine": normalized.get("machine", ""),
                    "fault": normalized.get("fault", ""),
                    "symptoms": normalized.get("symptoms", ""),
                    "cause": normalized.get("cause", ""),
                    "action": normalized.get("action", normalized.get("action_taken", "")),
                    "engineer_notes": normalized.get("engineer_notes", ""),
                    "source": f"{path.name} / {sheet_name}, row {row_number}",
                })
    return documents, maintenance_rows


def load_pdfs() -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    for path in sorted(DATA_DIR.rglob("*.pdf")):
        try:
            reader = PdfReader(str(path))
            for page_number, page in enumerate(reader.pages, start=1):
                text = " ".join((page.extract_text() or "").split())
                if not text:
                    continue
                # Keep each chunk tied to its real PDF page for useful citations.
                start = 0
                while start < len(text):
                    chunk = text[start : start + 1200]
                    if chunk.strip():
                        documents.append({
                            "text": chunk,
                            "source": path.name,
                            "locator": f"page {page_number}",
                            "metadata": {"page": page_number},
                        })
                    if start + 1200 >= len(text):
                        break
                    start += 950
        except Exception as exc:
            print(f"Skipping unreadable PDF {path.name}: {exc}")
    return documents


def load_sql_rows(database_url_override: Any = None) -> list[dict[str, Any]]:
    """Read local MySQL tables from an env URL or the macOS Keychain entry."""
    database_url = database_url_override or os.environ.get("SMARTA_DATABASE_URL")
    try:
        from sqlalchemy import create_engine, inspect, text
        if database_url:
            engine = create_engine(database_url, pool_pre_ping=True)
        else:
            import keyring
            password = keyring.get_password("Mysql@localhost:3306", "root")
            if not password:
                return []
            from sqlalchemy.engine import URL

            database_url = URL.create(
                "mysql+pymysql", username="root", password=password,
                host="localhost", port=3306,
                database=os.environ.get("SMARTA_MYSQL_DATABASE", "smarta"),
            )
            engine = create_engine(database_url, pool_pre_ping=True)
        available_tables = set(inspect(engine).get_table_names())
        result: list[dict[str, Any]] = []
        with engine.connect() as connection:
            for table in ("maintenance_logs", "smarta_maintenance_logs"):
                if table not in available_tables:
                    continue
                rows = connection.execute(text(f"SELECT * FROM `{table}`")).mappings().all()
                for index, row in enumerate(rows, start=1):
                    fields = {str(key): "" if value is None else str(value) for key, value in row.items()}
                    body = "\n".join(f"{key}: {value}" for key, value in fields.items() if value)
                    result.append({
                        "text": body,
                        "source": f"MySQL {table}",
                        "locator": f"record {index}",
                        "metadata": fields,
                    })
            if "smarta_documents" in available_tables:
                rows = connection.execute(text(
                    "SELECT source, locator, content, metadata FROM smarta_documents"
                )).mappings().all()
                for row in rows:
                    result.append({
                        "text": str(row["content"] or ""),
                        "source": f"MySQL {row['source']}",
                        "locator": str(row["locator"] or ""),
                        "metadata": json.loads(row["metadata"] or "{}"),
                    })
        engine.dispose()
        return result
    except Exception as exc:
        # Local file ingestion must remain available if an optional database is down.
        # Never write a connection URL or driver diagnostic to logs.
        if database_url or os.environ.get("SMARTA_DATABASE_URL"):
            print("Optional MySQL source unavailable; check its secure connection settings.")
        return []


def get_document_bundle(database_url_override: Any = None) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    spreadsheet_docs, maintenance_rows = load_spreadsheets()
    documents = load_pdfs() + spreadsheet_docs + load_sql_rows(database_url_override)
    return documents, maintenance_rows


def get_documents() -> list[dict[str, Any]]:
    """Backward-compatible document list for the original indexing scripts."""
    documents, _ = get_document_bundle()
    return documents

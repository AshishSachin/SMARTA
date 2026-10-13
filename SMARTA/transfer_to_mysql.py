"""Copy SMARTA's local indexed source data to the configured local MySQL database.

Credentials come from SMARTA_DATABASE_URL or macOS Keychain. This script never
prompts for, prints, or writes a password.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import sys

import keyring
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from data_store import DB_PATH, initialize_corpus

SERVICE = "Mysql@localhost:3306"
ACCOUNT = "root"
DATABASE = os.environ.get("SMARTA_MYSQL_DATABASE", "smarta")


def main() -> int:
    configured_url = os.environ.get("SMARTA_DATABASE_URL")
    password = None if configured_url else keyring.get_password(SERVICE, ACCOUNT)
    if not configured_url and not password:
        print(
            "MySQL credential is not available in macOS Keychain. Add the existing "
            "localhost:3306 / root credential in Keychain Access with service "
            f"{SERVICE}, then rerun this script. SMARTA does not store the password in source or a .env file."
        )
        return 2

    if configured_url:
        server_url = configured_url
        target_url = configured_url
    else:
        server_url = URL.create(
            "mysql+pymysql", username=ACCOUNT, password=password,
            host="localhost", port=3306,
        )
        target_url = URL.create(
            "mysql+pymysql", username=ACCOUNT, password=password,
            host="localhost", port=3306, database=DATABASE,
        )

    server = create_engine(server_url, pool_pre_ping=True)
    try:
        with server.begin() as connection:
            connection.execute(text(
                f"CREATE DATABASE IF NOT EXISTS `{DATABASE}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            ))
    except Exception:
        print("Could not initialize the local SMARTA MySQL database. Check Keychain access and MySQL service status.")
        server.dispose()
        return 1
    server.dispose()

    # Build from all local files and include any records already present in MySQL.
    try:
        counts = initialize_corpus(force=True, database_url_override=target_url)
    except Exception:
        print("Could not refresh SMARTA's local corpus from MySQL and source files.")
        return 1

    destination = create_engine(target_url, pool_pre_ping=True)
    try:
        with sqlite3.connect(DB_PATH) as local:
            local.row_factory = sqlite3.Row
            documents = local.execute(
                "SELECT source, locator, text, metadata FROM documents ORDER BY id"
            ).fetchall()
            maintenance_rows = local.execute(
                "SELECT machine, fault, symptoms, cause, action, engineer_notes, source FROM maintenance_logs ORDER BY id"
            ).fetchall()

        with destination.begin() as connection:
            connection.execute(text("""CREATE TABLE IF NOT EXISTS smarta_documents (
                doc_id CHAR(64) NOT NULL PRIMARY KEY,
                source VARCHAR(255) NOT NULL,
                locator VARCHAR(255) NOT NULL,
                content LONGTEXT NOT NULL,
                metadata LONGTEXT NOT NULL,
                FULLTEXT KEY smarta_documents_fulltext (content)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""))
            connection.execute(text("""CREATE TABLE IF NOT EXISTS smarta_maintenance_logs (
                source_key CHAR(64) NOT NULL PRIMARY KEY,
                machine VARCHAR(255) NOT NULL,
                fault TEXT NOT NULL,
                symptoms TEXT NOT NULL,
                cause TEXT NOT NULL,
                action TEXT NOT NULL,
                engineer_notes TEXT NOT NULL,
                source VARCHAR(512) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""))

            document_sql = text("""INSERT INTO smarta_documents
                (doc_id, source, locator, content, metadata) VALUES
                (:doc_id, :source, :locator, :content, :metadata)
                ON DUPLICATE KEY UPDATE source=VALUES(source), locator=VALUES(locator),
                    content=VALUES(content), metadata=VALUES(metadata)""")
            document_parameters = []
            for row in documents:
                stable_key = "\0".join((row["source"], row["locator"], row["text"]))
                document_parameters.append({
                    "doc_id": hashlib.sha256(stable_key.encode("utf-8")).hexdigest(),
                    "source": row["source"],
                    "locator": row["locator"],
                    "content": row["text"],
                    "metadata": row["metadata"],
                })
            if document_parameters:
                connection.execute(document_sql, document_parameters)

            log_sql = text("""INSERT INTO smarta_maintenance_logs
                (source_key, machine, fault, symptoms, cause, action, engineer_notes, source) VALUES
                (:source_key, :machine, :fault, :symptoms, :cause, :action, :engineer_notes, :source)
                ON DUPLICATE KEY UPDATE machine=VALUES(machine), fault=VALUES(fault),
                    symptoms=VALUES(symptoms), cause=VALUES(cause), action=VALUES(action),
                    engineer_notes=VALUES(engineer_notes), source=VALUES(source)""")
            log_parameters = []
            for row in maintenance_rows:
                fields = {key: (row[key] or "") for key in (
                    "machine", "fault", "symptoms", "cause", "action", "engineer_notes", "source"
                )}
                fields["source_key"] = hashlib.sha256(fields["source"].encode("utf-8")).hexdigest()
                log_parameters.append(fields)
            if log_parameters:
                connection.execute(log_sql, log_parameters)
    except Exception:
        print("MySQL transfer failed. No source data was removed; verify MySQL permissions and retry.")
        destination.dispose()
        return 1
    finally:
        destination.dispose()

    print(
        "MySQL sync complete: "
        f"{len(documents)} document chunks and {len(maintenance_rows)} structured maintenance rows. "
        f"Local corpus: {counts['documents']} chunks, {counts['maintenance_records']} records."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

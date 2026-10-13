"""Force a refresh of SMARTA's local SQL and full-text document corpus."""

from data_store import initialize_corpus

if __name__ == "__main__":
    counts = initialize_corpus(force=True)
    print(
        "SMARTA corpus refreshed: "
        f"{counts['documents']} document chunks, "
        f"{counts['maintenance_records']} maintenance records, "
        f"{counts['sources']} source files."
    )

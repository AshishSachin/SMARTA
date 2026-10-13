"""Optional SQL source integration; configure SMARTA_DATABASE_URL in the environment."""

from document_loader import load_sql_rows


def get_sql_documents():
    return load_sql_rows()


if __name__ == "__main__":
    docs = get_sql_documents()
    print(f"Loaded {len(docs)} SQL maintenance records.")

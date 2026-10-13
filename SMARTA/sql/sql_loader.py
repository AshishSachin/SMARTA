"""Inspect the configured SQL maintenance source without printing credentials."""

from document_loader import load_sql_rows

if __name__ == "__main__":
    rows = load_sql_rows()
    print(f"Loaded {len(rows)} SQL maintenance records.")
    for row in rows[:3]:
        print(row["text"])

import pandas as pd
from pathlib import Path

def get_excel_documents():

    excel_path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "maintenance_history.xlsx"
    )

    df = pd.read_excel(excel_path)

    documents = []

    for _, row in df.iterrows():

        text = f"""
Machine: {row['Machine']}

Fault: {row['Fault']}

Symptoms: {row['Symptoms']}

Cause: {row['Cause']}

Action: {row['Action']}
"""

        documents.append({
            "text": text,
            "metadata": {
                "source": "excel",
                "machine": row["Machine"],
                "fault": row["Fault"]
            }
        })

    return documents


if __name__ == "__main__":

    docs = get_excel_documents()

    print(docs[0])
    print(f"\nTotal Documents: {len(docs)}")
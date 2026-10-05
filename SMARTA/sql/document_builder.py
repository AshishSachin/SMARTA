import pandas as pd
from sqlalchemy import create_engine

# Database Connection
engine = create_engine(
    "mysql+pymysql://root:raghul*99@localhost/smarta"
)

def get_sql_documents():

    df = pd.read_sql(
        "SELECT * FROM maintenance_logs",
        engine
    )

    documents = []

    for _, row in df.iterrows():

        text = f"""
Machine: {row['machine']}

Fault: {row['fault']}

Cause: {row['cause']}

Action Taken: {row['action_taken']}

Engineer Notes: {row['engineer_notes']}
"""

        documents.append({
            "text": text,
            "metadata": {
                "machine": row["machine"],
                "fault": row["fault"],
                "source": "sql"
            }
        })

    return documents


# Test
if __name__ == "__main__":

    docs = get_sql_documents()

    print(docs[0])
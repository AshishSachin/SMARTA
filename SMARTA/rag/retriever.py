import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import faiss
import pickle
from sentence_transformers import SentenceTransformer

print("Loading Documents...")
with open("vectorstore/documents.pkl", "rb") as f:
    documents = pickle.load(f)

print("Loading FAISS Index...")
index = faiss.read_index("vectorstore/index.faiss")

print("Loading Embedding Model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

print("Retriever Ready")


def retrieve(query, k=4):

    query_embedding = model.encode([query])
    query_embedding = query_embedding.astype("float32")

    distances, ids = index.search(query_embedding, k)

    results = []

    for idx in ids[0]:
        results.append(documents[idx]["text"])

    return results
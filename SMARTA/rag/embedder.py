import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from document_loader import get_documents


documents = get_documents()

from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

all_texts = [doc["text"] for doc in documents]

embeddings = model.encode(all_texts)

print(embeddings.shape)

import numpy as np
from pathlib import Path

data_dir = (
    Path(__file__).resolve().parent.parent
    / "data"
)

data_dir.mkdir(exist_ok=True)

np.save(
    data_dir / "embeddings.npy",
    embeddings
)
print("Embeddings Saved!")
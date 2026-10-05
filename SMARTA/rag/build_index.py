import sys
from pathlib import Path
import pickle

sys.path.append(str(Path(__file__).resolve().parent.parent))

from document_loader import get_documents

documents = get_documents()

print(f"Loaded {len(documents)} documents")

vectorstore_dir = (
Path(__file__).resolve().parent.parent
/ "vectorstore"
)

vectorstore_dir.mkdir(exist_ok=True)

with open(
vectorstore_dir / "documents.pkl",
"wb"
) as f:
    pickle.dump(documents, f)

print("Documents Saved!")

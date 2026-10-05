import faiss
import numpy as np

# Load embeddings
embeddings = np.load("data/embeddings.npy")

print("Embeddings Loaded:")
print(embeddings.shape)

# Convert to float32
embeddings = embeddings.astype("float32")

# Get vector dimension
dimension = embeddings.shape[1]

# Create index
index = faiss.IndexFlatL2(dimension)

# Add vectors
index.add(embeddings)

print("Vectors Indexed:")
print(index.ntotal)

# Save index
faiss.write_index(
    index,
    "vectorstore/index.faiss"
)

print("FAISS Index Saved!")
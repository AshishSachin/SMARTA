from document_builder import get_documents

print("START")

docs = get_documents()

print("DOCUMENT COUNT:", len(docs))
print(docs[0])
from pypdf import PdfReader
import os

def chunk_text(text, chunk_size=500):

    chunks = []

    for i in range(0, len(text), chunk_size):

        chunk = text[i:i + chunk_size]

        chunks.append(chunk)

    return chunks

def load_pdfs(pdf_folder):

    documents = []

    for filename in os.listdir(pdf_folder):

        if filename.endswith(".pdf"):

            file_path = os.path.join(pdf_folder, filename)

            reader = PdfReader(file_path)

            full_text = ""

            for page in reader.pages:

                text = page.extract_text()

                if text:
                    full_text += text + "\n"

            chunks = chunk_text(full_text)

            for chunk in chunks:
                documents.append({
                    "source": filename,
                    "text": chunk
                })

    return documents

"""if __name__ == "__main__":

    docs = load_pdfs("data/pdfs")

    print(f"Chunks loaded: {len(docs)}")

    print("\nFirst chunk:\n")

    print(docs[0]["text"])

    print(docs[0]["source"])
print(len(docs[0]["text"]))"""
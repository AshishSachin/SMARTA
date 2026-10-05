from sql.document_builder import get_sql_documents
from excel.excel_loader import get_excel_documents
from pdf.pdf_loader import load_pdfs

def get_documents():

    sql_docs = get_sql_documents()

    excel_docs = get_excel_documents()

    pdf_docs = load_pdfs("data/pdfs")

    return sql_docs + excel_docs + pdf_docs


if __name__ == "__main__":

    docs = get_documents()

    print(f"Total Documents: {len(docs)}")
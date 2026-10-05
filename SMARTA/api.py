"""
SMARTA API server
------------------
Wraps the existing RAG pipeline (rag/retriever.py + rag/generator.py) in a
small FastAPI app so that a frontend (e.g. the Flutter chat app in
flutter_app/) can talk to SMARTA over HTTP instead of the terminal.

Run it with:
    pip install -r requirements.txt
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload

Then POST to /chat:
    curl -X POST http://localhost:8000/chat \
         -H "Content-Type: application/json" \
         -d '{"question": "Why is the compressor tripping alarm A12?"}'
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag.retriever import retrieve
from rag.generator import generate_answer

app = FastAPI(title="SMARTA API", version="1.0.0")

# Allow the Flutter app (web, mobile, desktop) to call this API from anywhere.
# Lock this down to specific origins if you deploy this publicly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str


@app.get("/health")
def health():
    """Simple liveness check the Flutter app can ping on startup."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        results = retrieve(question)
        context = "\n\n".join(results)
        answer = generate_answer(context=context, question=question)
    except Exception as exc:  # surface a readable error to the frontend
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(answer=answer)

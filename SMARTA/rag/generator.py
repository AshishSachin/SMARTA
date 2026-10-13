"""Grounded answer generation for SMARTA maintenance questions."""

from ollama import chat


def generate_answer(context: str, question: str) -> str:
    if not context.strip():
        return (
            "I couldn't find a matching record in the connected maintenance files. "
            "Please add the relevant machine manual, alarm list, or maintenance log and refresh the corpus."
        )

    prompt = f"""You are SMARTA, a maintenance assistant. Use only the source excerpts below.

Rules:
- Do not infer a machine-specific fault, alarm mapping, or cause that the excerpts do not state.
- If the exact alarm/code is absent, say that clearly. You may then give relevant general guidance, labeled as general, with its source citation.
- For a fault question, use Diagnosis, Evidence, and Recommended checks. Distinguish recorded facts from possibilities.
- Cite factual statements inline using only the numbered source labels shown, such as [1] or [2]. Never invent a filename, page number, or source label.
- If there is no relevant evidence, say so and ask for the machine make/model or missing record.

Source excerpts:
{context}

Question: {question}
"""
    response = chat(
        model="qwen2.5:3b",
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"].strip()

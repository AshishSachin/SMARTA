from ollama import chat


def generate_answer(context, question):

    prompt = f"""
You are SMARTA, an AI assistant for industrial manufacturing and maintenance.

Rules:

1. Answer ONLY using the provided context.
2. Never invent information.
3. If the answer is not present in the context, reply:
"I could not find that information in the available records."
4. If multiple documents mention the same issue, combine the information into one answer.

Formatting:

If the question is about:
- machine faults
- alarms
- failures
- troubleshooting
- maintenance

respond in this format:

Diagnosis:
Likely Cause:
Recommended Action:

Otherwise, answer naturally using bullet points or paragraphs.

Context:
{context}

Question:
{question}
"""

    response = chat(
        model="qwen2.5:3b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"]
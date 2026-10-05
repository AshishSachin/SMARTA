from ollama import chat

response = chat(
    model="qwen2.5:3b",
    messages=[
        {
            "role": "user",
            "content": "What is a cooling fan?"
        }
    ]
)

print(response["message"]["content"])
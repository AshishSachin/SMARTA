from rag.retriever import retrieve
from rag.generator import generate_answer


def main():

    while True:

        question = input("\nAsk a question: ")

        if question.lower() in ["exit", "quit"]:
            print("Exiting SMARTA...")
            break

        results = retrieve(question)

        context = "\n\n".join(results)

        answer = generate_answer(
            context=context,
            question=question
        )

        print("\nSMARTA Answer:\n")
        print(answer)


if __name__ == "__main__":
    main()
import os
import re

from dotenv import load_dotenv

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)


# ============================================================
# SOURCE DOCUMENT
# ============================================================

text = """
Customers can cancel their insurance policy within 14 days of purchase.

Customers should contact the bank immediately if their banking credentials are exposed.

The bank may temporarily hold a suspicious transaction while verification is completed.

Complaints can be raised through customer support, online banking, or a branch.

The bank aims to provide a final response to standard complaints within 15 business days.
"""


document = Document(
    page_content=text,
    metadata={
        "document_id": "POLICY-001",
        "document_name": "Customer Banking Policy",
        "document_type": "policy",
        "department": "customer_service",
        "version": "1.0",
        "region": "UK"
    }
)


# ============================================================
# CHUNKING
# ============================================================

splitter = RecursiveCharacterTextSplitter(
    chunk_size=200,
    chunk_overlap=20
)

chunks = splitter.split_documents(
    [document]
)


for index, chunk in enumerate(
        chunks,
        start=1
):

    chunk.metadata["chunk_id"] = (
        f"POLICY-001-CHUNK-{index:03d}"
    )


print(
    f"Created {len(chunks)} chunks"
)


# ============================================================
# EMBEDDINGS
# ============================================================

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


# ============================================================
# VECTOR DATABASE
# ============================================================

vectorstore = FAISS.from_documents(
    chunks,
    embeddings
)


print("Vector store created")


# ============================================================
# LLM
# ============================================================

llm = ChatGroq(
    model=GROQ_MODEL,
    temperature=0
)


# ============================================================
# RAG PIPELINE
# ============================================================

def rag_pipeline(question):

    print("\n")
    print("=" * 70)
    print("RETRIEVAL")
    print("=" * 70)


    retrieved_docs = vectorstore.similarity_search(
        question,
        k=2
    )


    for rank, doc in enumerate(
            retrieved_docs,
            start=1
    ):

        print(
            f"\nRank {rank}"
        )

        print(
            "Chunk:",
            doc.metadata["chunk_id"]
        )

        print(
            doc.page_content
        )


    context = "\n".join(
        doc.page_content
        for doc in retrieved_docs
    )


    prompt = f"""

Answer the question using ONLY the information below.

If the answer is not available,
say exactly:

I could not find that information.

Do not guess.

Information:

{context}


Question:

{question}

"""


    response = llm.invoke(
        prompt
    )


    answer = response.content


    print("\n")
    print("=" * 70)
    print("GENERATED ANSWER")
    print("=" * 70)

    print(answer)


    return answer, retrieved_docs



# ============================================================
# NORMALIZATION
# ============================================================

def clean_text(text):

    text = text.lower()

    # remove markdown
    text = re.sub(
        r"\*+",
        "",
        text
    )

    # remove punctuation

    text = re.sub(
        r"[.,!?]",
        "",
        text
    )

    return text.strip()



# ============================================================
# ANSWER CORRECTNESS
# ============================================================

def evaluate_answer(
        actual,
        expected,
        answerable
):

    actual = clean_text(actual)

    expected = clean_text(expected)


    if answerable:

        return expected in actual


    else:

        return (
            "i could not find that information"
            in actual
        )

# ============================================================
# RETRIEVAL QUALITY EVALUATION
# ============================================================

def evaluate_retrieval(
        question,
        retrieved_docs
):

    """
    Checks whether retrieved chunks are
    semantically relevant to the question.

    We use the same embedding model
    used by RAG.

    Question -> Vector
    Chunk -> Vector

    Then compare similarity.
    """

    question_embedding = embeddings.embed_query(
        question
    )


    chunk_texts = [
        doc.page_content
        for doc in retrieved_docs
    ]


    chunk_embeddings = embeddings.embed_documents(
        chunk_texts
    )


    similarities = []


    for chunk_embedding in chunk_embeddings:

        score = sum(
            q * c
            for q, c in zip(
                question_embedding,
                chunk_embedding
            )
        )

        similarities.append(score)


    highest_score = max(
        similarities
    )


    print(
        f"\nSemantic Retrieval Score: {highest_score:.3f}"
    )


    # Threshold chosen only for demo purposes

    return highest_score >= 0.40



# ============================================================
# FAITHFULNESS EVALUATION
# ============================================================

def evaluate_faithfulness(
        answer,
        retrieved_docs,
        answerable
):

    """
    Checks whether generated answer
    is supported by retrieved context.
    """


    if not answerable:

        # For unanswered questions,
        # faithfulness is not applicable.

        return "N/A"


    answer = clean_text(
        answer
    )


    context = clean_text(
        " ".join(
            doc.page_content
            for doc in retrieved_docs
        )
    )


    # Extract important words

    answer_words = set(
        answer.split()
    )


    context_words = set(
        context.split()
    )


    overlap = (
        answer_words.intersection(
            context_words
        )
    )


    if len(answer_words) == 0:

        return False


    ratio = (
        len(overlap)
        /
        len(answer_words)
    )


    print(
        f"Faithfulness overlap score: {ratio:.2f}"
    )


    return ratio >= 0.50



# ============================================================
# COMPLETE TEST CASE EVALUATION
# ============================================================

def evaluate_test_case(
        test_case
):


    question = test_case["question"]

    expected_answer = test_case["expected_answer"]

    answerable = test_case["answerable"]



    print("\n")
    print("#" * 70)
    print("TEST CASE")
    print("#" * 70)


    print("\nQuestion:")
    print(question)



    print("\nExpected:")
    print(expected_answer)



    # Run RAG

    answer, retrieved_docs = rag_pipeline(
        question
    )



    print("\n")
    print("-" * 70)
    print("EVALUATION")
    print("-" * 70)



    # ------------------------------------------
    # 1. Answer correctness
    # ------------------------------------------

    answer_score = evaluate_answer(
        answer,
        expected_answer,
        answerable
    )


    # ------------------------------------------
    # 2. Faithfulness
    # ------------------------------------------

    faithfulness_score = evaluate_faithfulness(
        answer,
        retrieved_docs,
        answerable
    )


    # ------------------------------------------
    # 3. Retrieval relevance
    # ------------------------------------------

    retrieval_score = evaluate_retrieval(
        question,
        retrieved_docs
    )


    print("\nResults")
    print("-" * 50)


    print(
        "Answer Correctness :",
        "PASS" if answer_score else "FAIL"
    )


    print(
        "Faithfulness       :",
        faithfulness_score
        if faithfulness_score == "N/A"
        else
        (
            "PASS"
            if faithfulness_score
            else
            "FAIL"
        )
    )


    print(
        "Retrieval Quality  :",
        "PASS"
        if retrieval_score
        else
        "FAIL"
    )


    return {

        "answer_correct":
            answer_score,

        "faithfulness":
            faithfulness_score,

        "retrieval":
            retrieval_score
    }





# ============================================================
# EVALUATION DATASET
# ============================================================


evaluation_dataset = [

    {

        "question":
            "How long does the bank take to respond to a complaint?",


        "expected_answer":
            "The bank aims to provide a final response to standard complaints within 15 business days.",


        "answerable":
            True
    },


    {

        "question":
            "What should customers do if their banking credentials are exposed?",


        "expected_answer":
            "Customers should contact the bank immediately.",


        "answerable":
            True
    },


    {

        "question":
            "What is the savings account interest rate?",


        "expected_answer":
            "I could not find that information.",


        "answerable":
            False
    }

]



# ============================================================
# RUN COMPLETE EVALUATION
# ============================================================


def run_evaluation():


    print("\n")
    print("=" * 70)
    print("RAG EVALUATION STARTED")
    print("=" * 70)



    results = []


    for test_case in evaluation_dataset:


        result = evaluate_test_case(
            test_case
        )


        results.append(
            result
        )



    print("\n")
    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)



    total = len(results)



    answer_pass = sum(
        1
        for r in results
        if r["answer_correct"]
    )



    faithfulness_pass = sum(
        1
        for r in results
        if r["faithfulness"] is True
    )



    retrieval_pass = sum(
        1
        for r in results
        if r["retrieval"]
    )



    print()

    print(
        f"Answer Correctness : "
        f"{answer_pass}/{total}"
    )


    print(
        f"Faithfulness       : "
        f"{faithfulness_pass}/{total}"
    )


    print(
        f"Retrieval Quality  : "
        f"{retrieval_pass}/{total}"
    )



# ============================================================
# INTERACTIVE CHAT
# ============================================================


def chat_mode():


    print("\n")
    print("=" * 70)
    print("RAG CHAT")
    print("=" * 70)


    while True:


        question = input(
            "\nAsk question (exit to stop): "
        )


        if question.lower() == "exit":

            break



        rag_pipeline(
            question
        )



# ============================================================
# MAIN MENU
# ============================================================


def main():


    while True:


        print("\n")
        print("=" * 70)
        print("RAG + LIGHTWEIGHT EVALUATION")
        print("=" * 70)


        print(
"""
1. Chat with RAG
2. Evaluate RAG
3. Exit
"""
        )


        choice = input(
            "Choose option: "
        )



        if choice == "1":

            chat_mode()



        elif choice == "2":

            run_evaluation()



        elif choice == "3":

            print(
                "Exiting..."
            )

            break



        else:

            print(
                "Invalid option"
            )



if __name__ == "__main__":

    main()

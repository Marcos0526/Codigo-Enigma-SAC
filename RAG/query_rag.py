import os
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

def query_rag(query_text, persist_directory='nasa_vector_db'):
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vector_db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
    
    # Retrieve top 3 relevant chunks
    docs = vector_db.similarity_search(query_text, k=3)
    
    print(f"\nQuery: {query_text}\n")
    print("--- Retrieved Context & Sources ---")
    for i, doc in enumerate(docs):
        source = doc.metadata.get('source', 'Unknown')
        page = doc.metadata.get('page', 'Unknown')
        print(f"\n[Match {i+1}] Source: {source}, Page: {page}")
        print(f"Content excerpt: {doc.page_content[:300]}...")

if __name__ == "__main__":
    query_rag("What are the combustion behaviors?")

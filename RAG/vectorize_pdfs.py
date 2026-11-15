import os
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

def process_pdfs(pdf_folder, persist_directory):
    # Setup embedding model (small model to save space/memory)
    # Using a model that is often available in generic environments
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    vector_db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
    
    pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith('.pdf')]
    
    for pdf_file in pdf_files:
        file_path = os.path.join(pdf_folder, pdf_file)
        print(f"Processing: {pdf_file}")
        
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        
        # Simple split
        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = text_splitter.split_documents(documents)
        
        # Add source metadata
        for chunk in chunks:
            chunk.metadata['source'] = pdf_file
        
        vector_db.add_documents(chunks)
        
    print("Vectorization complete.")

if __name__ == "__main__":
    process_pdfs('pdfs_NASA', 'nasa_vector_db')

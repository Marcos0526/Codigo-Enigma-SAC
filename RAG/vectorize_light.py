import os
import pypdf
import chromadb
from sentence_transformers import SentenceTransformer

def process_and_vectorize():
    pdf_folder = "pdfs_NASA"
    persist_dir = "nasa_vector_db"
    
    print("Loading embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    print("Initializing ChromaDB client...")
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection(name="nasa_docs")
    
    pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith('.pdf')]
    
    for pdf_file in pdf_files:
        file_path = os.path.join(pdf_folder, pdf_file)
        print(f"Processing PDF: {pdf_file}")
        
        reader = pypdf.PdfReader(file_path)
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text or not text.strip():
                continue
            
            # Simple chunking by paragraph or character size (e.g., 1000 chars)
            chunk_size = 1000
            for i in range(0, len(text), chunk_size):
                chunk_text = text[i:i + chunk_size]
                chunk_id = f"{pdf_file}_p{page_num+1}_c{i}"
                
                # Compute embedding
                embedding = model.encode(chunk_text).tolist()
                
                # Add to collection with metadata for citations
                collection.upsert(
                    ids=[chunk_id],
                    embeddings=[embedding],
                    documents=[chunk_text],
                    metadatas=[{"source": pdf_file, "page": page_num + 1}]
                )
                
    print("Vectorization completed successfully!")

if __name__ == "__main__":
    process_and_vectorize()

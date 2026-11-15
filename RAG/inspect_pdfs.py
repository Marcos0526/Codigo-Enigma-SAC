import os
from pypdf import PdfReader

PDF_DIR = "pdfs_NASA"

def inspect_pdfs():
    print(f"Inspecting directory: {PDF_DIR}")
    if not os.path.exists(PDF_DIR):
        print("Directory does not exist!")
        return

    files = [f for f in os.listdir(PDF_DIR) if f.endswith(".pdf")]
    print(f"Found {len(files)} PDF files.\n")

    for file in files:
        path = os.path.join(PDF_DIR, file)
        try:
            reader = PdfReader(path)
            num_pages = len(reader.pages)
            print(f"- {file}: {num_pages} pages")
            
            # Let's check text on page 1
            sample_text = reader.pages[0].extract_text()
            has_text = len(sample_text.strip()) > 50
            print(f"  Page 1 has text: {has_text} (sample: {sample_text[:100].strip()}...)")
        except Exception as e:
            print(f"- {file}: Error reading PDF: {e}")

if __name__ == "__main__":
    inspect_pdfs()

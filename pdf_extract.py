import fitz  # PyMuPDF

def extract_pdf_content(file_path):
    doc = fitz.open(file_path)
    html = ''
    for page in doc:
        text = page.get_text('html')
        html += text
    return html

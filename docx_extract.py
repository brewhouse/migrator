import docx
from bs4 import BeautifulSoup

def extract_docx_content(file_path):
    doc = docx.Document(file_path)
    html = ''
    for para in doc.paragraphs:
        html += f'<p>{para.text}</p>'
    # Optionally handle images, tables, etc. here
    return html

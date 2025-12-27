import pypdf
import pdfplumber
import docx

def extract_text(filepath):
    """
    Extracts text from PDF or DOCX file.
    """
    text = ""
    ext = filepath.rsplit('.', 1)[1].lower()
    
    try:
        if ext == 'pdf':
            print(f"DEBUG: Extracting PDF with pypdf: {filepath}")
            reader = pypdf.PdfReader(filepath)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            
            if not text.strip():
                print(f"DEBUG: pypdf failed, trying pdfplumber: {filepath}")
                with pdfplumber.open(filepath) as pdf:
                    for page in pdf.pages:
                        extracted = page.extract_text()
                        if extracted:
                            text += extracted + "\n"
        elif ext == 'docx':
            print(f"DEBUG: Extracting DOCX: {filepath}")
            doc = docx.Document(filepath)
            for para in doc.paragraphs:
                text += para.text + "\n"
    except Exception as e:
        print(f"DEBUG: Error extracting text from {filepath}: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    extracted_text = text.strip()
    print(f"DEBUG: Extraction complete. Chars: {len(extracted_text)}")
    return extracted_text

def generate_filename(subject_name, department, enrollment_id):
    """
    Generates the exact filename: <subjectName>_<department>_<enrollmentId>.pdf
    """
    # Sanitize inputs to prevent path traversal or nasty chars
    s_name = subject_name or "Unknown"
    s_dept = department or "Unknown"
    s_id = enrollment_id or "Unknown"
    
    safe_subject = "".join([c for c in s_name if c.isalnum() or c in (' ', '_')]).replace(' ', '_')
    safe_dept = "".join([c for c in s_dept if c.isalnum() or c in (' ', '_')]).replace(' ', '_')
    safe_id = "".join([c for c in s_id if c.isalnum() or c in (' ', '_')]).replace(' ', '_')
    
    return f"{safe_subject}_{safe_dept}_{safe_id}.pdf"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf', 'docx'}

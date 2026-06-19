import fitz  # PyMuPDF
from docx import Document
import io

def process_docx(file_bytes: bytes, active_entities: list[str], detect_fn) -> tuple[bytes, list]:
    doc = Document(io.BytesIO(file_bytes))
    report = []
    
    for para in doc.paragraphs:
        if not para.text.strip():
            continue
        res = detect_fn(para.text, active_entities)
        if res["found"]:
            para.text = res["redacted"]
            report.append({
                "text": "DOCX Paragraph",
                "pii_types": res["types"]
            })
            
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    res = detect_fn(cell.text, active_entities)
                    if res["found"]:
                        cell.text = res["redacted"]
                        report.append({
                            "text": "DOCX Table Cell",
                            "pii_types": res["types"]
                        })

    out_io = io.BytesIO()
    doc.save(out_io)
    return out_io.getvalue(), report


def process_pdf(file_bytes: bytes, active_entities: list[str], detect_raw_fn) -> tuple[bytes, list]:
    """
    Process native text PDFs using PyMuPDF redactions.
    detect_raw_fn should be a function that returns Presidio analyzer results (so we have start/end chars).
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    report = []

    for page in doc:
        text = page.get_text()
        if not text.strip():
            continue
            
        results = detect_raw_fn(text, active_entities)
        if not results:
            continue
            
        found_types = set()
        for res in results:
            found_types.add(res.entity_type)
            # Get the exact substring that was flagged
            substring = text[res.start:res.end]
            
            # Find it on the page
            quads = page.search_for(substring)
            for quad in quads:
                page.add_redact_annot(quad, fill=(0,0,0))
                
        if found_types:
            report.append({
                "text": "PDF Page Content",
                "pii_types": list(found_types)
            })
            page.apply_redactions()
            
    out_io = io.BytesIO()
    doc.save(out_io)
    return out_io.getvalue(), report

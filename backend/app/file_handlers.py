import fitz  # PyMuPDF
from docx import Document
import io

def process_docx(file_bytes: bytes, active_entities: list[str], detect_fn, masking_style: str = "LABEL", custom_patterns: list = None) -> tuple[bytes, list]:
    doc = Document(io.BytesIO(file_bytes))
    report = []
    
    for para in doc.paragraphs:
        if not para.text.strip():
            continue
        res = detect_fn(para.text, active_entities, masking_style, custom_patterns)
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
                    res = detect_fn(cell.text, active_entities, masking_style, custom_patterns)
                    if res["found"]:
                        cell.text = res["redacted"]
                        report.append({
                            "text": "DOCX Table Cell",
                            "pii_types": res["types"]
                        })

    out_io = io.BytesIO()
    doc.save(out_io)
    return out_io.getvalue(), report


def process_pdf(file_bytes: bytes, active_entities: list[str], detect_raw_fn, custom_patterns: list = None) -> tuple[bytes, list]:
    """
    Process native text PDFs using PyMuPDF redactions.
    detect_raw_fn should be a function that returns Presidio analyzer results (so we have start/end chars).
    """
    report = []
    out_io = io.BytesIO()
    
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            text = page.get_text()
            if not text.strip():
                continue
                
            results = detect_raw_fn(text, active_entities, custom_patterns)
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
                
        doc.save(out_io)
        
    return out_io.getvalue(), report

def mask_pii_in_image_gcp(image_bytes: bytes, active_entities: list[str], detect_raw_fn, custom_patterns: list = None):
    import cv2
    import numpy as np
    from google.cloud import vision
    import re
    
    # 1. OCR with Google Cloud Vision
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    
    if response.error.message:
        raise Exception(f"GCP Vision API Error: {response.error.message}")
        
    if not texts:
        return image_bytes, []

    # Decode image using OpenCV for drawing
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    masked = img.copy()
    report = []
    
    # The first element is the full document text
    full_text = texts[0].description
    
    # 2. Run Presidio on the full context block
    detection_results = detect_raw_fn(full_text, active_entities, custom_patterns)
    
    if not detection_results:
        return image_bytes, []
        
    # 3. Extract words that need to be redacted based on full context
    flagged_words = set()
    found_types = set()
    for res in detection_results:
        pii_string = full_text[res.start:res.end]
        found_types.add(res.entity_type)
        words = re.findall(r'\w+', pii_string)
        flagged_words.update(w.lower() for w in words if len(w) > 1)
        
    # 4. Redact individual Vision bounding boxes if their word matches a flagged word
    for text_annotation in texts[1:]:
        word = text_annotation.description
        clean_word = re.sub(r'\W+', '', word).lower()
        
        if clean_word and clean_word in flagged_words:
            vertices = text_annotation.bounding_poly.vertices
            top_left = (vertices[0].x, vertices[0].y)
            bottom_right = (vertices[2].x, vertices[2].y)
            
            cv2.rectangle(masked, top_left, bottom_right, (0, 0, 0), -1)
            report.append({
                "text": word,
                "pii_types": list(found_types)
            })
            
    success, buffer = cv2.imencode('.jpg', masked, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return buffer.tobytes(), report

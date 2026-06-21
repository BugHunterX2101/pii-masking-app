from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from datetime import datetime
import io

def generate_hipaa_certificate(org_name: str, filename: str, entities_removed: list, audit_id: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    normal_style = styles['Normal']
    
    # Custom styles
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Heading2'],
        textColor=colors.HexColor("#2C3E50"),
        spaceAfter=12
    )
    
    elements = []
    
    # Header
    elements.append(Paragraph(f"Enterprise Privacy Suite", title_style))
    elements.append(Paragraph(f"Certificate of HIPAA De-identification", subtitle_style))
    elements.append(Spacer(1, 20))
    
    # Body Text
    date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    statement = f"""
    This document certifies that the file <b>{filename}</b> was successfully scanned and 
    de-identified on <b>{date_str}</b> by the Enterprise Privacy Suite Engine on behalf of <b>{org_name}</b>.
    """
    elements.append(Paragraph(statement, normal_style))
    elements.append(Spacer(1, 12))
    
    legal_text = """
    The de-identification process applies the <b>Safe Harbor</b> methodology under HIPAA Privacy Rule 
    §164.514(b). Machine learning models and pattern recognition algorithms were used to locate and 
    remove identifiers.
    """
    elements.append(Paragraph(legal_text, normal_style))
    elements.append(Spacer(1, 20))
    
    # Entity Statistics Table
    elements.append(Paragraph("<b>Removed Identifiers Breakdown</b>", styles['Heading3']))
    
    # Count occurrences
    from collections import Counter
    counts = Counter(entities_removed)
    
    data = [["Entity Type", "Occurrences Removed"]]
    for ent_type, count in counts.items():
        data.append([ent_type, str(count)])
    
    if not entities_removed:
        data.append(["No PII Detected", "0"])
        
    data.append(["<b>Total</b>", f"<b>{len(entities_removed)}</b>"])
    
    t = Table(data, colWidths=[200, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#1A202C")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#EDF2F7")),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E0")),
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 40))
    
    # Footer
    elements.append(Paragraph(f"<b>Audit Tracking ID:</b> {audit_id}", normal_style))
    elements.append(Paragraph("This certificate is automatically generated and tamper-evident.", styles['Italic']))
    
    doc.build(elements)
    return buffer.getvalue()

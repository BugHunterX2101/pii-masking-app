"""
PII Masking API — FastAPI backend
Enterprise Phase 2: Auth0 SSO, AWS S3, Google Cloud Vision OCR
"""
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status, Request
from fastapi.responses import Response, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import os
import json
import io
import uuid
from pydantic import BaseModel
import boto3
from botocore.exceptions import NoCredentialsError

from backend.app import models, database, auth, pii_engine, file_handlers
from backend.app.database import engine, get_db

try:
    models.Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Database sync warning (safe if concurrent init): {e}")

app = FastAPI(title="Enterprise Privacy Suite", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-PII-Report", "X-PII-Count"],
)

# -------------------------------------------------------------------
# Environment & Cloud Config
# -------------------------------------------------------------------
AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "pii-mask-ocr-files")

s3_client = boto3.client('s3', region_name=AWS_REGION)

# Point GCP SDK to our JSON file credentials
gcp_creds = os.getenv("GCP_CREDENTIALS_JSON")
if gcp_creds:
    with open("/tmp/gcp.json", "w") as f:
        f.write(gcp_creds)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/gcp.json"


# -------------------------------------------------------------------
# Auth0 Integration
# -------------------------------------------------------------------
# We still use OAuth2PasswordBearer to extract the token from the header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="none")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = auth.verify_auth0_token(token)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token: missing sub claim")
        
    user = db.query(models.User).filter(models.User.username == sub).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not synced. Please call /api/auth/sync first.")
    return user

def require_admin(current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user

# -------------------------------------------------------------------
# Helper: Get active policies & Logging
# -------------------------------------------------------------------
def get_active_entities(db: Session):
    policies = db.query(models.DLPPolicy).filter(models.DLPPolicy.is_active == True).all()
    if not policies:
        default = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "AADHAAR", "PAN_CARD"]
        for p in default:
            db.add(models.DLPPolicy(pii_type=p, is_active=True))
        db.commit()
        active_entities = default
    else:
        active_entities = [p.pii_type for p in policies]
        
    settings = db.query(models.SystemSettings).first()
    masking_style = settings.masking_style if settings else "LABEL"
    
    custom = db.query(models.CustomRegexPolicy).filter(models.CustomRegexPolicy.is_active == True).all()
    custom_patterns = [{"name": c.name, "pattern": c.pattern} for c in custom]
    
    return active_entities, masking_style, custom_patterns

def log_audit(db: Session, user_id: int, action: str, ip: str, details: dict):
    log = models.AuditLog(
        user_id=user_id,
        action=action,
        ip_address=ip,
        details=details
    )
    db.add(log)
    db.commit()
# -------------------------------------------------------------------
# S3 Upload Helper
# -------------------------------------------------------------------
def upload_raw_to_s3(file_bytes: bytes, filename: str, content_type: str) -> str:
    s3_key = f"raw_{uuid.uuid4().hex}_{filename}"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=file_bytes,
        ContentType=content_type
    )
    return s3_key

def upload_to_s3_and_get_url(file_bytes: bytes, filename: str, content_type: str) -> str:
    try:
        s3_key = f"masked_{uuid.uuid4().hex}_{filename}"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type,
            # We don't set ACL='public-read' to keep it secure
        )
        # Generate presigned URL
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': s3_key},
            ExpiresIn=3600 # 1 hour
        )
        return url
    except Exception as e:
        print("S3 Upload Error:", e)
        # Fallback to base64 data URI if S3 fails (for robust local dev without keys)
        import base64
        b64 = base64.b64encode(file_bytes).decode('utf-8')
        return f"data:{content_type};base64,{b64}"

# -------------------------------------------------------------------
# Auth0 Sync Route
# -------------------------------------------------------------------
@app.post("/api/auth/sync")
def sync_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db), request: Request = None):
    """Called by frontend right after Auth0 login to sync the user to our Postgres DB."""
    payload = auth.verify_auth0_token(token)
    sub = payload.get("sub")
    
    user = db.query(models.User).filter(models.User.username == sub).first()
    if not user:
        is_first = db.query(models.User).count() == 0
        role = "admin" if is_first else "user"
        # We store Auth0 'sub' in username field. Hashed password is N/A for SSO.
        user = models.User(username=sub, hashed_password="SSO", role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        
    ip = request.client.host if request and request.client else "N/A"
    log_audit(db, user.id, "LOGIN", ip, {"provider": "Auth0"})
    
    return {"status": "synced", "role": user.role, "user_id": user.id}

# -------------------------------------------------------------------
# Admin Endpoints
# -------------------------------------------------------------------
@app.get("/api/admin/users")
def get_users(db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    users = db.query(models.User).order_by(models.User.id.asc()).all()
    return [{"id": u.id, "username": u.username, "role": u.role} for u in users]

class UserRoleUpdate(BaseModel):
    role: str

@app.put("/api/admin/users/{user_id}/role")
def update_user_role(user_id: int, update: UserRoleUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    if update.role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Invalid role specified")
        
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if target_user.id == current_user.id and update.role != "admin":
        raise HTTPException(status_code=400, detail="Admins cannot demote themselves")
        
    old_role = target_user.role
    target_user.role = update.role
    
    # Audit log
    log_audit(db, current_user.id, "UPDATE_USER_ROLE", "N/A", {
        "target_user_id": target_user.id,
        "old_role": old_role,
        "new_role": update.role
    })
    
    db.commit()
    return {"msg": f"User {target_user.username} role updated to {update.role}"}

@app.get("/api/admin/logs")
def get_audit_logs(db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    logs = db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).limit(100).all()
    return [{
        "id": l.id,
        "user_id": l.user.username if l.user else l.user_id, # return auth0 sub
        "action": l.action,
        "timestamp": l.timestamp,
        "ip_address": l.ip_address,
        "details": l.details
    } for l in logs]

@app.get("/api/admin/policies")
def get_policies(db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    return db.query(models.DLPPolicy).all()

class PolicyUpdate(BaseModel):
    pii_type: str
    is_active: bool

@app.post("/api/admin/policies")
def update_policy(update: PolicyUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    policy = db.query(models.DLPPolicy).filter(models.DLPPolicy.pii_type == update.pii_type).first()
    if policy:
        policy.is_active = update.is_active
    else:
        db.add(models.DLPPolicy(pii_type=update.pii_type, is_active=update.is_active))
    db.commit()
    return {"msg": "Policy updated"}

@app.get("/api/admin/settings")
def get_settings(db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    settings = db.query(models.SystemSettings).first()
    if not settings:
        settings = models.SystemSettings(masking_style="LABEL")
        db.add(settings)
        db.commit()
    return {"masking_style": settings.masking_style}

class SettingsUpdate(BaseModel):
    masking_style: str

@app.put("/api/admin/settings")
def update_settings(update: SettingsUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    settings = db.query(models.SystemSettings).first()
    if not settings:
        settings = models.SystemSettings(masking_style=update.masking_style)
        db.add(settings)
    else:
        settings.masking_style = update.masking_style
    db.commit()
    return {"msg": "Settings updated"}

@app.get("/api/admin/custom-regex")
def get_custom_regex(db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    patterns = db.query(models.CustomRegexPolicy).all()
    return [{"id": p.id, "name": p.name, "pattern": p.pattern, "is_active": p.is_active} for p in patterns]

class CustomRegexCreate(BaseModel):
    name: str
    pattern: str
    is_active: bool = True

@app.post("/api/admin/custom-regex")
def create_custom_regex(regex: CustomRegexCreate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    import re
    try:
        re.compile(regex.pattern)
    except re.error:
        raise HTTPException(status_code=400, detail="Invalid Regex pattern")
    
    new_regex = models.CustomRegexPolicy(name=regex.name.upper().replace(' ', '_'), pattern=regex.pattern, is_active=regex.is_active)
    db.add(new_regex)
    db.commit()
    return {"msg": "Regex added"}

@app.delete("/api/admin/custom-regex/{regex_id}")
def delete_custom_regex(regex_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    regex = db.query(models.CustomRegexPolicy).filter(models.CustomRegexPolicy.id == regex_id).first()
    if regex:
        db.delete(regex)
        db.commit()
    return {"msg": "Regex deleted"}

@app.get("/api/admin/logs/export")
def export_logs(db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    logs = db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp", "User ID", "Action", "IP Address", "Details"])
    
    for l in logs:
        writer.writerow([l.id, l.timestamp.isoformat(), l.user.username if l.user else l.user_id, l.action, l.ip_address, json.dumps(l.details) if l.details else ""])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"}
    )

@app.get("/api/admin/analytics")
def get_analytics(db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    logs = db.query(models.AuditLog).all()
    entity_counts = {}
    for l in logs:
        if l.details and "detected" in l.details:
            for ent in l.details["detected"]:
                entity_counts[ent] = entity_counts.get(ent, 0) + 1
                
    # Sort descending
    sorted_counts = [{"name": k, "count": v} for k, v in sorted(entity_counts.items(), key=lambda item: item[1], reverse=True)]
    return sorted_counts

# -------------------------------------------------------------------
# App API Routes (Protected)
# -------------------------------------------------------------------
@app.post("/api/upload")
async def upload_file(request: Request, file: UploadFile = File(...), current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    active_entities = get_active_entities(db)
    file_bytes = await file.read()
    
    ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
    
    try:
        # Determine media type based on extension
        if ext in ['pdf']:
            media_type = "application/pdf"
        elif ext in ['docx']:
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif ext in ['jpg', 'jpeg', 'png', 'webp']:
            media_type = "image/jpeg"
        elif ext in ['zip']:
            media_type = "application/zip"
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format.")

        # Upload raw file to S3 first
        s3_key = upload_raw_to_s3(file_bytes, file.filename, media_type)
        active_entities, masking_style, custom_patterns = get_active_entities(db)
    
        # 2. Dispatch task to Celery
        if ext == 'zip':
            from backend.app.worker import process_batch_task
            task = process_batch_task.delay(s3_key, active_entities, masking_style, custom_patterns)
        else:
            from backend.app.worker import process_document_task
            task = process_document_task.delay(s3_key, file.filename, media_type, active_entities, masking_style, custom_patterns)

        # Log audit for task initiation
        log_audit(db, current_user.id, "FILE_MASK_TASK_STARTED", request.client.host if request.client else "N/A", {
            "filename": file.filename,
            "task_id": task.id
        })

        return JSONResponse(status_code=202, content={
            "status": "accepted",
            "task_id": task.id,
            "message": "Document is being processed asynchronously."
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str, current_user: models.User = Depends(get_current_user)):
    from backend.app.worker import celery_app
    task_result = celery_app.AsyncResult(task_id)
    
    response = {
        "task_id": task_id,
        "status": task_result.status,
    }
    
    if task_result.status == 'SUCCESS':
        response["result"] = task_result.result
    elif task_result.status == 'FAILURE':
        response["error"] = str(task_result.info)
    elif task_result.status == 'PROCESSING':
        # Custom state updated via update_state
        response["message"] = task_result.info.get('status', 'Processing...') if isinstance(task_result.info, dict) else 'Processing...'

    return response

class TextMaskRequest(BaseModel):
    text: str

@app.post("/api/mask-text")
async def mask_text(request: Request, req: TextMaskRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    active_entities, masking_style, custom_patterns = get_active_entities(db)
    result = pii_engine.detect_and_mask_text(req.text, active_entities, masking_style, custom_patterns)
    
    if result["found"]:
        log_audit(db, current_user.id, "TEXT_MASK", request.client.host if request.client else "N/A", {
            "detected": result["types"]
        })
        
    return {
        "original": req.text,
        "masked": result["redacted"],
        "pii_found": result["found"],
        "pii_types": result["types"],
        "count": len(result["types"]),
    }

# -------------------------------------------------------------------
# Serve React static build
# -------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "frontend", "build"))

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
        
    if not os.path.isdir(STATIC_DIR):
        return JSONResponse({"info": "Frontend not built."}, status_code=200)
    if full_path:
        file_path = os.path.join(STATIC_DIR, full_path)
        real_path = os.path.realpath(file_path)
        if real_path.startswith(os.path.realpath(STATIC_DIR)) and os.path.isfile(real_path):
            return FileResponse(real_path)
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return JSONResponse({"error": "index.html not found"}, status_code=404)

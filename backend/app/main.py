"""
PII Masking API — FastAPI backend
Enterprise Phase 2: Auth0 SSO, AWS S3, Google Cloud Vision OCR
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, status, Request, Security
from fastapi.responses import Response, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session
import os
import json
import io
import uuid
import hashlib
from typing import Optional
from pydantic import BaseModel
import boto3
from botocore.exceptions import NoCredentialsError

from backend.app import models, database, auth, pii_engine, file_handlers
from backend.app.database import engine, get_db

try:
    models.Base.metadata.create_all(bind=engine)
    # Initialize Default Organization
    db = database.SessionLocal()
    try:
        default_org = db.query(models.Organization).filter(models.Organization.slug == "legacy-org").first()
        if not default_org:
            default_org = models.Organization(name="Legacy Org", slug="legacy-org", plan="enterprise")
            db.add(default_org)
            db.commit()
    finally:
        db.close()
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
DEFAULT_DLP_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "AADHAAR", "PAN_CARD"]

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
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header), db: Session = Depends(get_db)):
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API Key")
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    db_key = db.query(models.APIKey).filter(models.APIKey.key_hash == key_hash, models.APIKey.is_active == True).first()
    if not db_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
    return db_key

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = auth.verify_auth0_token(token)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token: missing sub claim")
        
    user = db.query(models.User).filter(models.User.username == sub).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not synced. Please call /api/auth/sync first.")
    if user.org_id is None:
        org = get_or_create_default_org(db)
        user.org_id = org.id
        db.commit()
        db.refresh(user)
    return user

def require_admin(current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user

# -------------------------------------------------------------------
# Helper: Get active policies & Logging
# -------------------------------------------------------------------
def get_or_create_default_org(db: Session):
    org = db.query(models.Organization).filter(models.Organization.slug == "legacy-org").first()
    if not org:
        org = models.Organization(name="Legacy Org", slug="legacy-org", plan="enterprise")
        db.add(org)
        db.commit()
        db.refresh(org)
    return org

def get_active_entities(db: Session, org_id: Optional[int] = None):
    # If org_id is provided, filter by it. Otherwise fallback (for legacy)
    query = db.query(models.DLPPolicy)
    if org_id is not None:
        query = query.filter(models.DLPPolicy.org_id == org_id)
        
    policies = query.filter(models.DLPPolicy.is_active == True).all()
    if not policies:
        for p in DEFAULT_DLP_ENTITIES:
            db.add(models.DLPPolicy(pii_type=p, is_active=True, org_id=org_id))
        db.commit()
        active_entities = DEFAULT_DLP_ENTITIES
    else:
        active_entities = [str(p.pii_type) for p in policies]
        
    settings_query = db.query(models.SystemSettings)
    if org_id is not None:
        settings_query = settings_query.filter(models.SystemSettings.org_id == org_id)
    settings = settings_query.first()
    masking_style = str(settings.masking_style) if settings else "LABEL"
    
    custom_query = db.query(models.CustomRegexPolicy)
    if org_id is not None:
        custom_query = custom_query.filter(models.CustomRegexPolicy.org_id == org_id)
    custom = custom_query.filter(models.CustomRegexPolicy.is_active == True).all()
    custom_patterns = [{"name": c.name, "pattern": c.pattern} for c in custom]
    
    return active_entities, masking_style, custom_patterns

def log_audit(db: Session, action: str, ip: str, details: dict, user_id: Optional[int] = None, org_id: Optional[int] = None, api_key_id: Optional[str] = None):
    log = models.AuditLog(
        user_id=user_id,
        org_id=org_id,
        api_key_id=api_key_id,
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
def sync_user(request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Called by frontend right after Auth0 login to sync the user to our Postgres DB."""
    payload = auth.verify_auth0_token(token)
    sub = payload.get("sub")

    # Debug: log every claim Auth0 sent so we can diagnose role issues
    print(f"[AUTH SYNC] sub={sub}")
    print(f"[AUTH SYNC] Full JWT payload keys: {list(payload.keys())}")
    print(f"[AUTH SYNC] email={payload.get('email', 'NOT PRESENT')}")
    print(f"[AUTH SYNC] name={payload.get('name', 'NOT PRESENT')}")
    print(f"[AUTH SYNC] nickname={payload.get('nickname', 'NOT PRESENT')}")

    user = db.query(models.User).filter(models.User.username == sub).first()

    # Check environment variable whitelist for admin promotion
    admin_emails = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "veditagrawal21@gmail.com,ceo@company.com").split(",") if e.strip()]

    # Collect ALL string values from the JWT payload — Auth0 can place email in
    # different claim names depending on the connection type and custom rules.
    all_claim_values = []
    for key, value in payload.items():
        if isinstance(value, str):
            all_claim_values.append(value.lower())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    all_claim_values.append(item.lower())

    user_email = payload.get("email", "").lower()

    is_admin = False

    # Check 1: Direct email match against whitelist
    if user_email and user_email in admin_emails:
        is_admin = True
        print(f"[AUTH SYNC] Admin granted via direct email match: {user_email}")

    # Check 2: Scan ALL claim values for admin email (catches non-standard claim names)
    if not is_admin:
        for admin_email in admin_emails:
            for claim_val in all_claim_values:
                if admin_email in claim_val:
                    is_admin = True
                    print(f"[AUTH SYNC] Admin granted via claim value scan: found '{admin_email}' in '{claim_val}'")
                    break
            if is_admin:
                break

    # Assign role based on checks above
    correct_role = "admin" if is_admin else "user"
    print(f"[AUTH SYNC] Final role decision: {correct_role} (is_admin={is_admin})")

    org = get_or_create_default_org(db)

    if not user:
        # Store Auth0 'sub' in username field. Hashed password is N/A for SSO users.
        user = models.User(username=sub, hashed_password="SSO", role=correct_role, org_id=org.id if org else None)
        db.add(user)
    else:
        # Always re-sync role on every login to enforce Zero-Trust compliance
        user.role = correct_role
        if user.org_id is None and org:
            user.org_id = org.id

    db.commit()
    db.refresh(user)

    ip = request.client.host if request.client else "N/A"
    log_audit(db, action="LOGIN", ip=ip, details={"provider": "Auth0", "role_assigned": correct_role, "email_claim": user_email or "NOT_PRESENT"}, user_id=user.id, org_id=user.org_id)

    return {"status": "synced", "role": user.role, "user_id": user.id, "org_id": user.org_id}


@app.post("/api/auth/debug")
def debug_token(token: str = Depends(oauth2_scheme)):
    """Debug endpoint: returns all claims in the token without validating signature."""
    claims = auth.debug_decode(token)
    # Also attempt verified decode and report outcome
    try:
        verified = auth.verify_auth0_token(token)
        verified_status = "OK"
    except Exception as e:
        verified = {}
        verified_status = str(e)
    return {
        "raw_claims": claims,
        "verified_status": verified_status,
        "email_claim": claims.get("email", "NOT PRESENT"),
        "name_claim": claims.get("name", "NOT PRESENT"),
        "nickname_claim": claims.get("nickname", "NOT PRESENT"),
        "sub_claim": claims.get("sub", "NOT PRESENT"),
    }


# -------------------------------------------------------------------
# Admin Endpoints
# -------------------------------------------------------------------
@app.get("/api/admin/users")
def get_users(db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    users = db.query(models.User).filter(models.User.org_id == current_user.org_id).order_by(models.User.id.asc()).all()
    return [{"id": u.id, "username": u.username, "role": u.role} for u in users]


@app.get("/api/admin/logs")
def get_audit_logs(db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    logs = db.query(models.AuditLog).filter(models.AuditLog.org_id == current_user.org_id).order_by(models.AuditLog.timestamp.desc()).limit(100).all()
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
    get_active_entities(db, org_id=current_user.org_id)
    return db.query(models.DLPPolicy).filter(models.DLPPolicy.org_id == current_user.org_id).order_by(models.DLPPolicy.pii_type.asc()).all()

class PolicyUpdate(BaseModel):
    pii_type: str
    is_active: bool

@app.post("/api/admin/policies")
def update_policy(update: PolicyUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    policy = db.query(models.DLPPolicy).filter(
        models.DLPPolicy.org_id == current_user.org_id,
        models.DLPPolicy.pii_type == update.pii_type
    ).first()
    if policy:
        policy.is_active = update.is_active
    else:
        db.add(models.DLPPolicy(pii_type=update.pii_type, is_active=update.is_active, org_id=current_user.org_id))
    db.commit()
    return {"msg": "Policy updated"}

@app.get("/api/admin/settings")
def get_settings(db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    settings = db.query(models.SystemSettings).filter(models.SystemSettings.org_id == current_user.org_id).first()
    if not settings:
        settings = models.SystemSettings(masking_style="LABEL", org_id=current_user.org_id)
        db.add(settings)
        db.commit()
    return {"masking_style": settings.masking_style}

class SettingsUpdate(BaseModel):
    masking_style: str

@app.put("/api/admin/settings")
def update_settings(update: SettingsUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    settings = db.query(models.SystemSettings).filter(models.SystemSettings.org_id == current_user.org_id).first()
    if not settings:
        settings = models.SystemSettings(masking_style=update.masking_style, org_id=current_user.org_id)
        db.add(settings)
    else:
        settings.masking_style = update.masking_style
    db.commit()
    return {"msg": "Settings updated"}

@app.get("/api/admin/custom-regex")
def get_custom_regex(db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    patterns = db.query(models.CustomRegexPolicy).filter(models.CustomRegexPolicy.org_id == current_user.org_id).all()
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
    
    new_regex = models.CustomRegexPolicy(name=regex.name.upper().replace(' ', '_'), pattern=regex.pattern, is_active=regex.is_active, org_id=current_user.org_id)
    db.add(new_regex)
    db.commit()
    return {"msg": "Regex added"}

@app.delete("/api/admin/custom-regex/{regex_id}")
def delete_custom_regex(regex_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    regex = db.query(models.CustomRegexPolicy).filter(
        models.CustomRegexPolicy.id == regex_id,
        models.CustomRegexPolicy.org_id == current_user.org_id
    ).first()
    if regex:
        db.delete(regex)
        db.commit()
    return {"msg": "Regex deleted"}

@app.get("/api/admin/logs/export")
def export_logs(db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    logs = db.query(models.AuditLog).filter(models.AuditLog.org_id == current_user.org_id).order_by(models.AuditLog.timestamp.desc()).all()
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
    logs = db.query(models.AuditLog).filter(models.AuditLog.org_id == current_user.org_id).all()
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
async def upload_file(request: Request, file: UploadFile = File(...), generate_certificate: bool = Form(False), current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    file_bytes = await file.read()
    
    ext = file.filename.lower().split('.')[-1] if file.filename and '.' in file.filename else ''
    
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
        elif ext in ['csv']:
            media_type = "text/csv"
        elif ext in ['jsonl']:
            media_type = "application/jsonl"
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format.")

        # Upload raw file to S3 first
        s3_key = upload_raw_to_s3(file_bytes, file.filename, media_type)
        active_entities, masking_style, custom_patterns = get_active_entities(db, org_id=current_user.org_id)
        
        org = db.query(models.Organization).filter(models.Organization.id == current_user.org_id).first()
        org_name = org.name if org else "Default Org"
    
        # 2. Dispatch task to Celery
        if ext in ['csv', 'jsonl']:
            from backend.app.worker import process_dataset_task
            task = process_dataset_task.delay(s3_key, file.filename, active_entities, custom_patterns)
        elif ext == 'zip':
            from backend.app.worker import process_batch_task
            task = process_batch_task.delay(s3_key, active_entities, masking_style, custom_patterns)
        else:
            from backend.app.worker import process_document_task
            task = process_document_task.delay(s3_key, file.filename, media_type, active_entities, masking_style, custom_patterns, generate_certificate, org_name)

        # Log audit for task initiation
        log_audit(db, action="FILE_MASK_TASK_STARTED", ip=request.client.host if request.client else "N/A", details={
            "filename": file.filename,
            "task_id": task.id
        }, user_id=current_user.id, org_id=current_user.org_id)

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
    language: Optional[str] = None

@app.post("/api/mask-text")
async def mask_text(request: Request, req: TextMaskRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    active_entities, masking_style, custom_patterns = get_active_entities(db, org_id=current_user.org_id)
    result = pii_engine.detect_and_mask_text(req.text, active_entities, masking_style, custom_patterns, language=req.language)
    
    if result["found"]:
        log_audit(db, action="TEXT_MASK", ip=request.client.host if request.client else "N/A", details={
            "detected": result["types"]
        }, user_id=current_user.id, org_id=current_user.org_id)
        
    return {
        "original": req.text,
        "masked": result["redacted"],
        "pii_found": result["found"],
        "pii_types": result["types"],
        "count": len(result["types"]),
    }

class CloudScanRequest(BaseModel):
    provider: str # "aws" or "azure"
    bucket_name: str
    prefix: str = ""
    access_key: str
    secret_key: str
    mode: str = "discovery" # "discovery" or "sanitize"

@app.post("/api/cloud-scan")
async def cloud_scan_api(request: Request, req: CloudScanRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    active_entities, masking_style, custom_patterns = get_active_entities(db, org_id=current_user.org_id)
    
    from backend.app.worker import scan_cloud_bucket_task
    task = scan_cloud_bucket_task.delay(  # type: ignore
        req.provider,
        req.bucket_name,
        req.prefix,
        req.access_key,
        req.secret_key,
        req.mode,
        active_entities,
        masking_style,
        custom_patterns
    )
    
    log_audit(db, action="CLOUD_SCAN_STARTED", ip=request.client.host if request.client else "N/A", details={
        "provider": req.provider,
        "bucket": req.bucket_name,
        "task_id": task.id
    }, user_id=current_user.id, org_id=current_user.org_id)
    
    return JSONResponse(status_code=202, content={
        "status": "accepted",
        "task_id": task.id,
        "message": "Cloud scan is being processed asynchronously."
    })

# -------------------------------------------------------------------
# Programmatic API Routes (Protected by API Key)
# -------------------------------------------------------------------
@app.post("/api/v1/mask-text")
async def api_v1_mask_text(request: Request, req: TextMaskRequest, api_key: models.APIKey = Depends(verify_api_key), db: Session = Depends(get_db)):
    active_entities, masking_style, custom_patterns = get_active_entities(db, org_id=int(api_key.org_id))  # type: ignore
    
    result = pii_engine.detect_and_mask_text(req.text, active_entities, str(masking_style), custom_patterns, language=req.language)
    
    if result["found"]:
        log_audit(db, action="API_TEXT_MASK", ip=request.client.host if request.client else "N/A", details={
            "detected": result["types"]
        }, org_id=int(api_key.org_id), api_key_id=str(api_key.id))  # type: ignore
        
    return {
        "original": req.text,
        "masked": result["redacted"],
        "pii_found": result["found"],
        "pii_types": result["types"],
        "count": len(result["types"]),
    }

@app.post("/api/v1/sanitize/dataset")
async def api_v1_sanitize_dataset(
    request: Request,
    file: UploadFile = File(...),
    language: Optional[str] = None,
    api_key: models.APIKey = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """AI Training Data Sanitization API - Parses CSV/JSONL and replaces PII with synthetic Faker data."""
    ext = file.filename.lower().split('.')[-1] if file.filename and '.' in file.filename else ''
    if ext not in ['csv', 'jsonl']:
        raise HTTPException(status_code=400, detail="Only .csv and .jsonl files are supported for datasets.")
        
    file_bytes = await file.read()
    media_type = "text/csv" if ext == 'csv' else "application/jsonl"
    
    s3_key = upload_raw_to_s3(file_bytes, file.filename if file.filename else "dataset", media_type)
    active_entities, _, custom_patterns = get_active_entities(db, org_id=int(api_key.org_id))  # type: ignore
    
    from backend.app.worker import process_dataset_task
    task = process_dataset_task.delay(s3_key, file.filename, active_entities, custom_patterns, language)  # type: ignore
    
    log_audit(db, action="API_DATASET_SANITIZATION", ip=request.client.host if request.client else "N/A", details={
        "filename": file.filename, "task_id": task.id
    }, org_id=int(api_key.org_id), api_key_id=str(api_key.id))  # type: ignore

    return JSONResponse(status_code=202, content={
        "status": "accepted",
        "task_id": task.id,
        "message": "Dataset is being sanitized asynchronously."
    })

@app.post("/api/v1/scan/realtime")
async def api_v1_scan_realtime(request: Request, req: TextMaskRequest, api_key: models.APIKey = Depends(verify_api_key), db: Session = Depends(get_db)):
    """Ultra-fast DLP Gateway for Slack/Teams Webhooks (<100ms)"""
    active_entities, _, custom_patterns = get_active_entities(db, org_id=int(api_key.org_id))  # type: ignore
    
    # Fast path: detect_raw avoids the heavy Anonymizer engine if we just need a boolean decision
    results = pii_engine.detect_raw(req.text, active_entities, custom_patterns, language=req.language)
    
    found = len(results) > 0
    entity_types = list(set([r.entity_type for r in results])) if found else []
    
    if found:
        log_audit(db, action="API_REALTIME_DLP_SCAN", ip=request.client.host if request.client else "N/A", details={
            "detected": entity_types
        }, org_id=int(api_key.org_id), api_key_id=str(api_key.id))  # type: ignore
        
    return {
        "action": "BLOCK" if found else "ALLOW",
        "pii_found": found,
        "pii_types": entity_types,
        "count": len(results)
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

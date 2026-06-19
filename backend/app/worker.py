import os
import boto3
import uuid
from celery import Celery
from . import pii_engine, file_handlers
from .main import mask_pii_in_image_gcp, upload_to_s3_and_get_url

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "pii-mask-ocr-files")

celery_app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)

s3_client = boto3.client('s3', region_name=AWS_REGION)

@celery_app.task(bind=True)
def process_document_task(self, s3_key: str, filename: str, content_type: str, active_entities: list[str]):
    try:
        # 1. Download raw file from S3
        self.update_state(state='PROCESSING', meta={'status': 'Downloading file...'})
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        file_bytes = response['Body'].read()

        # 2. Process
        self.update_state(state='PROCESSING', meta={'status': 'AI Masking in progress...'})
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        if ext in ['pdf']:
            out_bytes, report = file_handlers.process_pdf(file_bytes, active_entities, pii_engine.detect_raw)
            media_type = "application/pdf"
        elif ext in ['docx']:
            out_bytes, report = file_handlers.process_docx(file_bytes, active_entities, pii_engine.detect_and_mask_text)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif ext in ['jpg', 'jpeg', 'png', 'webp']:
            out_bytes, report = mask_pii_in_image_gcp(file_bytes, active_entities)
            media_type = "image/jpeg"
        else:
            raise ValueError("Unsupported file format.")

        # 3. Upload masked file to S3
        self.update_state(state='PROCESSING', meta={'status': 'Uploading masked file...'})
        masked_s3_key = f"masked_{uuid.uuid4().hex}_{filename}"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=masked_s3_key,
            Body=out_bytes,
            ContentType=media_type
        )
        
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': masked_s3_key},
            ExpiresIn=3600 # 1 hour
        )

        return {
            "status": "success",
            "download_url": download_url,
            "report": report
        }
    except Exception as e:
        # Cleanly fail task
        raise e

import os
import boto3
import uuid
from celery import Celery
from . import pii_engine, file_handlers

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "pii-mask-ocr-files")

celery_app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)

s3_client = boto3.client('s3', region_name=AWS_REGION)

@celery_app.task(bind=True)
def process_document_task(self, s3_key: str, filename: str, content_type: str, active_entities: list[str], masking_style: str = "LABEL", custom_patterns: list = None):
    try:
        # 1. Download raw file from S3
        self.update_state(state='PROCESSING', meta={'status': 'Downloading file...'})
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        file_bytes = response['Body'].read()

        # 2. Process
        self.update_state(state='PROCESSING', meta={'status': 'AI Masking in progress...'})
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        if ext in ['pdf']:
            out_bytes, report = file_handlers.process_pdf(file_bytes, active_entities, pii_engine.detect_raw, custom_patterns)
            media_type = "application/pdf"
        elif ext in ['docx']:
            out_bytes, report = file_handlers.process_docx(file_bytes, active_entities, pii_engine.detect_and_mask_text, masking_style, custom_patterns)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif ext in ['jpg', 'jpeg', 'png', 'webp']:
            out_bytes, report = file_handlers.mask_pii_in_image_gcp(file_bytes, active_entities, pii_engine.detect_raw, custom_patterns)
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
    finally:
        # 4. Cleanup: Delete raw unmasked file from S3 to prevent data leaks
        try:
            s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
            # We don't log success to avoid spam, but this guarantees deletion
        except Exception:
            pass # Best effort cleanup on failure

@celery_app.task(bind=True)
def process_batch_task(self, s3_key: str, active_entities: list[str], masking_style: str = "LABEL", custom_patterns: list = None):
    import zipfile
    import io
    try:
        self.update_state(state='PROCESSING', meta={'status': 'Downloading batch zip...'})
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        zip_bytes = response['Body'].read()
        
        in_zip = zipfile.ZipFile(io.BytesIO(zip_bytes))
        out_bytes_io = io.BytesIO()
        out_zip = zipfile.ZipFile(out_bytes_io, 'w', zipfile.ZIP_DEFLATED)
        
        report_summary = []
        total_files = len(in_zip.namelist())
        
        for idx, filename in enumerate(in_zip.namelist()):
            self.update_state(state='PROCESSING', meta={'status': f'Masking file {idx+1}/{total_files} ({filename})'})
            file_bytes = in_zip.read(filename)
            ext = filename.lower().split('.')[-1] if '.' in filename else ''
            
            try:
                if ext in ['pdf']:
                    out_b, rep = file_handlers.process_pdf(file_bytes, active_entities, pii_engine.detect_raw, custom_patterns)
                    out_zip.writestr(f"masked_{filename}", out_b)
                    report_summary.extend(rep)
                elif ext in ['docx']:
                    out_b, rep = file_handlers.process_docx(file_bytes, active_entities, pii_engine.detect_and_mask_text, masking_style, custom_patterns)
                    out_zip.writestr(f"masked_{filename}", out_b)
                    report_summary.extend(rep)
                elif ext in ['jpg', 'jpeg', 'png', 'webp']:
                    out_b, rep = file_handlers.mask_pii_in_image_gcp(file_bytes, active_entities, pii_engine.detect_raw, custom_patterns)
                    out_zip.writestr(f"masked_{filename}", out_b)
                    report_summary.extend(rep)
            except Exception:
                continue # Skip failing files in batch
                
        out_zip.close()
        
        self.update_state(state='PROCESSING', meta={'status': 'Uploading masked batch...'})
        masked_s3_key = f"masked_batch_{uuid.uuid4().hex}.zip"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=masked_s3_key,
            Body=out_bytes_io.getvalue(),
            ContentType='application/zip'
        )
        
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': masked_s3_key},
            ExpiresIn=3600
        )
        
        return {
            "status": "success",
            "download_url": download_url,
            "report": report_summary
        }
    except Exception as e:
        raise e
    finally:
        try:
            s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        except Exception:
            pass

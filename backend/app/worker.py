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
def process_document_task(self, s3_key: str, filename: str, content_type: str, active_entities: list[str], masking_style: str = "LABEL", custom_patterns: list = None, generate_certificate: bool = False, org_name: str = "Default Org"):
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

        cert_download_url = None
        if generate_certificate:
            self.update_state(state='PROCESSING', meta={'status': 'Generating HIPAA Certificate...'})
            from backend.app.compliance_cert import generate_hipaa_certificate
            entities_removed = [item['type'] for item in report] if report else []
            cert_bytes = generate_hipaa_certificate(org_name, filename, entities_removed, self.request.id)
            cert_s3_key = f"cert_{uuid.uuid4().hex}_{filename}.pdf"
            s3_client.put_object(Bucket=S3_BUCKET, Key=cert_s3_key, Body=cert_bytes, ContentType="application/pdf")
            cert_download_url = s3_client.generate_presigned_url('get_object', Params={'Bucket': S3_BUCKET, 'Key': cert_s3_key}, ExpiresIn=3600)

        return {
            "status": "success",
            "download_url": download_url,
            "certificate_url": cert_download_url,
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
        
        # Zip Bomb Prevention
        total_uncompressed_size = sum([info.file_size for info in in_zip.infolist()])
        if total_uncompressed_size > 500 * 1024 * 1024: # 500 MB limit
            raise ValueError(f"Batch zip exceeds safe extraction limits (500MB). Uncompressed size: {total_uncompressed_size/(1024*1024):.1f}MB")
            
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
            except Exception as ex:
                error_msg = f"Failed to process {filename}: {str(ex)}"
                out_zip.writestr(f"error_{filename}.txt", error_msg.encode('utf-8'))
                continue # Skip failing files but record the error
                
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

@celery_app.task(bind=True)
def process_dataset_task(self, s3_key: str, filename: str, active_entities: list[str], custom_patterns: list = None, language: str = None):
    import pandas as pd
    import io
    try:
        self.update_state(state='PROCESSING', meta={'status': 'Downloading dataset...'})
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        file_bytes = response['Body'].read()
        
        ext = filename.lower().split('.')[-1]
        
        self.update_state(state='PROCESSING', meta={'status': 'Parsing dataset...'})
        if ext == 'csv':
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif ext == 'jsonl':
            df = pd.read_json(io.BytesIO(file_bytes), lines=True)
        else:
            raise ValueError("Only CSV and JSONL are supported for AI datasets")
            
        total_rows = len(df)
        
        # Iterate and sanitize every string column
        self.update_state(state='PROCESSING', meta={'status': 'Synthesizing PII with Faker...'})
        
        # Process in batches for progress
        for idx in range(total_rows):
            if idx % max(1, total_rows//10) == 0:
                self.update_state(state='PROCESSING', meta={'status': f'Synthesizing {idx}/{total_rows} rows...'})
                
            for col in df.columns:
                val = df.at[idx, col]
                if isinstance(val, str) and len(val) > 2:
                    res = pii_engine.detect_and_synthesize_text(val, active_entities, custom_patterns, language)
                    if res["found"]:
                        df.at[idx, col] = res["redacted"]
                        
        self.update_state(state='PROCESSING', meta={'status': 'Uploading sanitized dataset...'})
        out_buffer = io.BytesIO()
        if ext == 'csv':
            df.to_csv(out_buffer, index=False)
            content_type = "text/csv"
        else:
            df.to_json(out_buffer, orient='records', lines=True)
            content_type = "application/jsonl"
            
        sanitized_s3_key = f"sanitized_{uuid.uuid4().hex}_{filename}"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=sanitized_s3_key,
            Body=out_buffer.getvalue(),
            ContentType=content_type
        )
        
        download_url = s3_client.generate_presigned_url(
            'get_object', Params={'Bucket': S3_BUCKET, 'Key': sanitized_s3_key}, ExpiresIn=3600
        )
        
        return {
            "status": "success",
            "download_url": download_url,
            "rows_processed": total_rows
        }
    except Exception as e:
        raise e
    finally:
        try:
            s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        except Exception:
            pass

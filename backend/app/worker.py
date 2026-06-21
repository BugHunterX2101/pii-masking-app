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
            entities_removed = []
            if report:
                for item in report:
                    if 'pii_types' in item:
                        entities_removed.extend(item['pii_types'])
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

@celery_app.task(bind=True)
def scan_cloud_bucket_task(self, provider: str, bucket_name: str, prefix: str, access_key: str, secret_key: str, mode: str, active_entities: list[str], masking_style: str = "LABEL", custom_patterns: list = None):
    import io
    import boto3
    import json
    import uuid
    from azure.storage.blob import BlobServiceClient
    
    self.update_state(state='PROCESSING', meta={'status': f'Connecting to {provider.upper()}...'})
    
    files_to_process = []
    
    try:
        if provider == "aws":
            # Temporarily instantiate an S3 client with the provided credentials
            client = boto3.client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_key, region_name='us-east-1')
            paginator = client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        if not obj['Key'].endswith('/'):
                            files_to_process.append({"key": obj['Key'], "size": obj['Size']})
                        if len(files_to_process) >= 50:
                            break
                if len(files_to_process) >= 50:
                    break
                    
        elif provider == "azure":
            # Secret key acts as connection string for Azure
            blob_service_client = BlobServiceClient.from_connection_string(secret_key)
            container_client = blob_service_client.get_container_client(bucket_name)
            
            blob_list = container_client.list_blobs(name_starts_with=prefix)
            for blob in blob_list:
                files_to_process.append({"key": blob.name, "size": blob.size})
                if len(files_to_process) >= 50:
                    break
        else:
            raise ValueError(f"Unsupported provider: {provider}")
            
    except Exception as e:
        raise ValueError(f"Failed to connect to {provider.upper()}: {str(e)}")
        
    total_files = len(files_to_process)
    if total_files == 0:
        return {"status": "success", "message": "No files found to scan.", "report": []}
        
    discovery_report = []
    
    for idx, f in enumerate(files_to_process):
        key = f["key"]
        self.update_state(state='PROCESSING', meta={'status': f'Scanning file {idx+1}/{total_files}: {key}'})
        
        try:
            # Download file into memory
            file_bytes = b""
            if provider == "aws":
                obj = client.get_object(Bucket=bucket_name, Key=key)
                file_bytes = obj['Body'].read()
            elif provider == "azure":
                blob_client = container_client.get_blob_client(key)
                file_bytes = blob_client.download_blob().readall()
                
            ext = key.lower().split('.')[-1] if '.' in key else ''
            rep = []
            out_b = None
            
            # Use appropriate handler
            if ext in ['pdf']:
                out_b, rep = file_handlers.process_pdf(file_bytes, active_entities, pii_engine.detect_raw, custom_patterns)
            elif ext in ['docx']:
                out_b, rep = file_handlers.process_docx(file_bytes, active_entities, pii_engine.detect_and_mask_text, masking_style, custom_patterns)
            elif ext in ['jpg', 'jpeg', 'png', 'webp']:
                out_b, rep = file_handlers.mask_pii_in_image_gcp(file_bytes, active_entities, pii_engine.detect_raw, custom_patterns)
            elif ext in ['csv', 'jsonl']:
                # For discovery on datasets, we skip heavy dataset masking in Phase 3 basic scan
                rep = [{"text": "Dataset Scan skipped in Phase 3 basic scan", "pii_types": []}]
                out_b = file_bytes # unchanged
                
            # Aggregate found types
            found_types = set()
            for r in rep:
                if 'pii_types' in r:
                    found_types.update(r['pii_types'])
                    
            if found_types:
                discovery_report.append({
                    "file": key,
                    "pii_detected": list(found_types),
                    "items_found": len(rep)
                })
                
            # If Sanitize mode, write back to a sanitized prefix
            if mode == "sanitize" and out_b and rep:
                sanitized_key = f"sanitized/{key}"
                if provider == "aws":
                    client.put_object(Bucket=bucket_name, Key=sanitized_key, Body=out_b)
                elif provider == "azure":
                    out_blob = container_client.get_blob_client(sanitized_key)
                    out_blob.upload_blob(out_b, overwrite=True)
                    
        except Exception as ex:
            discovery_report.append({
                "file": key,
                "error": str(ex)
            })
            
    # Upload the final discovery report JSON to S3 so the UI can download it
    report_json = json.dumps(discovery_report, indent=2)
    report_s3_key = f"discovery_report_{uuid.uuid4().hex}.json"
    s3_client.put_object(Bucket=S3_BUCKET, Key=report_s3_key, Body=report_json, ContentType="application/json")
    
    download_url = s3_client.generate_presigned_url('get_object', Params={'Bucket': S3_BUCKET, 'Key': report_s3_key}, ExpiresIn=3600)

    return {
        "status": "success",
        "download_url": download_url,
        "files_scanned": total_files,
        "files_with_pii": len([r for r in discovery_report if "pii_detected" in r])
    }

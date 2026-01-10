import base64
import json
import os
import time
from fastapi import APIRouter, HTTPException

from kyc_platform.api_handler.schemas import (
    DocumentUploadRequest,
    DocumentUploadResponse,
    DocumentStatusResponse,
    ErrorResponse,
    HealthResponse,
    ProcessingStatus,
)
from kyc_platform.api_handler.services.id_generator import generate_document_id, generate_verification_id
from kyc_platform.api_handler.services.idempotency import generate_idempotency_key
from kyc_platform.api_handler.services.enqueue import enqueue_service
from kyc_platform.contracts.models import DocumentRecord
from kyc_platform.persistence import get_repository
from kyc_platform.shared.config import config
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def save_image(image_base64: str, document_id: str) -> str:
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    
    try:
        image_data = base64.b64decode(image_base64)
    except Exception:
        raise ValueError("Invalid base64 image")
    
    filename = f"{document_id}.jpg"
    filepath = os.path.join(config.UPLOAD_DIR, filename)
    
    with open(filepath, "wb") as f:
        f.write(image_data)
    
    return filepath


@router.post(
    "/documents",
    response_model=DocumentUploadResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Upload document for OCR processing",
    description="""
Upload an identity document image for OCR extraction.

**Supported document types:**
- `dni`: Argentine National Identity Document (DNI nuevo or viejo)
- `passport`: Argentine Passport with MRZ
- `license`: Argentine Driver's License

**Optional features:**
- `check_authenticity`: Enable photocopy/screen detection
- `check_document_liveness`: Enable multi-frame liveness check (requires `frames` array)

**Idempotency:**
Duplicate requests (same client_id + document_type + image) return the existing document without reprocessing.

**Processing Flow:**
1. Document is validated and stored
2. Job is queued for async OCR processing  
3. Use GET /documents/{document_id} to check status
4. Optional: Receive results via webhook
    """,
)
async def upload_document(request: DocumentUploadRequest):
    repository = get_repository()
    
    base_idempotency_key = generate_idempotency_key(
        request.client_id,
        request.document_type,
        request.image,
    )
    
    if not request.force_reprocess:
        existing = repository.get_by_idempotency_key(base_idempotency_key)
        if existing:
            logger.info(
                "Duplicate request detected, returning existing document",
                extra={
                    "document_id": existing.document_id,
                    "idempotency_key": base_idempotency_key[:16] + "...",
                },
            )
            return DocumentUploadResponse(
                ok=True,
                document_id=existing.document_id,
                verification_id=existing.verification_id,
                status=ProcessingStatus(existing.status.value),
            )
        idempotency_key = base_idempotency_key
    else:
        idempotency_key = f"{base_idempotency_key}_{int(time.time() * 1000)}"
        logger.info(
            "Force reprocess requested, generating unique idempotency key",
            extra={"idempotency_key": idempotency_key[:16] + "..."},
        )
    
    document_id = generate_document_id()
    verification_id = generate_verification_id()
    
    logger.info(
        "Received document upload request",
        extra={
            "document_id": document_id,
            "document_type": request.document_type.value,
            "client_id": request.client_id,
        },
    )
    
    try:
        image_ref = save_image(request.image, document_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save image: {e}")
        raise HTTPException(status_code=500, detail="Failed to save image")
    
    record = DocumentRecord(
        document_id=document_id,
        verification_id=verification_id,
        client_id=request.client_id,
        document_type=request.document_type,
        image_ref=image_ref,
        idempotency_key=idempotency_key,
    )
    
    if not repository.save(record):
        raise HTTPException(status_code=500, detail="Failed to save document record")
    
    success = enqueue_service.enqueue_document_uploaded(
        document_id=document_id,
        verification_id=verification_id,
        client_id=request.client_id,
        document_type=request.document_type,
        image_ref=image_ref,
        check_authenticity=request.check_authenticity,
        check_document_liveness=request.check_document_liveness,
        frames=request.frames,
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to enqueue document for processing")
    
    record.mark_queued()
    repository.update(record)
    
    return DocumentUploadResponse(
        ok=True,
        document_id=document_id,
        verification_id=verification_id,
        status=ProcessingStatus.QUEUED,
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentStatusResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get document processing status",
    description="""
Retrieve the current processing status and extracted data for a document.

**Status values:**
- `pending`: Document received, not yet queued
- `queued`: Document queued for OCR processing
- `processing`: OCR extraction in progress
- `extracted`: Extraction completed successfully (extracted_data available)
- `failed`: Extraction failed (see errors field)
    """,
)
async def get_document_status(document_id: str):
    repository = get_repository()
    record = repository.get_by_id(document_id)
    
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentStatusResponse(
        document_id=record.document_id,
        verification_id=record.verification_id,
        document_type=record.document_type,
        status=ProcessingStatus(record.status.value),
        extracted_data=record.extracted_data,
        confidence=record.confidence,
        processing_time_ms=record.processing_time_ms,
        errors=record.errors,
    )


@router.post(
    "/process",
    summary="Process queued documents (local development only)",
    description="""
Manually trigger OCR processing for documents in the queue.

**Note:** This endpoint is for local development only. In production, 
documents are processed automatically by Lambda workers consuming from SQS.

**Parameters:**
- `max_messages`: Maximum number of documents to process (default: 10)
    """,
)
async def process_queue(max_messages: int = 10):
    from kyc_platform.queue import get_queue
    from kyc_platform.workers.ocr_dni.lambda_function import handler as dni_handler
    from kyc_platform.workers.ocr_passport.lambda_function import handler as passport_handler
    from kyc_platform.workers.ocr_license.lambda_function import handler as license_handler
    
    if not config.is_local():
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only available in local development mode",
        )
    
    results = {"dni": [], "passport": [], "license": []}
    queue = get_queue()
    
    dni_messages = queue.consume("kyc-ocr-dni", max_messages)
    
    if dni_messages:
        event = {"Records": [{"body": m["body"], "receiptHandle": m["receipt_handle"]} for m in dni_messages]}
        try:
            result = dni_handler(event, None)
            body = json.loads(result.get("body", "{}")) if isinstance(result.get("body"), str) else result
            results["dni"] = body.get("results", [])
            for m in dni_messages:
                queue.delete_message("kyc-ocr-dni", m["receipt_handle"])
        except Exception as e:
            logger.error(f"DNI processing failed: {e}")
            results["dni"] = [{"error": str(e)}]
    
    passport_messages = queue.consume("kyc-ocr-passport", max_messages)
    
    if passport_messages:
        event = {"Records": [{"body": m["body"], "receiptHandle": m["receipt_handle"]} for m in passport_messages]}
        try:
            result = passport_handler(event, None)
            body = json.loads(result.get("body", "{}")) if isinstance(result.get("body"), str) else result
            results["passport"] = body.get("results", [])
            for m in passport_messages:
                queue.delete_message("kyc-ocr-passport", m["receipt_handle"])
        except Exception as e:
            logger.error(f"Passport processing failed: {e}")
            results["passport"] = [{"error": str(e)}]
    
    license_messages = queue.consume("kyc-ocr-license", max_messages)
    
    if license_messages:
        event = {"Records": [{"body": m["body"], "receiptHandle": m["receipt_handle"]} for m in license_messages]}
        try:
            result = license_handler(event, None)
            body = json.loads(result.get("body", "{}")) if isinstance(result.get("body"), str) else result
            results["license"] = body.get("results", [])
            for m in license_messages:
                queue.delete_message("kyc-ocr-license", m["receipt_handle"])
        except Exception as e:
            logger.error(f"License processing failed: {e}")
            results["license"] = [{"error": str(e)}]
    
    total_processed = len(results["dni"]) + len(results["passport"]) + len(results["license"])
    
    return {
        "ok": True,
        "processed": total_processed,
        "results": results,
        "message": f"Processed {total_processed} document(s)" if total_processed > 0 else "No documents in queue",
    }


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns the health status of the KYC API service.",
)
async def health_check():
    return HealthResponse(status="healthy", service="kyc-api-handler")

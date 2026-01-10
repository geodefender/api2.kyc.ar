import base64
import os
from fastapi import APIRouter, HTTPException

from kyc_platform.api_handler.schemas import (
    DocumentUploadRequest,
    DocumentUploadResponse,
    DocumentStatusResponse,
    ErrorResponse,
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
)
async def upload_document(request: DocumentUploadRequest):
    repository = get_repository()
    
    idempotency_key = generate_idempotency_key(
        request.client_id,
        request.document_type,
        request.image,
    )
    
    existing = repository.get_by_idempotency_key(idempotency_key)
    if existing:
        logger.info(
            "Duplicate request detected, returning existing document",
            extra={
                "document_id": existing.document_id,
                "idempotency_key": idempotency_key[:16] + "...",
            },
        )
        return DocumentUploadResponse(
            ok=True,
            document_id=existing.document_id,
            verification_id=existing.verification_id,
            status=existing.status.value,
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
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to enqueue document for processing")
    
    record.mark_queued()
    repository.update(record)
    
    return DocumentUploadResponse(
        ok=True,
        document_id=document_id,
        verification_id=verification_id,
        status="queued",
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentStatusResponse,
    responses={404: {"model": ErrorResponse}},
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
        status=record.status.value,
        extracted_data=record.extracted_data,
        confidence=record.confidence,
        processing_time_ms=record.processing_time_ms,
        errors=record.errors,
    )


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "kyc-api-handler"}

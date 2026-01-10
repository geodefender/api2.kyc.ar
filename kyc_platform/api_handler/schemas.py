from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field

from kyc_platform.shared.config import DocumentType


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    FAILED = "failed"


class DocumentUploadRequest(BaseModel):
    document_type: DocumentType = Field(
        ...,
        description="Type of identity document to process",
        json_schema_extra={"example": "dni"},
    )
    image: str = Field(
        ...,
        description="Base64 encoded image of the document (JPEG or PNG format)",
        json_schema_extra={
            "format": "byte",
            "example": "/9j/4AAQSkZJRgABAQEASABIAAD/2wBD... (base64 encoded image)",
        },
    )
    client_id: str = Field(
        default="demo",
        description="Unique client identifier for grouping documents and idempotency",
        json_schema_extra={"example": "client_abc123"},
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="Optional URL to receive extraction results via POST webhook",
        json_schema_extra={"example": "https://your-app.com/webhook/kyc"},
    )
    webhook_secret: Optional[str] = Field(
        default=None,
        description="Secret key for HMAC-SHA256 webhook signature verification",
        json_schema_extra={"example": "your-webhook-secret"},
    )
    force_reprocess: bool = Field(
        default=False,
        description="Skip idempotency check and force reprocessing of the image",
        json_schema_extra={"example": False},
    )
    check_authenticity: bool = Field(
        default=False,
        description="Enable authenticity analysis (saturation, sharpness, glare, moire detection)",
        json_schema_extra={"example": True},
    )
    check_document_liveness: bool = Field(
        default=False,
        description="Enable document liveness check (requires frames parameter)",
        json_schema_extra={"example": False},
    )
    frames: Optional[list[str]] = Field(
        default=None,
        description="Array of 3-5 base64 images at different angles for document liveness check",
        json_schema_extra={"example": None},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "document_type": "dni",
                    "image": "/9j/4AAQSkZJRgABAQEASABIAAD...",
                    "client_id": "client_abc123",
                    "webhook_url": "https://your-app.com/webhook/kyc",
                    "webhook_secret": "your-webhook-secret",
                }
            ]
        }
    }


class DocumentUploadResponse(BaseModel):
    ok: bool = Field(
        ...,
        description="Indicates if the request was successful",
        json_schema_extra={"example": True},
    )
    document_id: str = Field(
        ...,
        description="Unique identifier for the uploaded document",
        json_schema_extra={"example": "doc_1736523845123_a1b2c3d4"},
    )
    verification_id: str = Field(
        ...,
        description="Verification session identifier for grouping related documents",
        json_schema_extra={"example": "ver_1736523845123_e5f6g7h8"},
    )
    status: ProcessingStatus = Field(
        ...,
        description="Current processing status of the document",
        json_schema_extra={"example": "queued"},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ok": True,
                    "document_id": "doc_1736523845123_a1b2c3d4",
                    "verification_id": "ver_1736523845123_e5f6g7h8",
                    "status": "queued",
                }
            ]
        }
    }


class DocumentStatusResponse(BaseModel):
    document_id: str = Field(
        ...,
        description="Unique identifier for the document",
        json_schema_extra={"example": "doc_1736523845123_a1b2c3d4"},
    )
    verification_id: str = Field(
        ...,
        description="Verification session identifier",
        json_schema_extra={"example": "ver_1736523845123_e5f6g7h8"},
    )
    document_type: DocumentType = Field(
        ...,
        description="Type of identity document",
        json_schema_extra={"example": "dni"},
    )
    status: ProcessingStatus = Field(
        ...,
        description="Current processing status",
        json_schema_extra={"example": "extracted"},
    )
    extracted_data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Extracted document data (available when status is 'extracted')",
        json_schema_extra={
            "example": {
                "numero_documento": "12345678",
                "apellido": "GONZALEZ",
                "nombre": "JUAN CARLOS",
                "sexo": "M",
                "nacionalidad": "ARG",
                "fecha_nacimiento": "15/03/1985",
            }
        },
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Extraction confidence score (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
        json_schema_extra={"example": 0.95},
    )
    processing_time_ms: Optional[int] = Field(
        default=None,
        description="Total processing time in milliseconds",
        json_schema_extra={"example": 2450},
    )
    errors: Optional[list[str]] = Field(
        default=None,
        description="List of errors if status is 'failed'",
        json_schema_extra={"example": ["OCR extraction failed: image too blurry"]},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "document_id": "doc_1736523845123_a1b2c3d4",
                    "verification_id": "ver_1736523845123_e5f6g7h8",
                    "document_type": "dni",
                    "status": "extracted",
                    "extracted_data": {
                        "numero_documento": "12345678",
                        "apellido": "GONZALEZ",
                        "nombre": "JUAN CARLOS",
                    },
                    "confidence": 0.95,
                    "processing_time_ms": 2450,
                    "errors": None,
                }
            ]
        }
    }


class ErrorResponse(BaseModel):
    ok: bool = Field(
        default=False,
        description="Always false for error responses",
        json_schema_extra={"example": False},
    )
    error: str = Field(
        ...,
        description="Error type or code",
        json_schema_extra={"example": "DOCUMENT_NOT_FOUND"},
    )
    detail: Optional[str] = Field(
        default=None,
        description="Detailed error message",
        json_schema_extra={"example": "Document with ID doc_xyz not found"},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ok": False,
                    "error": "DOCUMENT_NOT_FOUND",
                    "detail": "Document with ID doc_xyz not found",
                }
            ]
        }
    }


class HealthResponse(BaseModel):
    status: str = Field(
        ...,
        description="Health status of the service",
        json_schema_extra={"example": "healthy"},
    )
    service: str = Field(
        ...,
        description="Name of the service",
        json_schema_extra={"example": "kyc-api-handler"},
    )

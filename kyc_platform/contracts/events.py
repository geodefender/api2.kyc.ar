from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from kyc_platform.shared.config import DocumentType


class BaseEvent(BaseModel):
    event: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    version: str = "1"


class DocumentUploadedEvent(BaseEvent):
    event: str = "document.uploaded.v1"
    document_id: str
    verification_id: str
    client_id: str
    document_type: DocumentType
    image_ref: str
    check_authenticity: bool = False
    check_document_liveness: bool = False
    frames: Optional[list[str]] = None


class DocumentExtractedEvent(BaseEvent):
    event: str = "document.extracted.v1"
    document_id: str
    verification_id: str
    document_type: DocumentType
    extracted_data: dict[str, Any]
    confidence: float
    processing_time_ms: int
    errors: Optional[list[str]] = None
    authenticity_result: Optional[dict[str, Any]] = None
    liveness_result: Optional[dict[str, Any]] = None


class EventFactory:
    @staticmethod
    def create_document_uploaded(
        document_id: str,
        verification_id: str,
        client_id: str,
        document_type: DocumentType,
        image_ref: str,
        check_authenticity: bool = False,
        check_document_liveness: bool = False,
        frames: Optional[list[str]] = None,
    ) -> DocumentUploadedEvent:
        return DocumentUploadedEvent(
            document_id=document_id,
            verification_id=verification_id,
            client_id=client_id,
            document_type=document_type,
            image_ref=image_ref,
            check_authenticity=check_authenticity,
            check_document_liveness=check_document_liveness,
            frames=frames,
        )
    
    @staticmethod
    def create_document_extracted(
        document_id: str,
        verification_id: str,
        document_type: DocumentType,
        extracted_data: dict[str, Any],
        confidence: float,
        processing_time_ms: int,
        errors: Optional[list[str]] = None,
        authenticity_result: Optional[dict[str, Any]] = None,
        liveness_result: Optional[dict[str, Any]] = None,
    ) -> DocumentExtractedEvent:
        return DocumentExtractedEvent(
            document_id=document_id,
            verification_id=verification_id,
            document_type=document_type,
            extracted_data=extracted_data,
            confidence=confidence,
            processing_time_ms=processing_time_ms,
            errors=errors,
            authenticity_result=authenticity_result,
            liveness_result=liveness_result,
        )

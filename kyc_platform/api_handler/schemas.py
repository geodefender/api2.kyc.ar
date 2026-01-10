from typing import Optional
from pydantic import BaseModel, Field

from kyc_platform.shared.config import DocumentType


class DocumentUploadRequest(BaseModel):
    document_type: DocumentType = Field(..., description="Type of document: dni or passport")
    image: str = Field(..., description="Base64 encoded image")
    client_id: str = Field(default="demo", description="Client identifier")


class DocumentUploadResponse(BaseModel):
    ok: bool
    document_id: str
    verification_id: str
    status: str


class DocumentStatusResponse(BaseModel):
    document_id: str
    verification_id: str
    document_type: DocumentType
    status: str
    extracted_data: Optional[dict] = None
    confidence: Optional[float] = None
    processing_time_ms: Optional[int] = None
    errors: Optional[list[str]] = None


class ErrorResponse(BaseModel):
    ok: bool = False
    error: str
    detail: Optional[str] = None

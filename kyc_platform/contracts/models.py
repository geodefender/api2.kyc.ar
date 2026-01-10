from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field

from kyc_platform.shared.config import DocumentType


class DocumentStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    FAILED = "failed"


class DNIData(BaseModel):
    numero_documento: Optional[str] = None
    apellido: Optional[str] = None
    nombre: Optional[str] = None
    sexo: Optional[str] = None
    nacionalidad: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    fecha_emision: Optional[str] = None
    fecha_vencimiento: Optional[str] = None
    ejemplar: Optional[str] = None
    tramite: Optional[str] = None
    cuil: Optional[str] = None
    pdf417_raw: Optional[str] = None


class PassportData(BaseModel):
    numero_pasaporte: Optional[str] = None
    apellido: Optional[str] = None
    nombre: Optional[str] = None
    nacionalidad: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    sexo: Optional[str] = None
    fecha_vencimiento: Optional[str] = None
    codigo_pais: Optional[str] = None
    mrz_line1: Optional[str] = None
    mrz_line2: Optional[str] = None


class DocumentRecord(BaseModel):
    document_id: str
    verification_id: str
    client_id: str
    document_type: DocumentType
    status: DocumentStatus = DocumentStatus.PENDING
    image_ref: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    extracted_data: Optional[dict[str, Any]] = None
    confidence: Optional[float] = None
    processing_time_ms: Optional[int] = None
    errors: Optional[list[str]] = None
    
    def mark_queued(self) -> "DocumentRecord":
        self.status = DocumentStatus.QUEUED
        self.updated_at = datetime.utcnow().isoformat()
        return self
    
    def mark_processing(self) -> "DocumentRecord":
        self.status = DocumentStatus.PROCESSING
        self.updated_at = datetime.utcnow().isoformat()
        return self
    
    def mark_extracted(
        self,
        extracted_data: dict[str, Any],
        confidence: float,
        processing_time_ms: int,
    ) -> "DocumentRecord":
        self.status = DocumentStatus.EXTRACTED
        self.extracted_data = extracted_data
        self.confidence = confidence
        self.processing_time_ms = processing_time_ms
        self.updated_at = datetime.utcnow().isoformat()
        return self
    
    def mark_failed(self, errors: list[str]) -> "DocumentRecord":
        self.status = DocumentStatus.FAILED
        self.errors = errors
        self.updated_at = datetime.utcnow().isoformat()
        return self

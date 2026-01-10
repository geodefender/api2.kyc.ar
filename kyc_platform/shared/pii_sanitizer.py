"""
PII Sanitizer - Utilities for safe logging of sensitive data.

NEVER log:
- Full MRZ lines
- PDF417 raw barcode data
- Base64 encoded images
- Full document numbers
- Full CUIL/CUIT numbers

ALWAYS log:
- Truncated hashes
- Last 2-3 digits of document numbers
- Boolean flags (has_mrz: true)
- Counts and lengths
"""

import hashlib
import re
from typing import Any, Optional


def hash_truncated(value: str, length: int = 8) -> str:
    """Generate a truncated hash for identification without exposing full value."""
    if not value:
        return "empty"
    full_hash = hashlib.sha256(value.encode()).hexdigest()
    return full_hash[:length]


def mask_document_number(doc_number: Optional[str]) -> str:
    """Mask document number, showing only last 3 digits."""
    if not doc_number:
        return "***"
    clean = re.sub(r"[^0-9]", "", doc_number)
    if len(clean) <= 3:
        return "***"
    return f"***{clean[-3:]}"


def mask_cuil(cuil: Optional[str]) -> str:
    """Mask CUIL/CUIT, showing only verification digit."""
    if not cuil:
        return "**-********-*"
    clean = re.sub(r"[^0-9]", "", cuil)
    if len(clean) < 2:
        return "**-********-*"
    return f"**-********-{clean[-1]}"


def mask_mrz_line(mrz_line: Optional[str]) -> str:
    """Mask MRZ line, showing only structure."""
    if not mrz_line:
        return None
    length = len(mrz_line)
    first_char = mrz_line[0] if mrz_line else "?"
    return f"{first_char}***[{length} chars]"


def mask_pdf417(pdf417_raw: Optional[str]) -> str:
    """Mask PDF417 barcode data."""
    if not pdf417_raw:
        return None
    return f"[PDF417:{len(pdf417_raw)} bytes, hash:{hash_truncated(pdf417_raw)}]"


def mask_base64_image(image_base64: Optional[str]) -> str:
    """Mask base64 image, showing only size."""
    if not image_base64:
        return None
    size_kb = len(image_base64) * 3 // 4 // 1024
    return f"[IMAGE:{size_kb}KB, hash:{hash_truncated(image_base64)}]"


def sanitize_extracted_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize extracted data for safe logging.
    
    Returns a copy with sensitive fields masked.
    """
    if not data:
        return {}
    
    sanitized = {}
    
    sensitive_fields = {
        "numero_documento": mask_document_number,
        "numero_pasaporte": mask_document_number,
        "cuil": mask_cuil,
        "mrz_line1": mask_mrz_line,
        "mrz_line2": mask_mrz_line,
        "pdf417_raw": mask_pdf417,
        "tramite": lambda x: f"***{x[-4:]}" if x and len(x) > 4 else "***",
    }
    
    safe_fields = {
        "sexo", "nacionalidad", "codigo_pais", "ejemplar",
    }
    
    for key, value in data.items():
        if key in sensitive_fields:
            sanitized[key] = sensitive_fields[key](value)
        elif key in safe_fields:
            sanitized[key] = value
        elif "fecha" in key.lower():
            sanitized[key] = value
        elif key in ("apellido", "nombre"):
            if value:
                sanitized[key] = f"{value[0]}***" if len(value) > 0 else "***"
            else:
                sanitized[key] = None
        else:
            if isinstance(value, str) and len(value) > 20:
                sanitized[key] = f"[{len(value)} chars]"
            else:
                sanitized[key] = value
    
    return sanitized


def sanitize_event_for_logging(event: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize an event payload for safe logging.
    
    Removes or masks:
    - image / image_ref content
    - extracted_data sensitive fields
    - Any base64 content
    """
    if not event:
        return {}
    
    sanitized = {}
    
    for key, value in event.items():
        if key in ("image", "image_base64"):
            sanitized[key] = mask_base64_image(value)
        elif key == "image_ref":
            sanitized[key] = value
        elif key == "extracted_data" and isinstance(value, dict):
            sanitized[key] = sanitize_extracted_data(value)
        elif key in ("pdf417_raw", "mrz_line1", "mrz_line2"):
            sanitized[key] = mask_mrz_line(value) if "mrz" in key else mask_pdf417(value)
        else:
            sanitized[key] = value
    
    return sanitized


class PIISafeLogger:
    """Wrapper for safe logging with automatic PII sanitization."""
    
    def __init__(self, logger):
        self.logger = logger
    
    def info(self, message: str, extra: Optional[dict] = None):
        safe_extra = sanitize_event_for_logging(extra) if extra else None
        self.logger.info(message, extra=safe_extra)
    
    def warning(self, message: str, extra: Optional[dict] = None):
        safe_extra = sanitize_event_for_logging(extra) if extra else None
        self.logger.warning(message, extra=safe_extra)
    
    def error(self, message: str, extra: Optional[dict] = None):
        safe_extra = sanitize_event_for_logging(extra) if extra else None
        self.logger.error(message, extra=safe_extra)
    
    def debug(self, message: str, extra: Optional[dict] = None):
        safe_extra = sanitize_event_for_logging(extra) if extra else None
        self.logger.debug(message, extra=safe_extra)

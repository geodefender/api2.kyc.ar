import hashlib
from typing import Optional

from kyc_platform.shared.config import DocumentType
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


def generate_idempotency_key(
    client_id: str,
    document_type: DocumentType,
    image_base64: str,
) -> str:
    content = f"{client_id}:{document_type.value}:{image_base64}"
    return hashlib.sha256(content.encode()).hexdigest()


class IdempotencyService:
    def __init__(self, repository):
        self.repository = repository
    
    def check_duplicate(
        self,
        client_id: str,
        document_type: DocumentType,
        image_base64: str,
    ) -> Optional[str]:
        idempotency_key = generate_idempotency_key(client_id, document_type, image_base64)
        
        existing = self.repository.get_by_idempotency_key(idempotency_key)
        
        if existing:
            logger.info(
                "Duplicate request detected",
                extra={
                    "idempotency_key": idempotency_key[:16] + "...",
                    "existing_document_id": existing.document_id,
                },
            )
            return existing.document_id
        
        return None
    
    def get_idempotency_key(
        self,
        client_id: str,
        document_type: DocumentType,
        image_base64: str,
    ) -> str:
        return generate_idempotency_key(client_id, document_type, image_base64)

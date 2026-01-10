import base64
import hashlib
import io
from typing import Optional

from PIL import Image

from kyc_platform.shared.config import DocumentType
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


def normalize_image(image_base64: str) -> bytes:
    """
    Normalize image by:
    1. Decoding base64 to binary
    2. Loading as PIL Image (strips EXIF and other metadata)
    3. Re-encoding as JPEG with consistent quality
    
    This ensures the same visual content produces the same hash,
    regardless of metadata differences.
    """
    try:
        image_data = base64.b64decode(image_base64)
        
        image = Image.open(io.BytesIO(image_data))
        
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=85)
        
        return output.getvalue()
    except Exception as e:
        logger.warning(
            "Failed to normalize image, using raw base64",
            extra={"error": str(e)},
        )
        return image_base64.encode()


def generate_idempotency_key(
    client_id: str,
    document_type: DocumentType,
    image_base64: str,
) -> str:
    """
    Generate idempotency key from:
    - client_id
    - document_type
    - normalized image content (stripped of metadata)
    
    This ensures:
    - Same image with different EXIF = same hash
    - Same image re-encoded = same hash
    - Different clients with same image = different hash
    """
    normalized_image = normalize_image(image_base64)
    image_hash = hashlib.sha256(normalized_image).hexdigest()
    
    content = f"{client_id}:{document_type.value}:{image_hash}"
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
                    "idempotency_key_prefix": idempotency_key[:16],
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

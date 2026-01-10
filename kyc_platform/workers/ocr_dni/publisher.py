from typing import Any

from kyc_platform.contracts.events import EventFactory
from kyc_platform.queue import get_queue
from kyc_platform.shared.config import config, DocumentType
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class DNIPublisher:
    def __init__(self):
        self.queue = get_queue()
    
    def publish_extracted(
        self,
        document_id: str,
        verification_id: str,
        extracted_data: dict[str, Any],
        confidence: float,
        processing_time_ms: int,
        errors: list[str] | None = None,
    ) -> bool:
        event = EventFactory.create_document_extracted(
            document_id=document_id,
            verification_id=verification_id,
            document_type=DocumentType.DNI,
            extracted_data=extracted_data,
            confidence=confidence,
            processing_time_ms=processing_time_ms,
            errors=errors,
        )
        
        success = self.queue.publish(config.QUEUE_EXTRACTED_NAME, event.model_dump())
        
        if success:
            logger.info(
                "Published document.extracted.v1",
                extra={
                    "document_id": document_id,
                    "confidence": confidence,
                },
            )
        
        return success

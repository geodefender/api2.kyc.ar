from typing import Any, Optional

from kyc_platform.contracts.events import EventFactory
from kyc_platform.queue import get_queue
from kyc_platform.shared.config import config, DocumentType
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class LicensePublisher:
    
    def __init__(self):
        self.queue = get_queue()
    
    def publish_extracted(
        self,
        document_id: str,
        verification_id: str,
        extracted_data: dict[str, Any],
        confidence: float,
        processing_time_ms: int,
        errors: Optional[list[str]] = None,
        authenticity_result: Optional[dict[str, Any]] = None,
        liveness_result: Optional[dict[str, Any]] = None,
    ) -> bool:
        event = EventFactory.create_document_extracted(
            document_id=document_id,
            verification_id=verification_id,
            document_type=DocumentType.LICENSE,
            extracted_data=extracted_data,
            confidence=confidence,
            processing_time_ms=processing_time_ms,
            errors=errors,
            authenticity_result=authenticity_result,
            liveness_result=liveness_result,
        )
        
        logger.info(
            f"Publishing document.extracted.v1 to {config.QUEUE_EXTRACTED_NAME}",
            extra={
                "document_id": document_id,
                "confidence": confidence,
            },
        )
        
        return self.queue.publish(config.QUEUE_EXTRACTED_NAME, event.model_dump())

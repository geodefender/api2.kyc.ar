from kyc_platform.contracts.events import EventFactory, DocumentUploadedEvent
from kyc_platform.queue import get_queue
from kyc_platform.shared.config import config, DocumentType
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class EnqueueService:
    def __init__(self):
        self.queue = get_queue()
    
    def enqueue_document_uploaded(
        self,
        document_id: str,
        verification_id: str,
        client_id: str,
        document_type: DocumentType,
        image_ref: str,
    ) -> bool:
        event = EventFactory.create_document_uploaded(
            document_id=document_id,
            verification_id=verification_id,
            client_id=client_id,
            document_type=document_type,
            image_ref=image_ref,
        )
        
        queue_name = config.get_queue_name_for_document_type(document_type)
        
        logger.info(
            f"Enqueueing document.uploaded.v1 to {queue_name}",
            extra={
                "document_id": document_id,
                "document_type": document_type.value,
                "queue": queue_name,
            },
        )
        
        return self.queue.publish(queue_name, event.model_dump())


enqueue_service = EnqueueService()

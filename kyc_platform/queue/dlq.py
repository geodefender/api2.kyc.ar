from typing import Any, Optional
from datetime import datetime

from kyc_platform.queue.base import EventQueue
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class DLQMessage:
    def __init__(
        self,
        original_message: dict[str, Any],
        error_code: str,
        error_message: str,
        stage: str,
        document_id: Optional[str] = None,
        attempt_count: int = 1,
    ):
        self.original_message = original_message
        self.error_code = error_code
        self.error_message = error_message
        self.stage = stage
        self.document_id = document_id
        self.attempt_count = attempt_count
        self.failed_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "dlq_metadata": {
                "error_code": self.error_code,
                "error_message": self.error_message,
                "stage": self.stage,
                "document_id": self.document_id,
                "attempt_count": self.attempt_count,
                "failed_at": self.failed_at,
            },
            "original_message": self.original_message,
        }


class DLQHandler:
    def __init__(self, queue: EventQueue, dlq_suffix: str = "-dlq"):
        self.queue = queue
        self.dlq_suffix = dlq_suffix
    
    def get_dlq_name(self, source_queue: str) -> str:
        return f"{source_queue}{self.dlq_suffix}"
    
    def send_to_dlq(
        self,
        source_queue: str,
        original_message: dict[str, Any],
        error_code: str,
        error_message: str,
        stage: str,
        document_id: Optional[str] = None,
        attempt_count: int = 1,
    ) -> bool:
        dlq_message = DLQMessage(
            original_message=original_message,
            error_code=error_code,
            error_message=error_message,
            stage=stage,
            document_id=document_id,
            attempt_count=attempt_count,
        )
        
        dlq_name = self.get_dlq_name(source_queue)
        
        logger.error(
            "Sending message to DLQ",
            extra={
                "dlq_name": dlq_name,
                "document_id": document_id,
                "error_code": error_code,
                "stage": stage,
                "attempt_count": attempt_count,
            },
        )
        
        return self.queue.publish(dlq_name, dlq_message.to_dict())
    
    def consume_from_dlq(self, source_queue: str, max_messages: int = 10) -> list[dict[str, Any]]:
        dlq_name = self.get_dlq_name(source_queue)
        return self.queue.consume(dlq_name, max_messages)


class WorkerErrorHandler:
    DLQ_THRESHOLD = 3
    
    def __init__(self, queue: EventQueue, source_queue: str):
        self.dlq_handler = DLQHandler(queue)
        self.source_queue = source_queue
    
    def handle_error(
        self,
        message: dict[str, Any],
        error: Exception,
        stage: str,
        document_id: Optional[str] = None,
        attempt_count: int = 1,
    ) -> bool:
        error_code = type(error).__name__
        error_message = str(error)
        
        logger.error(
            f"Worker error in stage {stage}",
            extra={
                "document_id": document_id,
                "error_code": error_code,
                "error_message": error_message,
                "attempt_count": attempt_count,
            },
        )
        
        if attempt_count >= self.DLQ_THRESHOLD:
            return self.dlq_handler.send_to_dlq(
                source_queue=self.source_queue,
                original_message=message,
                error_code=error_code,
                error_message=error_message,
                stage=stage,
                document_id=document_id,
                attempt_count=attempt_count,
            )
        
        return False

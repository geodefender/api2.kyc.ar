from typing import Any, Optional
from datetime import datetime

from kyc_platform.queue.base import EventQueue
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class DLQMessage:
    """Dead Letter Queue message with full error context."""
    
    def __init__(
        self,
        original_message: dict[str, Any],
        error_code: str,
        error_message: str,
        stage: str,
        worker_name: str,
        document_id: Optional[str] = None,
        verification_id: Optional[str] = None,
        attempt_count: int = 1,
        max_receive_count: int = 3,
    ):
        self.original_message = original_message
        self.error_code = error_code
        self.error_message = error_message
        self.stage = stage
        self.worker_name = worker_name
        self.document_id = document_id
        self.verification_id = verification_id
        self.attempt_count = attempt_count
        self.max_receive_count = max_receive_count
        self.failed_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "dlq_metadata": {
                "error_code": self.error_code,
                "error_message": self.error_message,
                "stage": self.stage,
                "worker_name": self.worker_name,
                "document_id": self.document_id,
                "verification_id": self.verification_id,
                "attempt_count": self.attempt_count,
                "max_receive_count": self.max_receive_count,
                "failed_at": self.failed_at,
                "is_final_attempt": self.attempt_count >= self.max_receive_count,
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
        worker_name: str,
        document_id: Optional[str] = None,
        verification_id: Optional[str] = None,
        attempt_count: int = 1,
        max_receive_count: int = 3,
    ) -> bool:
        dlq_message = DLQMessage(
            original_message=original_message,
            error_code=error_code,
            error_message=error_message,
            stage=stage,
            worker_name=worker_name,
            document_id=document_id,
            verification_id=verification_id,
            attempt_count=attempt_count,
            max_receive_count=max_receive_count,
        )
        
        dlq_name = self.get_dlq_name(source_queue)
        
        logger.error(
            "Sending message to DLQ",
            extra={
                "dlq_name": dlq_name,
                "worker_name": worker_name,
                "document_id": document_id,
                "verification_id": verification_id,
                "error_code": error_code,
                "stage": stage,
                "attempt_count": attempt_count,
                "is_final_attempt": attempt_count >= max_receive_count,
            },
        )
        
        return self.queue.publish(dlq_name, dlq_message.to_dict())
    
    def consume_from_dlq(self, source_queue: str, max_messages: int = 10) -> list[dict[str, Any]]:
        dlq_name = self.get_dlq_name(source_queue)
        return self.queue.consume(dlq_name, max_messages)


class WorkerErrorHandler:
    """Handles worker errors with DLQ support and structured logging."""
    
    DEFAULT_MAX_RECEIVE_COUNT = 3
    
    def __init__(
        self,
        queue: EventQueue,
        source_queue: str,
        worker_name: str,
        max_receive_count: int = DEFAULT_MAX_RECEIVE_COUNT,
    ):
        self.dlq_handler = DLQHandler(queue)
        self.source_queue = source_queue
        self.worker_name = worker_name
        self.max_receive_count = max_receive_count
    
    def handle_error(
        self,
        message: dict[str, Any],
        error: Exception,
        stage: str,
        document_id: Optional[str] = None,
        verification_id: Optional[str] = None,
        attempt_count: int = 1,
    ) -> bool:
        """
        Handle a worker error.
        
        Returns True if message was sent to DLQ (final attempt reached).
        Returns False if message should be retried.
        """
        error_code = type(error).__name__
        error_message = str(error)[:500]
        
        logger.error(
            f"Worker error in stage {stage}",
            extra={
                "worker_name": self.worker_name,
                "document_id": document_id,
                "verification_id": verification_id,
                "error_code": error_code,
                "error_message_preview": error_message[:100],
                "attempt_count": attempt_count,
                "max_receive_count": self.max_receive_count,
            },
        )
        
        if attempt_count >= self.max_receive_count:
            return self.dlq_handler.send_to_dlq(
                source_queue=self.source_queue,
                original_message=message,
                error_code=error_code,
                error_message=error_message,
                stage=stage,
                worker_name=self.worker_name,
                document_id=document_id,
                verification_id=verification_id,
                attempt_count=attempt_count,
                max_receive_count=self.max_receive_count,
            )
        
        return False

from abc import ABC, abstractmethod
from typing import Any


class EventQueue(ABC):
    @abstractmethod
    def publish(self, queue_name: str, event: dict[str, Any]) -> bool:
        pass
    
    @abstractmethod
    def consume(self, queue_name: str, max_messages: int = 10) -> list[dict[str, Any]]:
        pass
    
    @abstractmethod
    def delete_message(self, queue_name: str, receipt_handle: str) -> bool:
        pass
    
    @abstractmethod
    def get_queue_size(self, queue_name: str) -> int:
        pass

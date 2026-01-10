import json
import os
import uuid
from typing import Any
from datetime import datetime

from kyc_platform.queue.base import EventQueue
from kyc_platform.shared.config import config
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class MockQueue(EventQueue):
    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir or config.MOCK_QUEUE_DIR
        os.makedirs(self.base_dir, exist_ok=True)
    
    def _get_queue_path(self, queue_name: str) -> str:
        return os.path.join(self.base_dir, f"{queue_name}.json")
    
    def _load_queue(self, queue_name: str) -> list[dict[str, Any]]:
        path = self._get_queue_path(queue_name)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    
    def _save_queue(self, queue_name: str, messages: list[dict[str, Any]]) -> None:
        path = self._get_queue_path(queue_name)
        with open(path, "w") as f:
            json.dump(messages, f, indent=2)
    
    def publish(self, queue_name: str, event: dict[str, Any]) -> bool:
        try:
            messages = self._load_queue(queue_name)
            message = {
                "message_id": str(uuid.uuid4()),
                "receipt_handle": str(uuid.uuid4()),
                "body": event,
                "sent_timestamp": datetime.utcnow().isoformat(),
                "visible": True,
            }
            messages.append(message)
            self._save_queue(queue_name, messages)
            logger.info(f"Published message to queue {queue_name}", extra={"message_id": message["message_id"]})
            return True
        except Exception as e:
            logger.error(f"Failed to publish to queue {queue_name}: {e}")
            return False
    
    def consume(self, queue_name: str, max_messages: int = 10) -> list[dict[str, Any]]:
        messages = self._load_queue(queue_name)
        visible_messages = [m for m in messages if m.get("visible", True)]
        result = visible_messages[:max_messages]
        
        for msg in result:
            msg["visible"] = False
            if "receive_count" not in msg:
                msg["receive_count"] = 1
            else:
                msg["receive_count"] += 1
        self._save_queue(queue_name, messages)
        
        return result
    
    def delete_message(self, queue_name: str, receipt_handle: str) -> bool:
        try:
            messages = self._load_queue(queue_name)
            messages = [m for m in messages if m.get("receipt_handle") != receipt_handle]
            self._save_queue(queue_name, messages)
            logger.info(f"Deleted message from queue {queue_name}", extra={"receipt_handle": receipt_handle})
            return True
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")
            return False
    
    def get_queue_size(self, queue_name: str) -> int:
        messages = self._load_queue(queue_name)
        return len([m for m in messages if m.get("visible", True)])
    
    def make_visible(self, queue_name: str, receipt_handle: str) -> bool:
        try:
            messages = self._load_queue(queue_name)
            for m in messages:
                if m.get("receipt_handle") == receipt_handle:
                    m["visible"] = True
                    break
            self._save_queue(queue_name, messages)
            logger.info(f"Made message visible in queue {queue_name}", extra={"receipt_handle": receipt_handle})
            return True
        except Exception as e:
            logger.error(f"Failed to make message visible: {e}")
            return False
    
    def peek_all(self, queue_name: str) -> list[dict[str, Any]]:
        return self._load_queue(queue_name)
    
    def clear_queue(self, queue_name: str) -> None:
        self._save_queue(queue_name, [])

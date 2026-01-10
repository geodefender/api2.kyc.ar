import json
from typing import Any

from kyc_platform.queue.base import EventQueue
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class SQSQueue(EventQueue):
    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client("sqs", region_name=self.region)
            except ImportError:
                raise RuntimeError("boto3 is required for SQS. Install it with: pip install boto3")
        return self._client
    
    def _get_queue_url(self, queue_name: str) -> str:
        response = self.client.get_queue_url(QueueName=queue_name)
        return response["QueueUrl"]
    
    def publish(self, queue_name: str, event: dict[str, Any]) -> bool:
        try:
            queue_url = self._get_queue_url(queue_name)
            response = self.client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(event),
            )
            logger.info(
                f"Published message to SQS queue {queue_name}",
                extra={"message_id": response["MessageId"]},
            )
            return True
        except Exception as e:
            logger.error(f"Failed to publish to SQS queue {queue_name}: {e}")
            return False
    
    def consume(self, queue_name: str, max_messages: int = 10) -> list[dict[str, Any]]:
        try:
            queue_url = self._get_queue_url(queue_name)
            response = self.client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=min(max_messages, 10),
                WaitTimeSeconds=5,
            )
            
            messages = response.get("Messages", [])
            result = []
            for msg in messages:
                result.append({
                    "message_id": msg["MessageId"],
                    "receipt_handle": msg["ReceiptHandle"],
                    "body": json.loads(msg["Body"]),
                })
            return result
        except Exception as e:
            logger.error(f"Failed to consume from SQS queue {queue_name}: {e}")
            return []
    
    def delete_message(self, queue_name: str, receipt_handle: str) -> bool:
        try:
            queue_url = self._get_queue_url(queue_name)
            self.client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
            )
            logger.info(f"Deleted message from SQS queue {queue_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete message from SQS: {e}")
            return False
    
    def get_queue_size(self, queue_name: str) -> int:
        try:
            queue_url = self._get_queue_url(queue_name)
            response = self.client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=["ApproximateNumberOfMessages"],
            )
            return int(response["Attributes"]["ApproximateNumberOfMessages"])
        except Exception as e:
            logger.error(f"Failed to get queue size: {e}")
            return 0

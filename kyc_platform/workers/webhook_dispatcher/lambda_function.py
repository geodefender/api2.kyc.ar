import json
import hashlib
import hmac
import time
from typing import Any, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from kyc_platform.queue import get_queue
from kyc_platform.queue.dlq import WorkerErrorHandler
from kyc_platform.shared.config import config
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class WebhookConfig:
    MAX_RETRIES: int = 3
    INITIAL_BACKOFF_S: float = 1.0
    MAX_BACKOFF_S: float = 30.0
    TIMEOUT_S: int = 10


def generate_signature(payload: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def send_webhook(
    url: str,
    payload: dict[str, Any],
    secret: str,
    timeout: int = WebhookConfig.TIMEOUT_S,
) -> tuple[bool, Optional[str]]:
    payload_json = json.dumps(payload)
    signature = generate_signature(payload_json, secret)
    
    headers = {
        "Content-Type": "application/json",
        "X-KYC-Signature": f"sha256={signature}",
        "X-KYC-Timestamp": str(int(time.time())),
    }
    
    request = Request(
        url,
        data=payload_json.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    
    try:
        with urlopen(request, timeout=timeout) as response:
            return True, None
    except HTTPError as e:
        return False, f"HTTP {e.code}: {e.reason}"
    except URLError as e:
        return False, f"URL Error: {str(e.reason)}"
    except Exception as e:
        return False, str(e)


def send_with_retry(
    url: str,
    payload: dict[str, Any],
    secret: str,
) -> tuple[bool, int, Optional[str]]:
    backoff = WebhookConfig.INITIAL_BACKOFF_S
    last_error = None
    
    for attempt in range(1, WebhookConfig.MAX_RETRIES + 1):
        success, error = send_webhook(url, payload, secret)
        
        if success:
            logger.info(
                "Webhook delivered successfully",
                extra={
                    "url": url,
                    "attempt": attempt,
                },
            )
            return True, attempt, None
        
        last_error = error
        logger.warning(
            f"Webhook delivery failed, attempt {attempt}/{WebhookConfig.MAX_RETRIES}",
            extra={
                "url": url,
                "error": error,
                "backoff_s": backoff,
            },
        )
        
        if attempt < WebhookConfig.MAX_RETRIES:
            time.sleep(backoff)
            backoff = min(backoff * 2, WebhookConfig.MAX_BACKOFF_S)
    
    return False, WebhookConfig.MAX_RETRIES, last_error


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    logger.info("Webhook Dispatcher received event", extra={"event": event})
    
    if "Records" in event:
        records = event["Records"]
    else:
        records = [{"body": event}]
    
    queue = get_queue()
    error_handler = WorkerErrorHandler(queue, config.QUEUE_EXTRACTED_NAME)
    
    results = []
    
    for record in records:
        if isinstance(record.get("body"), str):
            body = json.loads(record["body"])
        else:
            body = record.get("body", record)
        
        result = process_webhook(body, error_handler)
        results.append(result)
    
    return {
        "statusCode": 200,
        "body": json.dumps({"processed": len(results), "results": results}),
    }


def process_webhook(
    event_body: dict[str, Any],
    error_handler: WorkerErrorHandler,
) -> dict[str, Any]:
    document_id = event_body.get("document_id")
    webhook_url = event_body.get("webhook_url")
    webhook_secret = event_body.get("webhook_secret", "default-secret")
    
    if not webhook_url:
        logger.info("No webhook URL configured, skipping", extra={"document_id": document_id})
        return {"success": True, "skipped": True, "document_id": document_id}
    
    payload = {
        "event": event_body.get("event"),
        "document_id": document_id,
        "verification_id": event_body.get("verification_id"),
        "document_type": event_body.get("document_type"),
        "extracted_data": event_body.get("extracted_data"),
        "confidence": event_body.get("confidence"),
        "processing_time_ms": event_body.get("processing_time_ms"),
        "timestamp": event_body.get("timestamp"),
    }
    
    try:
        success, attempts, error = send_with_retry(webhook_url, payload, webhook_secret)
        
        if success:
            return {
                "success": True,
                "document_id": document_id,
                "attempts": attempts,
            }
        else:
            error_handler.handle_error(
                message=event_body,
                error=Exception(f"Webhook delivery failed: {error}"),
                stage="webhook_delivery",
                document_id=document_id,
                attempt_count=attempts,
            )
            return {
                "success": False,
                "document_id": document_id,
                "error": error,
                "attempts": attempts,
            }
    except Exception as e:
        error_handler.handle_error(
            message=event_body,
            error=e,
            stage="webhook_processing",
            document_id=document_id,
        )
        return {
            "success": False,
            "document_id": document_id,
            "error": str(e),
        }


if __name__ == "__main__":
    test_event = {
        "event": "document.extracted.v1",
        "document_id": "doc_test_123",
        "verification_id": "ver_test_456",
        "document_type": "dni",
        "extracted_data": {"numero_documento": "12345678"},
        "confidence": 0.95,
        "webhook_url": "https://example.com/webhook",
        "webhook_secret": "test-secret",
    }
    result = handler(test_event)
    print(json.dumps(result, indent=2))

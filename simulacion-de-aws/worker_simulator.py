#!/usr/bin/env python3
import json
import sys
import time

sys.path.insert(0, ".")

from kyc_platform.queue import get_queue
from kyc_platform.workers.ocr_dni.lambda_function import handler as dni_handler
from kyc_platform.workers.ocr_passport.lambda_function import handler as passport_handler
from kyc_platform.shared.config import config
from kyc_platform.shared.logging import get_logger

logger = get_logger("aws-simulator")

POLL_INTERVAL_SECONDS = 2
MAX_MESSAGES_PER_POLL = 5


def process_queue(queue, queue_name: str, handler_fn) -> int:
    messages = queue.consume(queue_name, MAX_MESSAGES_PER_POLL)
    
    if not messages:
        return 0
    
    logger.info(f"Processing {len(messages)} message(s) from {queue_name}")
    
    processed_count = 0
    
    for m in messages:
        body_content = m.get("body", {})
        if isinstance(body_content, dict):
            body_str = json.dumps(body_content)
        else:
            body_str = str(body_content)
        
        event = {
            "Records": [
                {
                    "messageId": m.get("message_id", ""),
                    "receiptHandle": m.get("receipt_handle", ""),
                    "body": body_str,
                    "attributes": {
                        "SentTimestamp": m.get("sent_timestamp", ""),
                        "ApproximateReceiveCount": str(m.get("receive_count", 1)),
                    },
                    "messageAttributes": {},
                    "md5OfBody": "",
                    "eventSource": "aws:sqs",
                    "eventSourceARN": f"arn:aws:sqs:us-east-1:000000000000:{queue_name}",
                    "awsRegion": "us-east-1",
                }
            ]
        }
        
        try:
            result = handler_fn(event, None)
            
            queue.delete_message(queue_name, m["receipt_handle"])
            processed_count += 1
            logger.info(f"Successfully processed message from {queue_name}", 
                       extra={"message_id": m.get("message_id")})
            
        except Exception as e:
            logger.error(f"Error processing message from {queue_name}: {e}",
                        extra={"message_id": m.get("message_id")})
            queue.make_visible(queue_name, m["receipt_handle"])
    
    return processed_count


def main():
    if not config.is_local():
        print("ERROR: This simulator only runs in local development mode")
        print("In production, AWS Lambda + SQS handles this automatically")
        sys.exit(1)
    
    print("=" * 60)
    print("AWS SQS/Lambda Simulator")
    print("=" * 60)
    print(f"Poll interval: {POLL_INTERVAL_SECONDS}s")
    print(f"Queues monitored:")
    print(f"  - {config.QUEUE_DNI_NAME}")
    print(f"  - {config.QUEUE_PASSPORT_NAME}")
    print("=" * 60)
    print("Waiting for messages... (Ctrl+C to stop)\n")
    
    queue = get_queue()
    
    try:
        while True:
            dni_count = process_queue(queue, config.QUEUE_DNI_NAME, dni_handler)
            passport_count = process_queue(queue, config.QUEUE_PASSPORT_NAME, passport_handler)
            
            if dni_count == 0 and passport_count == 0:
                pass
            
            time.sleep(POLL_INTERVAL_SECONDS)
            
    except KeyboardInterrupt:
        print("\nSimulator stopped")


if __name__ == "__main__":
    main()

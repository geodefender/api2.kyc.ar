import json
from typing import Any

from kyc_platform.workers.ocr_passport.processor import PassportProcessor
from kyc_platform.workers.ocr_passport.publisher import PassportPublisher
from kyc_platform.persistence import get_repository
from kyc_platform.queue import get_queue, WorkerErrorHandler
from kyc_platform.shared.config import config
from kyc_platform.shared.logging import get_logger
from kyc_platform.shared.pii_sanitizer import sanitize_event_for_logging

logger = get_logger(__name__)

WORKER_NAME = "kyc-worker-ocr-passport"

processor = PassportProcessor()
publisher = PassportPublisher()


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    safe_event = sanitize_event_for_logging(event)
    logger.info("Passport Worker received event", extra={"event": safe_event})
    
    if "Records" in event:
        records = event["Records"]
    else:
        records = [{"body": event}]
    
    queue = get_queue()
    error_handler = WorkerErrorHandler(
        queue=queue,
        source_queue=config.QUEUE_PASSPORT_NAME,
        worker_name=WORKER_NAME,
    )
    
    results = []
    
    for record in records:
        if isinstance(record.get("body"), str):
            body = json.loads(record["body"])
        else:
            body = record.get("body", record)
        
        result = process_single_document(body, error_handler)
        results.append(result)
    
    return {
        "statusCode": 200,
        "body": json.dumps({"processed": len(results), "results": results}),
    }


def process_single_document(
    event_body: dict[str, Any],
    error_handler: WorkerErrorHandler,
) -> dict[str, Any]:
    document_id = event_body.get("document_id")
    verification_id = event_body.get("verification_id")
    image_ref = event_body.get("image_ref")
    
    if not all([document_id, verification_id, image_ref]):
        safe_event = sanitize_event_for_logging(event_body)
        logger.error("Missing required fields in event", extra={"event": safe_event})
        return {"success": False, "error": "Missing required fields"}
    
    logger.info(
        "Processing Passport document",
        extra={"document_id": document_id, "image_ref": image_ref},
    )
    
    repository = get_repository()
    record = repository.get_by_id(document_id)
    if record:
        record.mark_processing()
        repository.update(record)
    
    try:
        result = processor.process(image_ref)
    except Exception as e:
        error_handler.handle_error(
            message=event_body,
            error=e,
            stage="ocr_processing",
            document_id=document_id,
            verification_id=verification_id,
        )
        if record:
            record.mark_failed([str(e)])
            repository.update(record)
        return {
            "success": False,
            "document_id": document_id,
            "errors": [str(e)],
        }
    
    if result["success"]:
        publisher.publish_extracted(
            document_id=document_id,
            verification_id=verification_id,
            extracted_data=result["extracted_data"],
            confidence=result["confidence"],
            processing_time_ms=result["processing_time_ms"],
        )
        
        if record:
            record.mark_extracted(
                extracted_data=result["extracted_data"],
                confidence=result["confidence"],
                processing_time_ms=result["processing_time_ms"],
            )
            repository.update(record)
        
        return {
            "success": True,
            "document_id": document_id,
            "confidence": result["confidence"],
        }
    else:
        errors = result.get("errors", ["Unknown error"])
        
        if record:
            record.mark_failed(errors)
            repository.update(record)
        
        return {
            "success": False,
            "document_id": document_id,
            "errors": errors,
        }


if __name__ == "__main__":
    test_event = {
        "event": "document.uploaded.v1",
        "document_id": "doc_test_passport",
        "verification_id": "ver_test_passport",
        "image_ref": "./data/uploads/test_passport.jpg",
    }
    result = handler(test_event)
    print(json.dumps(result, indent=2))

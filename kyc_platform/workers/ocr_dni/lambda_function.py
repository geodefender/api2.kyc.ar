import json
from typing import Any

from kyc_platform.workers.ocr_dni.processor import DNIProcessor
from kyc_platform.workers.ocr_dni.publisher import DNIPublisher
from kyc_platform.persistence import get_repository
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)

processor = DNIProcessor()
publisher = DNIPublisher()


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    logger.info("DNI Worker received event", extra={"event": event})
    
    if "Records" in event:
        records = event["Records"]
    else:
        records = [{"body": event}]
    
    results = []
    
    for record in records:
        if isinstance(record.get("body"), str):
            body = json.loads(record["body"])
        else:
            body = record.get("body", record)
        
        result = process_single_document(body)
        results.append(result)
    
    return {
        "statusCode": 200,
        "body": json.dumps({"processed": len(results), "results": results}),
    }


def process_single_document(event_body: dict[str, Any]) -> dict[str, Any]:
    document_id = event_body.get("document_id")
    verification_id = event_body.get("verification_id")
    image_ref = event_body.get("image_ref")
    
    if not all([document_id, verification_id, image_ref]):
        logger.error("Missing required fields in event", extra={"event": event_body})
        return {"success": False, "error": "Missing required fields"}
    
    logger.info(
        "Processing DNI document",
        extra={"document_id": document_id, "image_ref": image_ref},
    )
    
    repository = get_repository()
    record = repository.get_by_id(document_id)
    if record:
        record.mark_processing()
        repository.update(record)
    
    result = processor.process(image_ref)
    
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
            "dni_type": result.get("dni_type"),
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
        "document_id": "doc_test_123",
        "verification_id": "ver_test_456",
        "image_ref": "./data/uploads/test.jpg",
    }
    result = handler(test_event)
    print(json.dumps(result, indent=2))

#!/usr/bin/env python3
import json
import base64
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kyc_platform.queue import MockQueue
from kyc_platform.shared.config import config, DocumentType
from kyc_platform.workers.ocr_dni import handler as dni_handler
from kyc_platform.workers.ocr_passport import handler as passport_handler
from kyc_platform.persistence import get_repository


def create_test_image() -> str:
    from PIL import Image, ImageDraw
    
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    
    img = Image.new("RGB", (800, 600), color="white")
    draw = ImageDraw.Draw(img)
    
    draw.rectangle([50, 50, 750, 550], outline="black", width=2)
    draw.text((100, 100), "REPUBLICA ARGENTINA", fill="blue")
    draw.text((100, 150), "DOCUMENTO NACIONAL DE IDENTIDAD", fill="black")
    draw.text((100, 220), "Apellido: PEREZ", fill="black")
    draw.text((100, 260), "Nombre: JUAN CARLOS", fill="black")
    draw.text((100, 300), "DNI: 30123456", fill="black")
    draw.text((100, 340), "Fecha Nacimiento: 15/03/1985", fill="black")
    draw.text((100, 380), "Sexo: M", fill="black")
    draw.text((100, 420), "Nacionalidad: ARGENTINA", fill="black")
    
    test_path = os.path.join(config.UPLOAD_DIR, "test_dni.jpg")
    img.save(test_path)
    
    return test_path


def run_local_pipeline():
    print("=" * 60)
    print("KYC Platform - Local Pipeline Runner")
    print("=" * 60)
    
    queue = MockQueue()
    repository = get_repository()
    
    print("\n[1] Creating test image...")
    test_image_path = create_test_image()
    print(f"    Created: {test_image_path}")
    
    print("\n[2] Simulating POST /documents...")
    
    from kyc_platform.api_handler.services.id_generator import generate_document_id, generate_verification_id
    from kyc_platform.contracts.models import DocumentRecord
    from kyc_platform.contracts.events import EventFactory
    
    document_id = generate_document_id()
    verification_id = generate_verification_id()
    document_type = DocumentType.DNI
    
    record = DocumentRecord(
        document_id=document_id,
        verification_id=verification_id,
        client_id="demo",
        document_type=document_type,
        image_ref=test_image_path,
    )
    repository.save(record)
    record.mark_queued()
    repository.update(record)
    
    print(f"    document_id: {document_id}")
    print(f"    verification_id: {verification_id}")
    print(f"    document_type: {document_type.value}")
    
    event = EventFactory.create_document_uploaded(
        document_id=document_id,
        verification_id=verification_id,
        client_id="demo",
        document_type=document_type,
        image_ref=test_image_path,
    )
    
    queue_name = config.get_queue_name_for_document_type(document_type)
    queue.publish(queue_name, event.model_dump())
    
    print(f"\n[3] Event published to queue: {queue_name}")
    print(f"    Event: document.uploaded.v1")
    
    print("\n[4] Consuming from queue and processing...")
    
    messages = queue.consume(queue_name, max_messages=1)
    if messages:
        message = messages[0]
        event_body = message["body"]
        
        print(f"    Received message: {message['message_id']}")
        
        if document_type == DocumentType.DNI:
            result = dni_handler(event_body)
        else:
            result = passport_handler(event_body)
        
        queue.delete_message(queue_name, message["receipt_handle"])
        
        print(f"\n[5] Worker result:")
        print(json.dumps(json.loads(result["body"]), indent=2))
    else:
        print("    No messages in queue!")
    
    print("\n[6] Checking extracted queue...")
    extracted_messages = queue.peek_all(config.QUEUE_EXTRACTED_NAME)
    if extracted_messages:
        print(f"    Found {len(extracted_messages)} extracted event(s):")
        for msg in extracted_messages:
            print(json.dumps(msg["body"], indent=2))
    else:
        print("    No extracted events found")
    
    print("\n[7] Checking document status in database...")
    final_record = repository.get_by_id(document_id)
    if final_record:
        print(f"    Status: {final_record.status.value}")
        print(f"    Confidence: {final_record.confidence}")
        if final_record.extracted_data:
            print(f"    Extracted Data:")
            print(json.dumps(final_record.extracted_data, indent=6))
    
    print("\n" + "=" * 60)
    print("Pipeline completed successfully!")
    print("=" * 60)


def cleanup():
    queue = MockQueue()
    queue.clear_queue(config.QUEUE_DNI_NAME)
    queue.clear_queue(config.QUEUE_PASSPORT_NAME)
    queue.clear_queue(config.QUEUE_EXTRACTED_NAME)
    print("Queues cleared.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        cleanup()
    else:
        run_local_pipeline()

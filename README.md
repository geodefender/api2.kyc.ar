# KYC Platform - OCR Microservice

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [API Endpoints](#api-endpoints)
5. [Event Contracts](#event-contracts)
6. [Data Models](#data-models)
7. [Queue System](#queue-system)
8. [Workers](#workers)
9. [Security Features](#security-features)
10. [AWS Deployment](#aws-deployment)
11. [Environment Variables](#environment-variables)
12. [Local Development](#local-development)
13. [Dependencies](#dependencies)

---

## Overview

Event-driven microservice platform for OCR processing of Argentine identity documents (DNI and Passport). Designed for AWS Lambda + SQS deployment, fully simulable locally.

### Supported Documents
| Document Type | Subtype | Extraction Method |
|---------------|---------|-------------------|
| DNI | Nuevo (2012+) | PDF417 barcode + OCR fallback |
| DNI | Viejo (pre-2012) | OCR only |
| Passport | Standard | MRZ parsing + OCR fallback |

### Design Principles
- **Event-driven**: Single canonical event per type, routing via queues
- **Stateless workers**: No filtering logic, queue subscription determines processing
- **Idempotent**: Duplicate detection via content hash
- **Fault-tolerant**: DLQ support with structured error logging

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              KYC Platform                                    │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────────┐
                              │   Client App     │
                              └────────┬─────────┘
                                       │
                                       │ POST /documents
                                       │ (image + document_type)
                                       ▼
                    ┌──────────────────────────────────────┐
                    │         kyc-handler-documents        │
                    │           (FastAPI + Lambda)         │
                    │                                      │
                    │  1. Generate idempotency key         │
                    │  2. Check for duplicates             │
                    │  3. Save image to storage            │
                    │  4. Create document record           │
                    │  5. Route to appropriate queue       │
                    └──────────────────┬───────────────────┘
                                       │
                    ┌──────────────────┴───────────────────┐
                    │      document.uploaded.v1 event      │
                    └──────────────────┬───────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
    │  kyc-ocr-dni    │    │ kyc-ocr-passport│    │  kyc-webhook    │
    │     (SQS)       │    │     (SQS)       │    │     (SQS)       │
    └────────┬────────┘    └────────┬────────┘    └────────┬────────┘
             │                      │                      │
             ▼                      ▼                      ▼
    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
    │ kyc-worker-     │    │ kyc-worker-     │    │ kyc-worker-     │
    │ ocr-dni         │    │ ocr-passport    │    │ webhook         │
    │ (Lambda)        │    │ (Lambda)        │    │ (Lambda)        │
    │                 │    │                 │    │                 │
    │ Strategies:     │    │ Strategies:     │    │ Features:       │
    │ - PDF417        │    │ - MRZ parsing   │    │ - HMAC signing  │
    │ - OCR fallback  │    │ - OCR fallback  │    │ - Retry/backoff │
    └────────┬────────┘    └────────┬────────┘    └─────────────────┘
             │                      │
             └──────────┬───────────┘
                        │
                        ▼
              ┌─────────────────┐
              │  kyc-extracted  │
              │     (SQS)       │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  document.      │
              │  extracted.v1   │
              └─────────────────┘

    Error Handling:
    ┌─────────────────┐
    │ kyc-ocr-dni-dlq │ ◄── Failed messages after 3 retries
    │ kyc-ocr-        │
    │ passport-dlq    │
    └─────────────────┘
```

---

## Project Structure

```
kyc_platform/
├── __init__.py
├── api_handler/                    # HTTP API (FastAPI)
│   ├── __init__.py
│   ├── main.py                     # Uvicorn entrypoint (port 5000)
│   ├── routes/
│   │   ├── __init__.py
│   │   └── documents.py            # POST /documents, GET /documents/{id}
│   ├── schemas.py                  # Request/Response models
│   └── services/
│       ├── __init__.py
│       ├── enqueue.py              # Queue publishing service
│       ├── id_generator.py         # doc_*/ver_* ID generation
│       └── idempotency.py          # SHA256 hash generation
│
├── workers/                        # Lambda Workers
│   ├── __init__.py
│   ├── ocr_dni/
│   │   ├── __init__.py
│   │   ├── lambda_function.py      # DNI processing handler
│   │   ├── processor.py            # DNI processing orchestrator
│   │   ├── publisher.py            # Extracted event publisher
│   │   └── strategies/
│   │       ├── __init__.py
│   │       ├── base.py             # Strategy interface
│   │       ├── dni_nuevo.py        # PDF417 + OCR
│   │       └── dni_viejo.py        # OCR only
│   ├── ocr_passport/
│   │   ├── __init__.py
│   │   ├── lambda_function.py      # Passport processing handler
│   │   ├── processor.py            # Passport processing orchestrator
│   │   ├── publisher.py            # Extracted event publisher
│   │   └── strategies/
│   │       ├── __init__.py
│   │       ├── base.py             # Strategy interface
│   │       └── mrz_parser.py       # MRZ extraction
│   └── webhook_dispatcher/
│       ├── __init__.py
│       └── lambda_function.py      # Webhook delivery with HMAC
│
├── queue/                          # Queue Abstraction Layer
│   ├── __init__.py
│   ├── base.py                     # EventQueue interface
│   ├── mock_queue.py               # File-based queue for local dev
│   ├── sqs_queue.py                # AWS SQS implementation
│   └── dlq.py                      # Dead Letter Queue handling
│
├── contracts/                      # Shared Contracts
│   ├── __init__.py
│   ├── events.py                   # Event definitions (Pydantic)
│   └── models.py                   # Domain models
│
├── persistence/                    # Data Persistence
│   ├── __init__.py
│   ├── base.py                     # Repository interface
│   └── sqlite_repository.py        # SQLite implementation
│
├── runner/                         # Local Testing
│   ├── __init__.py
│   └── local_pipeline.py           # End-to-end simulation
│
└── shared/                         # Cross-cutting Concerns
    ├── __init__.py
    ├── config.py                   # Environment configuration
    ├── aws_config.py               # Lambda memory/timeout settings
    └── logging.py                  # Structured JSON logging
```

---

## API Endpoints

### POST /documents
Upload a document for OCR processing.

**Request:**
```json
{
  "client_id": "client_abc123",
  "document_type": "dni",
  "image": "<base64-encoded-image>",
  "webhook_url": "https://example.com/webhook",
  "webhook_secret": "your-secret-key"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| client_id | string | Yes | Client identifier for grouping documents |
| document_type | enum | Yes | `dni` or `passport` |
| image | string | Yes | Base64-encoded image (JPEG/PNG) |
| webhook_url | string | No | URL for result notification |
| webhook_secret | string | No | Secret for HMAC signature |

**Response (201 Created):**
```json
{
  "ok": true,
  "document_id": "doc_1736523845123_a1b2c3d4",
  "verification_id": "ver_1736523845123_e5f6g7h8",
  "status": "queued"
}
```

**Response (409 Conflict - Duplicate):**
```json
{
  "ok": true,
  "document_id": "doc_1736523845123_a1b2c3d4",
  "verification_id": "ver_1736523845123_e5f6g7h8",
  "status": "extracted"
}
```

### GET /documents/{document_id}
Get document processing status.

**Response (200 OK):**
```json
{
  "document_id": "doc_1736523845123_a1b2c3d4",
  "verification_id": "ver_1736523845123_e5f6g7h8",
  "document_type": "dni",
  "status": "extracted",
  "extracted_data": {
    "numero_documento": "12345678",
    "apellido": "GONZALEZ",
    "nombre": "JUAN CARLOS",
    "sexo": "M",
    "nacionalidad": "ARG",
    "fecha_nacimiento": "15/03/1985",
    "fecha_emision": "01/01/2020",
    "fecha_vencimiento": "01/01/2035"
  },
  "confidence": 0.95,
  "processing_time_ms": 2450,
  "errors": null
}
```

**Status Values:**
| Status | Description |
|--------|-------------|
| pending | Document received, not yet queued |
| queued | Document queued for processing |
| processing | OCR extraction in progress |
| extracted | Extraction completed successfully |
| failed | Extraction failed (see errors field) |

### GET /health
Health check endpoint.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "kyc-api-handler"
}
```

---

## Event Contracts

### document.uploaded.v1
Published when a document is uploaded and queued for processing.

```json
{
  "event": "document.uploaded.v1",
  "timestamp": "2026-01-10T14:30:00.000000",
  "version": "1",
  "document_id": "doc_1736523845123_a1b2c3d4",
  "verification_id": "ver_1736523845123_e5f6g7h8",
  "client_id": "client_abc123",
  "document_type": "dni",
  "image_ref": "./data/uploads/doc_1736523845123_a1b2c3d4.jpg"
}
```

| Field | Type | Description |
|-------|------|-------------|
| event | string | Event type identifier |
| timestamp | ISO 8601 | UTC timestamp of event creation |
| version | string | Event schema version |
| document_id | string | Unique document identifier |
| verification_id | string | Verification session identifier |
| client_id | string | Client identifier |
| document_type | enum | `dni` or `passport` |
| image_ref | string | Path/URL to stored image |

### document.extracted.v1
Published when OCR extraction completes.

```json
{
  "event": "document.extracted.v1",
  "timestamp": "2026-01-10T14:30:05.000000",
  "version": "1",
  "document_id": "doc_1736523845123_a1b2c3d4",
  "verification_id": "ver_1736523845123_e5f6g7h8",
  "document_type": "dni",
  "extracted_data": {
    "numero_documento": "12345678",
    "apellido": "GONZALEZ",
    "nombre": "JUAN CARLOS"
  },
  "confidence": 0.95,
  "processing_time_ms": 2450,
  "errors": null
}
```

---

## Data Models

### DNI Data (Extracted Fields)
```json
{
  "numero_documento": "12345678",
  "apellido": "GONZALEZ",
  "nombre": "JUAN CARLOS",
  "sexo": "M",
  "nacionalidad": "ARG",
  "fecha_nacimiento": "15/03/1985",
  "fecha_emision": "01/01/2020",
  "fecha_vencimiento": "01/01/2035",
  "ejemplar": "A",
  "tramite": "00123456789",
  "cuil": "20-12345678-9",
  "pdf417_raw": "<raw-barcode-data>"
}
```

### Passport Data (Extracted Fields)
```json
{
  "numero_pasaporte": "AAA123456",
  "apellido": "GONZALEZ",
  "nombre": "JUAN CARLOS",
  "nacionalidad": "ARG",
  "fecha_nacimiento": "15/03/1985",
  "sexo": "M",
  "fecha_vencimiento": "01/01/2035",
  "codigo_pais": "ARG",
  "mrz_line1": "P<ARGGONZALEZ<<JUAN<CARLOS<<<<<<<<<<<<<<<<<<",
  "mrz_line2": "AAA1234560ARG8503151M3501017<<<<<<<<<<<<<<00"
}
```

### Document Record (Persistence)
```json
{
  "document_id": "doc_1736523845123_a1b2c3d4",
  "verification_id": "ver_1736523845123_e5f6g7h8",
  "client_id": "client_abc123",
  "document_type": "dni",
  "status": "extracted",
  "image_ref": "./data/uploads/doc_1736523845123_a1b2c3d4.jpg",
  "created_at": "2026-01-10T14:30:00.000000",
  "updated_at": "2026-01-10T14:30:05.000000",
  "extracted_data": {},
  "confidence": 0.95,
  "processing_time_ms": 2450,
  "errors": null,
  "idempotency_key": "sha256:a1b2c3d4..."
}
```

---

## Queue System

### Queue Names
| Queue | Purpose | Consumer |
|-------|---------|----------|
| kyc-ocr-dni | DNI processing jobs | kyc-worker-ocr-dni |
| kyc-ocr-passport | Passport processing jobs | kyc-worker-ocr-passport |
| kyc-extracted | Extraction results | Downstream services |
| kyc-webhook | Webhook notifications | kyc-worker-webhook |
| kyc-ocr-dni-dlq | Failed DNI jobs | Manual review |
| kyc-ocr-passport-dlq | Failed passport jobs | Manual review |

### Routing Logic
```python
def get_queue_name_for_document_type(document_type: DocumentType) -> str:
    mapping = {
        DocumentType.DNI: "kyc-ocr-dni",
        DocumentType.PASSPORT: "kyc-ocr-passport",
    }
    return mapping[document_type]
```

### Queue Interface
```python
class EventQueue(ABC):
    @abstractmethod
    def publish(self, queue_name: str, message: dict) -> bool:
        pass
    
    @abstractmethod
    def consume(self, queue_name: str, max_messages: int = 10) -> list[dict]:
        pass
    
    @abstractmethod
    def delete(self, queue_name: str, receipt_handle: str) -> bool:
        pass
```

---

## Workers

### DNI Worker (kyc-worker-ocr-dni)

**Strategies:**

1. **DNI Nuevo (2012+)**
   - Primary: PDF417 barcode extraction using `pyzbar`
   - Fallback: OCR using `pytesseract`
   - Barcode contains all personal data in structured format

2. **DNI Viejo (pre-2012)**
   - OCR only extraction
   - Field detection via regex patterns

**Processing Flow:**
```
1. Load image from image_ref
2. Detect DNI type (nuevo/viejo) based on image features
3. Apply appropriate strategy
4. Publish document.extracted.v1 to kyc-extracted queue
5. Update document record in persistence
```

### Passport Worker (kyc-worker-ocr-passport)

**Strategies:**

1. **MRZ Parser**
   - Extract Machine Readable Zone (2 lines at bottom)
   - Parse according to ICAO 9303 standard
   - Validate check digits

2. **OCR Fallback**
   - Full page OCR if MRZ extraction fails
   - Field detection via regex patterns

### Webhook Dispatcher (kyc-worker-webhook)

**Features:**
- HMAC-SHA256 signature for payload verification
- Exponential backoff retry (3 attempts)
- Headers: `X-KYC-Signature`, `X-KYC-Timestamp`

**Webhook Payload:**
```json
{
  "event": "document.extracted.v1",
  "document_id": "doc_1736523845123_a1b2c3d4",
  "verification_id": "ver_1736523845123_e5f6g7h8",
  "document_type": "dni",
  "extracted_data": {},
  "confidence": 0.95,
  "processing_time_ms": 2450,
  "timestamp": "2026-01-10T14:30:05.000000"
}
```

**Signature Verification (Client-side):**
```python
import hmac
import hashlib

def verify_signature(payload: str, secret: str, signature: str) -> bool:
    expected = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

---

## Security Features

### 1. Idempotency
Prevents duplicate processing of the same document.

**Key Generation:**
```python
def generate_idempotency_key(client_id: str, document_type: str, image_base64: str) -> str:
    content = f"{client_id}:{document_type}:{image_base64}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
```

**Behavior:**
- If idempotency key exists, return existing document
- If new, process normally and store key

### 2. Dead Letter Queue (DLQ)
Failed messages after 3 retries are sent to DLQ with metadata.

**DLQ Message Structure:**
```json
{
  "dlq_metadata": {
    "error_code": "OCRExtractionError",
    "error_message": "Failed to extract text from image",
    "stage": "ocr_processing",
    "document_id": "doc_123",
    "attempt_count": 3,
    "failed_at": "2026-01-10T14:35:00.000000"
  },
  "original_message": {
    "event": "document.uploaded.v1",
    "..."
  }
}
```

### 3. Webhook HMAC Signing
All webhook payloads are signed with HMAC-SHA256.

**Headers:**
| Header | Description |
|--------|-------------|
| X-KYC-Signature | `sha256=<hex-digest>` |
| X-KYC-Timestamp | Unix timestamp of signature |

### 4. Input Validation
- Base64 image validation before processing
- Document type enum validation
- Request size limits (configurable)

---

## AWS Deployment

### Lambda Configuration
| Lambda | Memory | Timeout | Trigger |
|--------|--------|---------|---------|
| kyc-handler-documents | 512 MB | 10s | API Gateway |
| kyc-worker-ocr-dni | 2048 MB | 180s | SQS (kyc-ocr-dni) |
| kyc-worker-ocr-passport | 2048 MB | 180s | SQS (kyc-ocr-passport) |
| kyc-worker-webhook | 256 MB | 30s | SQS (kyc-extracted) |

### SQS Configuration
| Queue | Visibility Timeout | Message Retention | DLQ |
|-------|-------------------|-------------------|-----|
| kyc-ocr-dni | 200s | 4 days | kyc-ocr-dni-dlq (3 receives) |
| kyc-ocr-passport | 200s | 4 days | kyc-ocr-passport-dlq (3 receives) |
| kyc-extracted | 60s | 4 days | None |
| kyc-webhook | 60s | 4 days | None |

### IAM Permissions (Minimum Required)

**kyc-handler-documents:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage"
      ],
      "Resource": [
        "arn:aws:sqs:*:*:kyc-ocr-dni",
        "arn:aws:sqs:*:*:kyc-ocr-passport"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::kyc-documents-bucket/*"
    }
  ]
}
```

**kyc-worker-ocr-*:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:*:*:kyc-ocr-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage"
      ],
      "Resource": [
        "arn:aws:sqs:*:*:kyc-extracted",
        "arn:aws:sqs:*:*:kyc-ocr-*-dlq"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::kyc-documents-bucket/*"
    }
  ]
}
```

### Infrastructure as Code (Terraform Example)
```hcl
module "kyc_platform" {
  source = "./modules/kyc"
  
  environment     = "production"
  service_prefix  = "kyc"
  
  handler_memory  = 512
  handler_timeout = 10
  
  worker_memory   = 2048
  worker_timeout  = 180
  
  dlq_max_receive_count = 3
}
```

---

## Environment Variables

### Application Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| KYC_ENVIRONMENT | local | `local` or `aws` |
| SERVICE_PREFIX | kyc | Prefix for all AWS resources |
| LOG_LEVEL | INFO | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Queue Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| QUEUE_DNI_NAME | kyc-ocr-dni | DNI processing queue |
| QUEUE_PASSPORT_NAME | kyc-ocr-passport | Passport processing queue |
| QUEUE_EXTRACTED_NAME | kyc-extracted | Extraction results queue |
| QUEUE_WEBHOOK_NAME | kyc-webhook | Webhook dispatch queue |

### Storage Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| MOCK_QUEUE_DIR | ./data/queues | Local queue storage |
| SQLITE_DB_PATH | ./data/kyc.db | Local database path |
| UPLOAD_DIR | ./data/uploads | Image upload directory |

### AWS Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| AWS_REGION | us-east-1 | AWS region |
| HANDLER_MEMORY_MB | 512 | Handler Lambda memory |
| HANDLER_TIMEOUT_S | 10 | Handler Lambda timeout |
| OCR_DNI_MEMORY_MB | 2048 | DNI worker memory |
| OCR_DNI_TIMEOUT_S | 180 | DNI worker timeout |
| OCR_PASSPORT_MEMORY_MB | 2048 | Passport worker memory |
| OCR_PASSPORT_TIMEOUT_S | 180 | Passport worker timeout |
| WEBHOOK_MEMORY_MB | 256 | Webhook worker memory |
| WEBHOOK_TIMEOUT_S | 30 | Webhook worker timeout |
| DLQ_MAX_RECEIVE_COUNT | 3 | Retries before DLQ |

---

## Local Development

### Prerequisites
- Python 3.11+
- Tesseract OCR (`apt install tesseract-ocr`)
- ZBar library for PDF417 (`apt install libzbar0`)

### Running the API Server
```bash
python -m kyc_platform.api_handler.main
```
Server runs on `http://0.0.0.0:5000`

### Running the Local Pipeline
Simulates the full flow: upload -> queue -> worker -> extraction
```bash
python -m kyc_platform.runner.local_pipeline
```

### Testing the API
```bash
# Upload a document
curl -X POST http://localhost:5000/documents \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "test-client",
    "document_type": "dni",
    "image": "<base64-image>"
  }'

# Check status
curl http://localhost:5000/documents/doc_123

# Health check
curl http://localhost:5000/health
```

### Mock Queue Behavior
In local mode, queues are simulated using JSON files in `./data/queues/`:
```
data/queues/
├── kyc-ocr-dni.json
├── kyc-ocr-passport.json
├── kyc-extracted.json
└── kyc-webhook.json
```

---

## Dependencies

### Python Packages
| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | ^0.100 | HTTP API framework |
| uvicorn | ^0.22 | ASGI server |
| pydantic | ^2.0 | Data validation |
| pytesseract | ^0.3 | OCR engine wrapper |
| pyzbar | ^0.1 | PDF417 barcode reader |
| pillow | ^10.0 | Image processing |
| mangum | ^0.17 | Lambda adapter |
| python-multipart | ^0.0.6 | File upload handling |

### System Dependencies
| Package | Purpose |
|---------|---------|
| tesseract-ocr | OCR engine |
| tesseract-ocr-spa | Spanish language pack |
| libzbar0 | Barcode reading library |

### Installation
```bash
# Python packages
pip install fastapi uvicorn pydantic pytesseract pyzbar pillow mangum python-multipart

# System packages (Debian/Ubuntu)
apt install tesseract-ocr tesseract-ocr-spa libzbar0
```

---

## Changelog

### January 2026
- Initial release
- DNI (nuevo/viejo) and Passport support
- Idempotency via SHA256 hash
- DLQ support with structured logging
- Webhook dispatcher with HMAC signing
- AWS-ready architecture with Lambda + SQS
- Local simulation mode for development

---

## License

Proprietary - All rights reserved.

---

## Contact

For technical questions or audit clarifications, contact the development team.

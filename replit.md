# KYC Platform - OCR Microservice

## Overview
Microservicio event-driven en Python para procesamiento OCR de documentos de identidad argentinos (DNI y Pasaporte). Arquitectura diseñada para AWS Lambda + SQS, simulable completamente en local.

## Recent Changes
- January 2026: Initial project setup
- Added idempotency support (hash de imagen + client_id + document_type)
- Added DLQ (Dead Letter Queue) support with structured error logging
- Added webhook dispatcher worker with HMAC signature and retries
- Updated naming convention to `kyc-*` for AWS resources
- Added AWS configuration for memory/timeout per Lambda
- **Audit improvements (Jan 10, 2026)**:
  - Enhanced idempotency: Image normalization via Pillow (strips EXIF) before hashing
  - Enhanced DLQ: Added worker_name, verification_id, max_receive_count, is_final_attempt
  - Explicit state machine: queued → processing → extracted/failed lifecycle
  - PII sanitization: Masking for document numbers, CUIL, MRZ, PDF417, base64 images

## User Preferences
- Language: Spanish for communication, English for code
- Architecture: Event-driven, Lambda-ready
- Persistence: SQLite for development, designed for DynamoDB/RDS in production
- Queue: Mock local queue, designed for AWS SQS

## Project Architecture

### Structure
```
kyc_platform/
├── api_handler/          # FastAPI Handler (port 5000)
├── workers/
│   ├── ocr_dni/          # DNI Worker (PDF417 + OCR)
│   ├── ocr_passport/     # Passport Worker (MRZ)
│   └── webhook_dispatcher/ # Webhook notifications
├── queue/                # EventQueue abstraction + DLQ
├── contracts/            # Events + Models
├── persistence/          # SQLite repository
├── runner/               # Local pipeline simulation
└── shared/               # Config + Logging + AWS Config
```

### Key Files
- `kyc_platform/api_handler/main.py` - FastAPI entrypoint
- `kyc_platform/workers/ocr_dni/lambda_function.py` - DNI Lambda handler
- `kyc_platform/workers/ocr_passport/lambda_function.py` - Passport Lambda handler
- `kyc_platform/workers/webhook_dispatcher/lambda_function.py` - Webhook Lambda handler
- `kyc_platform/runner/local_pipeline.py` - End-to-end simulation

### Running
- API Server: `python -m kyc_platform.api_handler.main`
- Local Pipeline: `python -m kyc_platform.runner.local_pipeline`

### AWS Resource Naming
- Lambdas: `kyc-handler-documents`, `kyc-worker-ocr-dni`, `kyc-worker-ocr-passport`, `kyc-worker-webhook`
- SQS Queues: `kyc-ocr-dni`, `kyc-ocr-passport`, `kyc-extracted`, `kyc-webhook`
- DLQ: `kyc-ocr-dni-dlq`, `kyc-ocr-passport-dlq`

### Production Features
- Idempotency: Duplicate detection via SHA256 hash (with EXIF normalization)
- DLQ: Dead letter queue with enhanced metadata (worker_name, verification_id, attempt tracking)
- Webhook: HMAC-signed notifications with retry/backoff
- State Machine: Explicit queued → processing → extracted/failed transitions
- PII Sanitization: Safe logging with masked sensitive data
- Configurable timeouts and memory per Lambda

### Dependencies
- FastAPI + Uvicorn (API)
- pytesseract (OCR)
- pyzbar (PDF417 barcode)
- Pillow (Image processing)
- Mangum (Lambda adapter)

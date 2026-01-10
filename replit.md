# KYC Platform - OCR Microservice

## Overview
Microservicio event-driven en Python para procesamiento OCR de documentos de identidad argentinos (DNI, Pasaporte y Licencia de conducir). Arquitectura diseñada para AWS Lambda + SQS, simulable completamente en local. Incluye detección de autenticidad y liveness de documentos como features opcionales.

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
- **Heuristic DNI detection (Jan 10, 2026)**:
  - Added preprocess/normalize.py: auto-rotate, deskew, trim, resize, CLAHE
  - Added heuristics/dni_heuristic_analyzer.py: PDF417, MRZ, front, old scoring
  - New strategies: dni_new_front.py, dni_new_back.py, dni_old.py
  - Modified processor.py: heuristic detection BEFORE OCR, strategy selection by variant
- **Strategy standardization (Jan 10, 2026)**:
  - All strategies now return `{source, fields, confidence}` format
  - source values: "pdf417", "ocr", "ocr_fallback", "error", "none"
  - normalize_image: each step wrapped with try/except, always returns valid image
- **Text normalization improvements (Jan 10, 2026)**:
  - Added text_normalizers.py module with specialized extraction helpers
  - normalize_document_number(): removes dots/spaces (33.116.561 → 33116561)
  - normalize_bilingual_date(): converts AGO/AUG → 08 for bilingual dates
  - extract_value_after_label(): handles label/value on separate lines
  - Improved document number extraction prioritizing XX.XXX.XXX format
  - Real DNI testing: 5-7 fields extracted, 0.85-0.90 confidence
- **PDF417 decoder upgrade (Jan 10, 2026)**:
  - Replaced pyzbar with pdf417decoder (pure Python, no zbar dependency)
  - pdf417decoder handles both DNI Nuevo and DNI Antiguo barcode formats
  - Added dual-format parser: new format (tramite@apellido@...) and old format (@dni@ejemplar@...)
  - DNI Nuevo front: extracts tramite, apellido, nombre, sexo, numero_documento, ejemplar, fechas
  - DNI Antiguo back: extracts numero_documento, ejemplar, apellido, nombre, nacionalidad, sexo, cuil, fechas
  - Successfully tested with real DNI images: 9-10 fields extracted, 0.85-0.90 confidence
- **Authenticity & Liveness Detection (Jan 10, 2026)**:
  - Added AuthenticityAnalyzer: saturation, Laplacian sharpness, glare, moiré pattern detection
  - Added DocumentLivenessAnalyzer: multi-frame analysis for hologram/reflection changes
  - New API parameters: check_authenticity, check_document_liveness, frames (array of base64)
  - Returns authenticity_score, liveness_score, and diagnostic flags in extracted_data
- **License document support (Jan 10, 2026)**:
  - Added LICENSE document type to config
  - Created ocr_license worker with Argentina-specific field extraction
  - Extracts: numero_licencia, numero_documento, apellido, nombre, fechas, clase, grupo_sanguineo
  - Updated worker_simulator to handle kyc-ocr-license queue

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
│   │   ├── preprocess/   # Image normalization (deskew, CLAHE, trim)
│   │   ├── heuristics/   # Document detection + authenticity + liveness analyzers
│   │   └── strategies/   # OCR strategies per variant
│   ├── ocr_passport/     # Passport Worker (MRZ)
│   ├── ocr_license/      # License Worker (Argentina)
│   └── webhook_dispatcher/ # Webhook notifications
├── queue/                # EventQueue abstraction + DLQ
├── contracts/            # Events + Models
├── persistence/          # SQLite repository
├── runner/               # Local pipeline simulation
└── shared/               # Config + Logging + AWS Config + PII Sanitizer
```

### Key Files
- `kyc_platform/api_handler/main.py` - FastAPI entrypoint
- `kyc_platform/workers/ocr_dni/lambda_function.py` - DNI Lambda handler
- `kyc_platform/workers/ocr_passport/lambda_function.py` - Passport Lambda handler
- `kyc_platform/workers/ocr_license/lambda_function.py` - License Lambda handler
- `kyc_platform/workers/ocr_dni/heuristics/authenticity_analyzer.py` - Authenticity checks
- `kyc_platform/workers/ocr_dni/heuristics/document_liveness_analyzer.py` - Liveness checks
- `kyc_platform/workers/webhook_dispatcher/lambda_function.py` - Webhook Lambda handler
- `kyc_platform/runner/local_pipeline.py` - End-to-end simulation

### Running
- API Server: `python -m kyc_platform.api_handler.main`
- AWS Simulator: `python simulacion-de-aws/worker_simulator.py`
- Local Pipeline: `python -m kyc_platform.runner.local_pipeline`

### Local Development Flow
1. Start both workflows: "KYC API Server" and "AWS Simulator"
2. POST `/documents` to upload a document
3. The simulator automatically processes the queue every 2 seconds
4. GET `/documents/{id}` to check status and extracted data

### AWS Resource Naming
- Lambdas: `kyc-handler-documents`, `kyc-worker-ocr-dni`, `kyc-worker-ocr-passport`, `kyc-worker-ocr-license`, `kyc-worker-webhook`
- SQS Queues: `kyc-ocr-dni`, `kyc-ocr-passport`, `kyc-ocr-license`, `kyc-extracted`, `kyc-webhook`
- DLQ: `kyc-ocr-dni-dlq`, `kyc-ocr-passport-dlq`, `kyc-ocr-license-dlq`

### Production Features
- Idempotency: Duplicate detection via SHA256 hash (with EXIF normalization)
- DLQ: Dead letter queue with enhanced metadata (worker_name, verification_id, attempt tracking)
- Webhook: HMAC-signed notifications with retry/backoff
- State Machine: Explicit queued → processing → extracted/failed transitions
- PII Sanitization: Safe logging with masked sensitive data
- Heuristic Detection: Document variant detection (dni_new_front, dni_new_back, dni_old) before OCR
- Image Preprocessing: Auto-rotate, deskew, CLAHE, margin trim, contour detection
- Configurable timeouts and memory per Lambda
- **Authenticity Detection** (optional): Saturation, sharpness, glare, moiré analysis via `check_authenticity`
- **Document Liveness** (optional): Multi-frame hologram/reflection analysis via `check_document_liveness` + `frames`

### API Optional Parameters
- `check_authenticity: bool` - Enable photocopy/screen capture detection
- `check_document_liveness: bool` - Enable multi-frame document liveness check
- `frames: list[str]` - Array of 3-5 base64 images at different angles (required for liveness)

### Dependencies
- FastAPI + Uvicorn (API)
- pytesseract (OCR)
- pdf417decoder (PDF417 barcode - pure Python, no zbar)
- Pillow (Image processing)
- OpenCV-headless (Image preprocessing, heuristics)
- Mangum (Lambda adapter)

# KYC Platform - OCR Microservice

## Overview
Microservicio event-driven en Python para procesamiento OCR de documentos de identidad argentinos (DNI y Pasaporte). Arquitectura diseñada para AWS Lambda + SQS, simulable completamente en local.

## Recent Changes
- Initial project setup (January 2026)
- Implemented full monorepo structure with Handler + Workers + Queue abstraction
- Added SQLite persistence layer
- Created DNI and Passport OCR strategies

## User Preferences
- Language: Spanish for communication, English for code
- Architecture: Event-driven, Lambda-ready
- Persistence: SQLite for development, designed for DynamoDB/RDS in production
- Queue: Mock local queue, designed for AWS SQS

## Project Architecture

### Structure
```
kyc_platform/
├── api_handler/      # FastAPI Handler (port 5000)
├── workers/
│   ├── ocr_dni/      # DNI Worker (PDF417 + OCR)
│   └── ocr_passport/ # Passport Worker (MRZ)
├── queue/            # EventQueue abstraction
├── contracts/        # Events + Models
├── persistence/      # SQLite repository
├── runner/           # Local pipeline simulation
└── shared/           # Config + Logging
```

### Key Files
- `kyc_platform/api_handler/main.py` - FastAPI entrypoint
- `kyc_platform/workers/ocr_dni/lambda_function.py` - DNI Lambda handler
- `kyc_platform/workers/ocr_passport/lambda_function.py` - Passport Lambda handler
- `kyc_platform/runner/local_pipeline.py` - End-to-end simulation

### Running
- API Server: `python -m kyc_platform.api_handler.main`
- Local Pipeline: `python -m kyc_platform.runner.local_pipeline`

### Dependencies
- FastAPI + Uvicorn (API)
- pytesseract (OCR)
- pyzbar (PDF417 barcode)
- Pillow (Image processing)
- Mangum (Lambda adapter)

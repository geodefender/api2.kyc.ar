from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from kyc_platform.api_handler.routes.documents import router as documents_router
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("KYC Platform API started")
    yield
    logger.info("KYC Platform API shutting down")


app = FastAPI(
    title="KYC Platform API",
    description="""
## Overview
Event-driven microservice for OCR processing of Argentine identity documents (DNI and Passport).

## Features
- **Document Upload**: Submit documents for OCR extraction
- **Status Tracking**: Query processing status and extracted data
- **Idempotency**: Duplicate detection via content hash
- **Webhooks**: Optional result notification via HMAC-signed webhooks

## Supported Documents
- **DNI Nuevo** (2012+): PDF417 barcode + OCR fallback
- **DNI Viejo** (pre-2012): OCR extraction
- **Passport**: MRZ parsing + OCR fallback

## Authentication
Currently open for development. Production deployments should implement API key or OAuth2.
    """,
    version="1.0.0",
    lifespan=lifespan,
    contact={
        "name": "KYC Platform Team",
        "email": "kyc-support@example.com",
    },
    license_info={
        "name": "Proprietary",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router, tags=["Documents"])

handler = Mangum(app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)

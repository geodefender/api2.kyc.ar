import os
from enum import Enum


class Environment(str, Enum):
    LOCAL = "local"
    AWS = "aws"


class DocumentType(str, Enum):
    DNI = "dni"
    PASSPORT = "passport"
    LICENSE = "license"


class Config:
    ENVIRONMENT: Environment = Environment(os.getenv("KYC_ENVIRONMENT", "local"))
    
    SERVICE_PREFIX: str = os.getenv("SERVICE_PREFIX", "kyc")
    
    QUEUE_DNI_NAME: str = os.getenv("QUEUE_DNI_NAME", f"{SERVICE_PREFIX}-ocr-dni")
    QUEUE_PASSPORT_NAME: str = os.getenv("QUEUE_PASSPORT_NAME", f"{SERVICE_PREFIX}-ocr-passport")
    QUEUE_LICENSE_NAME: str = os.getenv("QUEUE_LICENSE_NAME", f"{SERVICE_PREFIX}-ocr-license")
    QUEUE_EXTRACTED_NAME: str = os.getenv("QUEUE_EXTRACTED_NAME", f"{SERVICE_PREFIX}-extracted")
    QUEUE_WEBHOOK_NAME: str = os.getenv("QUEUE_WEBHOOK_NAME", f"{SERVICE_PREFIX}-webhook")
    
    LAMBDA_HANDLER_NAME: str = os.getenv("LAMBDA_HANDLER_NAME", f"{SERVICE_PREFIX}-handler-documents")
    LAMBDA_OCR_DNI_NAME: str = os.getenv("LAMBDA_OCR_DNI_NAME", f"{SERVICE_PREFIX}-worker-ocr-dni")
    LAMBDA_OCR_PASSPORT_NAME: str = os.getenv("LAMBDA_OCR_PASSPORT_NAME", f"{SERVICE_PREFIX}-worker-ocr-passport")
    LAMBDA_WEBHOOK_NAME: str = os.getenv("LAMBDA_WEBHOOK_NAME", f"{SERVICE_PREFIX}-worker-webhook")
    
    MOCK_QUEUE_DIR: str = os.getenv("MOCK_QUEUE_DIR", "./data/queues")
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "./data/kyc.db")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./data/uploads")
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def get_queue_name_for_document_type(cls, document_type: DocumentType) -> str:
        mapping = {
            DocumentType.DNI: cls.QUEUE_DNI_NAME,
            DocumentType.PASSPORT: cls.QUEUE_PASSPORT_NAME,
            DocumentType.LICENSE: cls.QUEUE_LICENSE_NAME,
        }
        return mapping[document_type]
    
    @classmethod
    def is_local(cls) -> bool:
        return cls.ENVIRONMENT == Environment.LOCAL
    
    @classmethod
    def is_aws(cls) -> bool:
        return cls.ENVIRONMENT == Environment.AWS


config = Config()

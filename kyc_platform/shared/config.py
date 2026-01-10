import os
from enum import Enum


class Environment(str, Enum):
    LOCAL = "local"
    AWS = "aws"


class DocumentType(str, Enum):
    DNI = "dni"
    PASSPORT = "passport"


class Config:
    ENVIRONMENT: Environment = Environment(os.getenv("KYC_ENVIRONMENT", "local"))
    
    QUEUE_DNI_NAME: str = os.getenv("QUEUE_DNI_NAME", "queue-ocr-dni")
    QUEUE_PASSPORT_NAME: str = os.getenv("QUEUE_PASSPORT_NAME", "queue-ocr-passport")
    QUEUE_EXTRACTED_NAME: str = os.getenv("QUEUE_EXTRACTED_NAME", "queue-extracted")
    
    MOCK_QUEUE_DIR: str = os.getenv("MOCK_QUEUE_DIR", "./data/queues")
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "./data/kyc.db")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./data/uploads")
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def get_queue_name_for_document_type(cls, document_type: DocumentType) -> str:
        mapping = {
            DocumentType.DNI: cls.QUEUE_DNI_NAME,
            DocumentType.PASSPORT: cls.QUEUE_PASSPORT_NAME,
        }
        return mapping[document_type]
    
    @classmethod
    def is_local(cls) -> bool:
        return cls.ENVIRONMENT == Environment.LOCAL
    
    @classmethod
    def is_aws(cls) -> bool:
        return cls.ENVIRONMENT == Environment.AWS


config = Config()

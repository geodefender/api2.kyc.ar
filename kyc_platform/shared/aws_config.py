import os


class AWSConfig:
    HANDLER_MEMORY_MB: int = int(os.getenv("HANDLER_MEMORY_MB", "512"))
    HANDLER_TIMEOUT_S: int = int(os.getenv("HANDLER_TIMEOUT_S", "10"))
    
    OCR_DNI_MEMORY_MB: int = int(os.getenv("OCR_DNI_MEMORY_MB", "2048"))
    OCR_DNI_TIMEOUT_S: int = int(os.getenv("OCR_DNI_TIMEOUT_S", "180"))
    
    OCR_PASSPORT_MEMORY_MB: int = int(os.getenv("OCR_PASSPORT_MEMORY_MB", "2048"))
    OCR_PASSPORT_TIMEOUT_S: int = int(os.getenv("OCR_PASSPORT_TIMEOUT_S", "180"))
    
    WEBHOOK_MEMORY_MB: int = int(os.getenv("WEBHOOK_MEMORY_MB", "256"))
    WEBHOOK_TIMEOUT_S: int = int(os.getenv("WEBHOOK_TIMEOUT_S", "30"))
    
    DLQ_MAX_RECEIVE_COUNT: int = int(os.getenv("DLQ_MAX_RECEIVE_COUNT", "3"))
    
    @classmethod
    def get_lambda_config(cls, component: str) -> dict:
        configs = {
            "handler": {
                "memory_mb": cls.HANDLER_MEMORY_MB,
                "timeout_s": cls.HANDLER_TIMEOUT_S,
                "description": "API Handler for document uploads",
            },
            "ocr_dni": {
                "memory_mb": cls.OCR_DNI_MEMORY_MB,
                "timeout_s": cls.OCR_DNI_TIMEOUT_S,
                "description": "OCR Worker for DNI documents",
            },
            "ocr_passport": {
                "memory_mb": cls.OCR_PASSPORT_MEMORY_MB,
                "timeout_s": cls.OCR_PASSPORT_TIMEOUT_S,
                "description": "OCR Worker for Passport documents",
            },
            "webhook": {
                "memory_mb": cls.WEBHOOK_MEMORY_MB,
                "timeout_s": cls.WEBHOOK_TIMEOUT_S,
                "description": "Webhook dispatcher for notifications",
            },
        }
        return configs.get(component, {})


aws_config = AWSConfig()

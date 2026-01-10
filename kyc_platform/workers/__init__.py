from kyc_platform.workers.ocr_dni import handler as dni_handler
from kyc_platform.workers.ocr_passport import handler as passport_handler
from kyc_platform.workers.webhook_dispatcher import handler as webhook_handler

__all__ = ["dni_handler", "passport_handler", "webhook_handler"]

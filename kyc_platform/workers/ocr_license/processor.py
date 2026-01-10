import time
from typing import Any
from PIL import Image

try:
    import cv2
    cv2_available = True
except ImportError:
    cv2 = None
    cv2_available = False

from kyc_platform.workers.ocr_license.strategies import LicenseArgentinaStrategy
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class LicenseProcessor:
    
    def __init__(self):
        self._strategy = LicenseArgentinaStrategy()
    
    def process(self, image_path: str) -> dict[str, Any]:
        start_time = time.time()
        
        try:
            pil_image = Image.open(image_path)
            pil_image = pil_image.convert("RGB")
        except Exception as e:
            logger.error(f"Failed to open image: {e}")
            return {
                "success": False,
                "errors": [f"Failed to open image: {str(e)}"],
                "processing_time_ms": int((time.time() - start_time) * 1000),
            }
        
        try:
            extraction_result = self._strategy.extract(pil_image)
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {
                "success": False,
                "errors": [f"Extraction failed: {str(e)}"],
                "processing_time_ms": int((time.time() - start_time) * 1000),
            }
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        if extraction_result["source"] == "error" or not extraction_result["fields"]:
            return {
                "success": False,
                "errors": ["No fields could be extracted from license"],
                "processing_time_ms": processing_time_ms,
            }
        
        return {
            "success": True,
            "extracted_data": extraction_result["fields"],
            "confidence": extraction_result["confidence"],
            "source": extraction_result["source"],
            "processing_time_ms": processing_time_ms,
        }

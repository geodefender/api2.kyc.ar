import time
from typing import Any
from PIL import Image

from kyc_platform.workers.ocr_passport.strategies import MRZStrategy
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class PassportProcessor:
    def __init__(self):
        self.strategy = MRZStrategy()
    
    def process(self, image_path: str) -> dict[str, Any]:
        start_time = time.time()
        
        try:
            image = Image.open(image_path)
        except Exception as e:
            logger.error(f"Failed to open image: {e}")
            return {
                "success": False,
                "errors": [f"Failed to open image: {str(e)}"],
                "processing_time_ms": int((time.time() - start_time) * 1000),
            }
        
        result = self.strategy.extract(image)
        confidence = self.strategy.get_confidence()
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return {
            "success": True,
            "extracted_data": result,
            "confidence": confidence,
            "processing_time_ms": processing_time_ms,
        }

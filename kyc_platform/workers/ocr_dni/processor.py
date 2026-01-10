import time
from typing import Any
from PIL import Image

from kyc_platform.workers.ocr_dni.strategies import DNINuevoStrategy, DNIViejoStrategy
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class DNIProcessor:
    def __init__(self):
        self.strategies = {
            "nuevo": DNINuevoStrategy(),
            "viejo": DNIViejoStrategy(),
        }
    
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
        
        nuevo_strategy = self.strategies["nuevo"]
        nuevo_result = nuevo_strategy.extract(image)
        nuevo_confidence = nuevo_strategy.get_confidence()
        
        if nuevo_confidence >= 0.9:
            processing_time_ms = int((time.time() - start_time) * 1000)
            return {
                "success": True,
                "extracted_data": nuevo_result,
                "confidence": nuevo_confidence,
                "dni_type": "nuevo",
                "processing_time_ms": processing_time_ms,
            }
        
        viejo_strategy = self.strategies["viejo"]
        viejo_result = viejo_strategy.extract(image)
        viejo_confidence = viejo_strategy.get_confidence()
        
        if nuevo_confidence >= viejo_confidence:
            best_result = nuevo_result
            best_confidence = nuevo_confidence
            dni_type = "nuevo"
        else:
            best_result = viejo_result
            best_confidence = viejo_confidence
            dni_type = "viejo"
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return {
            "success": True,
            "extracted_data": best_result,
            "confidence": best_confidence,
            "dni_type": dni_type,
            "processing_time_ms": processing_time_ms,
        }

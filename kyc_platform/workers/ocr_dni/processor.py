import time
import cv2
from typing import Any
from PIL import Image

from kyc_platform.workers.ocr_dni.preprocess import normalize_image
from kyc_platform.workers.ocr_dni.heuristics import DniHeuristicAnalyzer
from kyc_platform.workers.ocr_dni.strategies import (
    DNINewFrontStrategy,
    DNINewBackStrategy,
    DNIOldStrategy,
    DNINuevoStrategy,
    DNIViejoStrategy,
    DNIUnifiedStrategy,
)
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class DNIProcessor:
    
    def __init__(self):
        self._heuristic_analyzer = DniHeuristicAnalyzer()
        
        self._unified_strategy = DNIUnifiedStrategy()
        
        self._strategies = {
            "dni_new_front": DNINewFrontStrategy(),
            "dni_new_back": DNINewBackStrategy(),
            "dni_old": DNIOldStrategy(),
            "nuevo": DNINuevoStrategy(),
            "viejo": DNIViejoStrategy(),
        }
    
    def process(self, image_path: str) -> dict[str, Any]:
        start_time = time.time()
        
        try:
            cv_image = cv2.imread(image_path)
            if cv_image is None:
                raise ValueError(f"Could not read image from {image_path}")
        except Exception as e:
            logger.error(f"Failed to open image: {e}")
            return {
                "success": False,
                "errors": [f"Failed to open image: {str(e)}"],
                "processing_time_ms": int((time.time() - start_time) * 1000),
            }
        
        try:
            normalized = normalize_image(cv_image)
            logger.info("Image normalized successfully")
        except Exception as e:
            logger.warning(f"Image normalization failed, using original: {e}")
            normalized = cv_image
        
        heuristic_result = self._heuristic_analyzer.analyze(normalized)
        
        logger.info(
            "Heuristic analysis completed",
            extra={
                "document_variant": heuristic_result.document_variant,
                "confidence": heuristic_result.confidence,
                "signals": {
                    "pdf417_score": heuristic_result.signals.pdf417_score,
                    "mrz_score": heuristic_result.signals.mrz_score,
                    "dni_front_score": heuristic_result.signals.dni_front_score,
                    "dni_old_score": heuristic_result.signals.dni_old_score,
                    "notes": heuristic_result.signals.notes,
                },
            },
        )
        
        pil_image = Image.fromarray(cv2.cvtColor(normalized, cv2.COLOR_BGR2RGB))
        
        extraction_result = self._unified_strategy.extract(pil_image)
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return {
            "success": True,
            "extracted_data": extraction_result["fields"],
            "confidence": extraction_result["confidence"],
            "source": extraction_result["source"],
            "dni_type": self._map_variant_to_type(heuristic_result.document_variant),
            "document_variant": heuristic_result.document_variant,
            "heuristic_confidence": heuristic_result.confidence,
            "processing_time_ms": processing_time_ms,
        }
    
    def _extract_with_strategy(
        self,
        image: Image.Image,
        variant: str,
    ) -> dict[str, Any]:
        if variant == "dni_new_back":
            strategy = self._strategies["dni_new_back"]
            return strategy.extract(image)
        
        elif variant == "dni_new_front":
            strategy = self._strategies["dni_new_front"]
            return strategy.extract(image)
        
        elif variant == "dni_old":
            strategy = self._strategies["dni_old"]
            return strategy.extract(image)
        
        else:
            nuevo_strategy = self._strategies["nuevo"]
            nuevo_result = nuevo_strategy.extract(image)
            
            if nuevo_result["confidence"] >= 0.7:
                return nuevo_result
            
            viejo_strategy = self._strategies["viejo"]
            viejo_result = viejo_strategy.extract(image)
            
            if nuevo_result["confidence"] >= viejo_result["confidence"]:
                return nuevo_result
            else:
                return viejo_result
    
    def _map_variant_to_type(self, variant: str) -> str:
        mapping = {
            "dni_new_front": "nuevo",
            "dni_new_back": "nuevo",
            "dni_old": "viejo",
            "unknown": "nuevo",
        }
        return mapping.get(variant, "nuevo")

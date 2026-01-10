import re
from typing import Any
from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None

from kyc_platform.workers.ocr_dni.strategies.base import DNIOCRStrategy
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class DNIOldStrategy(DNIOCRStrategy):
    
    def __init__(self):
        self._confidence = 0.0
    
    def extract(self, image: Image.Image) -> dict[str, Any]:
        if pytesseract is None:
            logger.error("pytesseract not available")
            return {}
        
        try:
            text = pytesseract.image_to_string(image, lang="spa")
            result = self._parse_old_format(text)
            
            self._calculate_confidence(result)
            return result
        except Exception as e:
            logger.error(f"DNI Old OCR extraction failed: {e}")
            return {}
    
    def _parse_old_format(self, text: str) -> dict[str, Any]:
        result = {}
        text_upper = text.upper()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        dni_patterns = [
            r"DOCUMENTO\s*(?:NACIONAL)?\s*(?:DE)?\s*(?:IDENTIDAD)?\s*[:\-\#]?\s*(\d{7,8})",
            r"N[°UoO]?\s*(?:DE)?\s*(?:DOCUMENTO)?\s*[:\-]?\s*(\d{7,8})",
            r"\b(\d{7,8})\b",
        ]
        for pattern in dni_patterns:
            match = re.search(pattern, text_upper)
            if match:
                result["numero_documento"] = match.group(1)
                break
        
        apellido_patterns = [
            r"APELLIDO[S]?\s*[:\-]?\s*(.+)",
        ]
        for pattern in apellido_patterns:
            match = re.search(pattern, text_upper)
            if match:
                value = match.group(1).strip()
                value = re.sub(r'[^A-ZÁÉÍÓÚÑ\s]', '', value)
                if value:
                    result["apellido"] = value.title()
                break
        
        nombre_patterns = [
            r"NOMBRE[S]?\s*[:\-]?\s*(.+)",
        ]
        for pattern in nombre_patterns:
            match = re.search(pattern, text_upper)
            if match:
                value = match.group(1).strip()
                value = re.sub(r'[^A-ZÁÉÍÓÚÑ\s]', '', value)
                if value:
                    result["nombre"] = value.title()
                break
        
        if "MASCULINO" in text_upper:
            result["sexo"] = "M"
        elif "FEMENINO" in text_upper:
            result["sexo"] = "F"
        
        if "ARGENTIN" in text_upper:
            result["nacionalidad"] = "ARGENTINA"
        
        date_pattern = r"\b(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})\b"
        dates_found = re.findall(date_pattern, text)
        
        if len(dates_found) >= 1:
            result["fecha_nacimiento"] = dates_found[0]
        
        return result
    
    def _calculate_confidence(self, result: dict[str, Any]) -> None:
        fields_found = sum(1 for v in result.values() if v)
        
        if result.get("numero_documento") and fields_found >= 3:
            self._confidence = 0.75
        elif result.get("numero_documento"):
            self._confidence = 0.60
        elif fields_found >= 2:
            self._confidence = 0.45
        else:
            self._confidence = 0.20
    
    def get_confidence(self) -> float:
        return self._confidence

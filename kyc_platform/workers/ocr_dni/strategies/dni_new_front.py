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


class DNINewFrontStrategy(DNIOCRStrategy):
    
    def __init__(self):
        self._confidence = 0.0
    
    def extract(self, image: Image.Image) -> dict[str, Any]:
        if pytesseract is None:
            logger.error("pytesseract not available")
            return {}
        
        try:
            text = pytesseract.image_to_string(image, lang="spa")
            result = self._parse_front_text(text)
            
            self._calculate_confidence(result)
            return result
        except Exception as e:
            logger.error(f"DNI New Front OCR extraction failed: {e}")
            return {}
    
    def _parse_front_text(self, text: str) -> dict[str, Any]:
        result = {}
        text_upper = text.upper()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        dni_pattern = r"\b(\d{7,8})\b"
        for line in lines:
            match = re.search(dni_pattern, line)
            if match:
                result["numero_documento"] = match.group(1)
                break
        
        apellido_patterns = [
            r"APELLIDO[S]?\s*[/]?\s*SURNAME[S]?\s*[:\-]?\s*(.+)",
            r"SURNAME[S]?\s*[/]?\s*APELLIDO[S]?\s*[:\-]?\s*(.+)",
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
            r"NOMBRE[S]?\s*[/]?\s*NAME[S]?\s*[:\-]?\s*(.+)",
            r"NAME[S]?\s*[/]?\s*NOMBRE[S]?\s*[:\-]?\s*(.+)",
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
        
        if "MASCULINO" in text_upper or re.search(r'\bM\b', text_upper):
            result["sexo"] = "M"
        elif "FEMENINO" in text_upper or re.search(r'\bF\b', text_upper):
            result["sexo"] = "F"
        
        nationality_patterns = [
            r"NACIONALIDAD\s*[/]?\s*NATIONALITY\s*[:\-]?\s*(.+)",
            r"NACIONALIDAD\s*[:\-]?\s*(.+)",
        ]
        for pattern in nationality_patterns:
            match = re.search(pattern, text_upper)
            if match:
                value = match.group(1).strip()
                if "ARGENTIN" in value:
                    result["nacionalidad"] = "ARGENTINA"
                break
        
        date_pattern = r"\b(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})\b"
        dates_found = re.findall(date_pattern, text)
        
        if len(dates_found) >= 1:
            result["fecha_nacimiento"] = dates_found[0]
        if len(dates_found) >= 2:
            result["fecha_vencimiento"] = dates_found[1]
        
        return result
    
    def _calculate_confidence(self, result: dict[str, Any]) -> None:
        fields_found = sum(1 for v in result.values() if v)
        
        if result.get("numero_documento") and fields_found >= 3:
            self._confidence = 0.85
        elif result.get("numero_documento"):
            self._confidence = 0.70
        elif fields_found >= 2:
            self._confidence = 0.55
        else:
            self._confidence = 0.30
    
    def get_confidence(self) -> float:
        return self._confidence

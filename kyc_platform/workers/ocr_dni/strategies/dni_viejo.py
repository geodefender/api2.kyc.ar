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


class DNIViejoStrategy(DNIOCRStrategy):
    
    def __init__(self):
        self._confidence = 0.0
        self._source = "ocr"
    
    def extract(self, image: Image.Image) -> dict[str, Any]:
        if pytesseract is None:
            logger.error("pytesseract not available")
            return {
                "source": "error",
                "fields": {},
                "confidence": 0.0,
            }
        
        try:
            text = pytesseract.image_to_string(image, lang="spa")
            fields = self._parse_ocr_text(text)
            
            if fields.get("numero_documento"):
                self._confidence = 0.75
            elif any(fields.values()):
                self._confidence = 0.5
            else:
                self._confidence = 0.2
            
            return {
                "source": self._source,
                "fields": fields,
                "confidence": self._confidence,
            }
        except Exception as e:
            logger.error(f"DNI Viejo OCR extraction failed: {e}")
            return {
                "source": "error",
                "fields": {},
                "confidence": 0.0,
            }
    
    def _parse_ocr_text(self, text: str) -> dict[str, Any]:
        fields = {}
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text_upper = text.upper()
        
        dni_pattern = r"\b(\d{7,8})\b"
        for line in lines:
            match = re.search(dni_pattern, line)
            if match:
                fields["numero_documento"] = match.group(1)
                break
        
        apellido_patterns = [
            r"APELLIDO[S]?\s*[:\-]?\s*(.+)",
            r"SURNAME[S]?\s*[:\-]?\s*(.+)",
        ]
        for pattern in apellido_patterns:
            match = re.search(pattern, text_upper)
            if match:
                value = match.group(1).strip()
                value = re.sub(r'[^A-ZÁÉÍÓÚÑ\s]', '', value)
                if value:
                    fields["apellido"] = value.title()
                break
        
        nombre_patterns = [
            r"NOMBRE[S]?\s*[:\-]?\s*(.+)",
            r"GIVEN NAME[S]?\s*[:\-]?\s*(.+)",
            r"NAME[S]?\s*[:\-]?\s*(.+)",
        ]
        for pattern in nombre_patterns:
            match = re.search(pattern, text_upper)
            if match:
                value = match.group(1).strip()
                value = re.sub(r'[^A-ZÁÉÍÓÚÑ\s]', '', value)
                if value:
                    fields["nombre"] = value.title()
                break
        
        if "MASCULINO" in text_upper or " M " in text_upper:
            fields["sexo"] = "M"
        elif "FEMENINO" in text_upper or " F " in text_upper:
            fields["sexo"] = "F"
        
        if "ARGENTIN" in text_upper:
            fields["nacionalidad"] = "ARGENTINA"
        
        date_pattern = r"\b(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})\b"
        dates_found = re.findall(date_pattern, text)
        
        if len(dates_found) >= 1:
            fields["fecha_nacimiento"] = dates_found[0]
        
        return fields
    
    def get_confidence(self) -> float:
        return self._confidence

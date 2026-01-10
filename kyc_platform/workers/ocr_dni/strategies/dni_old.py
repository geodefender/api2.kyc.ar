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
            fields = self._parse_old_format(text)
            
            self._calculate_confidence(fields)
            
            return {
                "source": self._source,
                "fields": fields,
                "confidence": self._confidence,
            }
        except Exception as e:
            logger.error(f"DNI Old OCR extraction failed: {e}")
            return {
                "source": "error",
                "fields": {},
                "confidence": 0.0,
            }
    
    def _parse_old_format(self, text: str) -> dict[str, Any]:
        fields = {}
        text_upper = text.upper()
        
        dni_patterns = [
            r"DOCUMENTO\s*(?:NACIONAL)?\s*(?:DE)?\s*(?:IDENTIDAD)?\s*[:\-\#]?\s*(\d{7,8})",
            r"N[°UoO]?\s*(?:DE)?\s*(?:DOCUMENTO)?\s*[:\-]?\s*(\d{7,8})",
            r"\b(\d{7,8})\b",
        ]
        for pattern in dni_patterns:
            match = re.search(pattern, text_upper)
            if match:
                fields["numero_documento"] = match.group(1)
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
                    fields["apellido"] = value.title()
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
                    fields["nombre"] = value.title()
                break
        
        if "MASCULINO" in text_upper:
            fields["sexo"] = "M"
        elif "FEMENINO" in text_upper:
            fields["sexo"] = "F"
        
        if "ARGENTIN" in text_upper:
            fields["nacionalidad"] = "ARGENTINA"
        
        date_pattern = r"\b(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})\b"
        dates_found = re.findall(date_pattern, text)
        
        if len(dates_found) >= 1:
            fields["fecha_nacimiento"] = dates_found[0]
        
        return fields
    
    def _calculate_confidence(self, fields: dict[str, Any]) -> None:
        fields_found = sum(1 for v in fields.values() if v)
        
        if fields.get("numero_documento") and fields_found >= 3:
            self._confidence = 0.75
        elif fields.get("numero_documento"):
            self._confidence = 0.65
        elif fields_found >= 2:
            self._confidence = 0.50
        else:
            self._confidence = 0.20
    
    def get_confidence(self) -> float:
        return self._confidence

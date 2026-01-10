import re
from typing import Any
from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from pyzbar.pyzbar import decode as decode_barcode
except ImportError:
    decode_barcode = None

from kyc_platform.workers.ocr_dni.strategies.base import DNIOCRStrategy
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class DNINewBackStrategy(DNIOCRStrategy):
    
    def __init__(self):
        self._confidence = 0.0
        self._source = "unknown"
    
    def extract(self, image: Image.Image) -> dict[str, Any]:
        pdf417_result = self._extract_pdf417(image)
        if pdf417_result:
            self._source = "pdf417"
            self._confidence = 0.95
            return {
                "source": self._source,
                "fields": pdf417_result,
                "confidence": self._confidence,
            }
        
        ocr_result = self._extract_ocr_fallback(image)
        if ocr_result:
            self._source = "ocr_fallback"
            self._confidence = 0.60
            return {
                "source": self._source,
                "fields": ocr_result,
                "confidence": self._confidence,
            }
        
        return {
            "source": "none",
            "fields": {},
            "confidence": 0.0,
        }
    
    def _extract_pdf417(self, image: Image.Image) -> dict[str, Any] | None:
        if decode_barcode is None:
            logger.warning("pyzbar not available, skipping PDF417 extraction")
            return None
        
        try:
            barcodes = decode_barcode(image)
            for barcode in barcodes:
                if barcode.type == "PDF417":
                    raw_data = barcode.data.decode("utf-8", errors="ignore")
                    return self._parse_pdf417(raw_data)
        except Exception as e:
            logger.error(f"PDF417 extraction failed: {e}")
        
        return None
    
    def _parse_pdf417(self, raw_data: str) -> dict[str, Any]:
        fields = {}
        
        lines = raw_data.split("@")
        
        if len(lines) >= 8:
            fields["tramite"] = lines[0].strip() if len(lines) > 0 else None
            fields["apellido"] = lines[1].strip() if len(lines) > 1 else None
            fields["nombre"] = lines[2].strip() if len(lines) > 2 else None
            fields["sexo"] = lines[3].strip() if len(lines) > 3 else None
            fields["numero_documento"] = lines[4].strip() if len(lines) > 4 else None
            fields["ejemplar"] = lines[5].strip() if len(lines) > 5 else None
            fields["fecha_nacimiento"] = lines[6].strip() if len(lines) > 6 else None
            fields["fecha_emision"] = lines[7].strip() if len(lines) > 7 else None
            
            if len(lines) > 8:
                fields["cuil"] = lines[8].strip()
        
        return fields
    
    def _extract_ocr_fallback(self, image: Image.Image) -> dict[str, Any] | None:
        if pytesseract is None:
            logger.warning("pytesseract not available, skipping OCR fallback")
            return None
        
        try:
            text = pytesseract.image_to_string(image, lang="spa")
            return self._parse_dni_text(text)
        except Exception as e:
            logger.error(f"OCR fallback extraction failed: {e}")
            return None
    
    def _parse_dni_text(self, text: str) -> dict[str, Any]:
        fields = {}
        text_upper = text.upper()
        
        dni_pattern = r"\b(\d{7,8})\b"
        match = re.search(dni_pattern, text)
        if match:
            fields["numero_documento"] = match.group(1)
        
        date_pattern = r"\b(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})\b"
        dates_found = re.findall(date_pattern, text)
        
        if len(dates_found) >= 1:
            fields["fecha_nacimiento"] = dates_found[0]
        if len(dates_found) >= 2:
            fields["fecha_emision"] = dates_found[1]
        
        if "MASCULINO" in text_upper or " M " in text_upper:
            fields["sexo"] = "M"
        elif "FEMENINO" in text_upper or " F " in text_upper:
            fields["sexo"] = "F"
        
        return fields
    
    def get_confidence(self) -> float:
        return self._confidence

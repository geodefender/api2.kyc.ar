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


class DNINuevoStrategy(DNIOCRStrategy):
    def __init__(self):
        self._confidence = 0.0
        self._pdf417_data = None
    
    def extract(self, image: Image.Image) -> dict[str, Any]:
        result = {}
        
        pdf417_result = self._extract_pdf417(image)
        if pdf417_result:
            result.update(pdf417_result)
            self._confidence = 0.95
        
        ocr_result = self._extract_ocr(image)
        if ocr_result:
            for key, value in ocr_result.items():
                if key not in result or not result[key]:
                    result[key] = value
            if self._confidence < 0.7:
                self._confidence = 0.7
        
        return result
    
    def _extract_pdf417(self, image: Image.Image) -> dict[str, Any] | None:
        if decode_barcode is None:
            logger.warning("pyzbar not available, skipping PDF417 extraction")
            return None
        
        try:
            barcodes = decode_barcode(image)
            for barcode in barcodes:
                if barcode.type == "PDF417":
                    raw_data = barcode.data.decode("utf-8", errors="ignore")
                    self._pdf417_data = raw_data
                    return self._parse_pdf417(raw_data)
        except Exception as e:
            logger.error(f"PDF417 extraction failed: {e}")
        
        return None
    
    def _parse_pdf417(self, raw_data: str) -> dict[str, Any]:
        result = {"pdf417_raw": raw_data}
        
        lines = raw_data.split("@")
        
        if len(lines) >= 8:
            result["tramite"] = lines[0].strip() if len(lines) > 0 else None
            result["apellido"] = lines[1].strip() if len(lines) > 1 else None
            result["nombre"] = lines[2].strip() if len(lines) > 2 else None
            result["sexo"] = lines[3].strip() if len(lines) > 3 else None
            result["numero_documento"] = lines[4].strip() if len(lines) > 4 else None
            result["ejemplar"] = lines[5].strip() if len(lines) > 5 else None
            result["fecha_nacimiento"] = lines[6].strip() if len(lines) > 6 else None
            result["fecha_emision"] = lines[7].strip() if len(lines) > 7 else None
            
            if len(lines) > 8:
                result["cuil"] = lines[8].strip()
        
        return result
    
    def _extract_ocr(self, image: Image.Image) -> dict[str, Any] | None:
        if pytesseract is None:
            logger.warning("pytesseract not available, skipping OCR extraction")
            return None
        
        try:
            text = pytesseract.image_to_string(image, lang="spa")
            return self._parse_ocr_text(text)
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return None
    
    def _parse_ocr_text(self, text: str) -> dict[str, Any]:
        result = {}
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        dni_pattern = r"\b(\d{7,8})\b"
        for line in lines:
            match = re.search(dni_pattern, line)
            if match:
                result["numero_documento"] = match.group(1)
                break
        
        date_pattern = r"\b(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})\b"
        dates_found = []
        for line in lines:
            matches = re.findall(date_pattern, line)
            dates_found.extend(matches)
        
        if len(dates_found) >= 1:
            result["fecha_nacimiento"] = dates_found[0]
        if len(dates_found) >= 2:
            result["fecha_emision"] = dates_found[1]
        if len(dates_found) >= 3:
            result["fecha_vencimiento"] = dates_found[2]
        
        return result
    
    def get_confidence(self) -> float:
        return self._confidence

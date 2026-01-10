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
        self._pdf417_data = None
    
    def extract(self, image: Image.Image) -> dict[str, Any]:
        result = {}
        
        pdf417_result = self._extract_pdf417(image)
        if pdf417_result:
            result.update(pdf417_result)
            self._confidence = 0.95
            return result
        
        mrz_result = self._extract_mrz(image)
        if mrz_result:
            result.update(mrz_result)
            self._confidence = 0.85
        
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
        result = {}
        
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
    
    def _extract_mrz(self, image: Image.Image) -> dict[str, Any] | None:
        if pytesseract is None:
            logger.warning("pytesseract not available, skipping MRZ extraction")
            return None
        
        try:
            width, height = image.size
            mrz_region = image.crop((0, int(height * 0.70), width, height))
            
            text = pytesseract.image_to_string(mrz_region, config='--psm 6')
            return self._parse_mrz(text)
        except Exception as e:
            logger.error(f"MRZ extraction failed: {e}")
            return None
    
    def _parse_mrz(self, text: str) -> dict[str, Any] | None:
        result = {}
        
        lines = text.strip().split('\n')
        mrz_lines = []
        
        mrz_pattern = re.compile(r'^[A-Z0-9<]{20,44}$')
        
        for line in lines:
            clean_line = ''.join(c.upper() if c.isalnum() or c == '<' else '' for c in line)
            if len(clean_line) >= 20 and mrz_pattern.match(clean_line):
                mrz_lines.append(clean_line)
        
        if len(mrz_lines) < 2:
            return None
        
        if mrz_lines[0].startswith('ID'):
            doc_type = 'ID'
            if len(mrz_lines[0]) >= 5:
                country = mrz_lines[0][2:5].replace('<', '')
                if country:
                    result["nacionalidad"] = country
            
            doc_num_match = re.search(r'(\d{7,8})', mrz_lines[0])
            if doc_num_match:
                result["numero_documento"] = doc_num_match.group(1)
        
        if len(mrz_lines) > 1:
            line2 = mrz_lines[1]
            if len(line2) >= 7:
                birth_raw = line2[0:6]
                if birth_raw.isdigit():
                    year = birth_raw[0:2]
                    month = birth_raw[2:4]
                    day = birth_raw[4:6]
                    century = "19" if int(year) > 30 else "20"
                    result["fecha_nacimiento"] = f"{day}/{month}/{century}{year}"
            
            if len(line2) >= 8:
                sex_char = line2[7] if line2[7] in ['M', 'F'] else None
                if sex_char:
                    result["sexo"] = sex_char
        
        return result if result else None
    
    def get_confidence(self) -> float:
        return self._confidence

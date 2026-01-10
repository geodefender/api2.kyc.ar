import re
from typing import Any
from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None

from kyc_platform.workers.ocr_passport.strategies.base import PassportOCRStrategy
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class MRZStrategy(PassportOCRStrategy):
    MRZ_LINE_LENGTH = 44
    
    def __init__(self):
        self._confidence = 0.0
    
    def extract(self, image: Image.Image) -> dict[str, Any]:
        if pytesseract is None:
            logger.error("pytesseract not available")
            return {}
        
        try:
            text = pytesseract.image_to_string(image, lang="eng")
            mrz_lines = self._extract_mrz_lines(text)
            
            if len(mrz_lines) >= 2:
                result = self._parse_mrz(mrz_lines[0], mrz_lines[1])
                self._confidence = 0.9 if result.get("numero_pasaporte") else 0.5
                return result
            
            result = self._extract_from_ocr(text)
            self._confidence = 0.6 if result.get("numero_pasaporte") else 0.3
            return result
            
        except Exception as e:
            logger.error(f"Passport OCR extraction failed: {e}")
            return {}
    
    def _extract_mrz_lines(self, text: str) -> list[str]:
        lines = text.split("\n")
        mrz_lines = []
        
        for line in lines:
            cleaned = re.sub(r"[^A-Z0-9<]", "", line.upper())
            if len(cleaned) >= 40 and "<" in cleaned:
                mrz_lines.append(cleaned)
        
        return mrz_lines[:2]
    
    def _parse_mrz(self, line1: str, line2: str) -> dict[str, Any]:
        result = {
            "mrz_line1": line1,
            "mrz_line2": line2,
        }
        
        if len(line1) >= 44:
            doc_type = line1[0:2].replace("<", "")
            country_code = line1[2:5].replace("<", "")
            names_field = line1[5:44]
            
            result["codigo_pais"] = country_code
            
            if "<<" in names_field:
                parts = names_field.split("<<")
                result["apellido"] = parts[0].replace("<", " ").strip()
                if len(parts) > 1:
                    result["nombre"] = parts[1].replace("<", " ").strip()
        
        if len(line2) >= 44:
            passport_number = line2[0:9].replace("<", "")
            result["numero_pasaporte"] = passport_number
            
            nationality = line2[10:13].replace("<", "")
            result["nacionalidad"] = nationality
            
            birth_date = line2[13:19]
            if birth_date.isdigit():
                result["fecha_nacimiento"] = self._format_date(birth_date)
            
            sex = line2[20:21]
            if sex in ["M", "F"]:
                result["sexo"] = sex
            
            expiry_date = line2[21:27]
            if expiry_date.isdigit():
                result["fecha_vencimiento"] = self._format_date(expiry_date)
        
        return result
    
    def _format_date(self, date_str: str) -> str:
        if len(date_str) != 6:
            return date_str
        
        yy = date_str[0:2]
        mm = date_str[2:4]
        dd = date_str[4:6]
        
        year = int(yy)
        if year > 50:
            century = "19"
        else:
            century = "20"
        
        return f"{dd}/{mm}/{century}{yy}"
    
    def _extract_from_ocr(self, text: str) -> dict[str, Any]:
        result = {}
        text_upper = text.upper()
        
        passport_pattern = r"\b([A-Z]{2,3}\d{6,9})\b"
        match = re.search(passport_pattern, text_upper)
        if match:
            result["numero_pasaporte"] = match.group(1)
        
        if "ARGENTIN" in text_upper:
            result["nacionalidad"] = "ARGENTINA"
        
        apellido_patterns = [
            r"APELLIDO[S]?\s*[:\-/]?\s*([A-Z]+)",
            r"SURNAME[S]?\s*[:\-/]?\s*([A-Z]+)",
        ]
        for pattern in apellido_patterns:
            match = re.search(pattern, text_upper)
            if match:
                result["apellido"] = match.group(1).title()
                break
        
        nombre_patterns = [
            r"NOMBRE[S]?\s*[:\-/]?\s*([A-Z]+)",
            r"GIVEN NAME[S]?\s*[:\-/]?\s*([A-Z]+)",
        ]
        for pattern in nombre_patterns:
            match = re.search(pattern, text_upper)
            if match:
                result["nombre"] = match.group(1).title()
                break
        
        date_pattern = r"\b(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})\b"
        dates_found = re.findall(date_pattern, text)
        if dates_found:
            result["fecha_nacimiento"] = dates_found[0]
            if len(dates_found) > 1:
                result["fecha_vencimiento"] = dates_found[-1]
        
        return result
    
    def get_confidence(self) -> float:
        return self._confidence

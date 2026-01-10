import re
from typing import Any
from PIL import Image

try:
    import pytesseract
    tesseract_available = True
except ImportError:
    pytesseract = None
    tesseract_available = False

from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class LicenseArgentinaStrategy:
    
    def __init__(self):
        self.field_patterns = {
            "numero_licencia": [
                r"(?:N[°o]?\s*)?(?:LIC(?:ENCIA)?\.?\s*)?(\d{8,11})",
                r"LICENCIA\s*[:\-]?\s*(\d+)",
            ],
            "numero_documento": [
                r"(?:DNI|D\.N\.I\.?|DOCUMENTO)\s*[:\-]?\s*(\d{6,8})",
                r"(\d{2}[.\s]?\d{3}[.\s]?\d{3})",
            ],
            "apellido": [
                r"(?:APELLIDO|SURNAME)\s*[:\-]?\s*([A-ZÁÉÍÓÚÑ]+)",
            ],
            "nombre": [
                r"(?:NOMBRE|NAME|NOMBRES)\s*[:\-]?\s*([A-ZÁÉÍÓÚÑ\s]+)",
            ],
            "fecha_nacimiento": [
                r"(?:F(?:ECHA)?\.?\s*)?(?:NAC(?:IMIENTO)?\.?|BIRTH)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
                r"(?:NACIDO)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
            ],
            "fecha_vencimiento": [
                r"(?:VENC(?:IMIENTO)?\.?|EXPIRY|VTO\.?)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
                r"(?:VALIDO?\s*HASTA)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
            ],
            "fecha_emision": [
                r"(?:EMISI[OÓ]N|OTORG(?:AMIENTO)?)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
            ],
            "clase": [
                r"(?:CLASE|CLASS)\s*[:\-]?\s*([A-Z](?:\d)?(?:\.\d)?)",
                r"CLASE[S]?\s*HABILITADA[S]?\s*[:\-]?\s*([A-Z\d\s\.\,]+)",
            ],
            "domicilio": [
                r"(?:DOMICILIO|DOM\.?|DIRECCION)\s*[:\-]?\s*(.+?)(?=\n|$)",
            ],
            "grupo_sanguineo": [
                r"(?:GRUPO|BLOOD|SANG)\s*[:\-]?\s*([ABO]{1,2}[\+\-]?)",
                r"(?:GR\.?\s*SANG\.?)\s*[:\-]?\s*([ABO]{1,2}[\+\-]?)",
            ],
            "cuil": [
                r"(?:CUIL|C\.U\.I\.L\.?)\s*[:\-]?\s*(\d{2}[\-\s]?\d{8}[\-\s]?\d{1})",
            ],
        }
    
    def extract(self, image: Image.Image) -> dict[str, Any]:
        if not tesseract_available:
            logger.warning("Tesseract not available")
            return {
                "source": "error",
                "fields": {},
                "confidence": 0.0,
            }
        
        try:
            text = pytesseract.image_to_string(image, lang="spa", config="--psm 6")
            logger.debug(f"OCR text extracted: {len(text)} characters")
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return {
                "source": "error",
                "fields": {},
                "confidence": 0.0,
            }
        
        fields = {}
        text_upper = text.upper()
        
        for field_name, patterns in self.field_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text_upper, re.IGNORECASE | re.MULTILINE)
                if match:
                    value = match.group(1).strip()
                    value = self._clean_value(field_name, value)
                    if value:
                        fields[field_name] = value
                        break
        
        field_count = len(fields)
        max_fields = len(self.field_patterns)
        confidence = min(0.95, (field_count / max_fields) * 1.2)
        
        if field_count == 0:
            return {
                "source": "none",
                "fields": {},
                "confidence": 0.0,
            }
        
        return {
            "source": "ocr",
            "fields": fields,
            "confidence": round(confidence, 2),
        }
    
    def _clean_value(self, field_name: str, value: str) -> str:
        if not value:
            return ""
        
        value = value.strip()
        
        if field_name == "numero_documento":
            value = re.sub(r"[.\s]", "", value)
        
        if field_name == "numero_licencia":
            value = re.sub(r"[^0-9]", "", value)
        
        if "fecha" in field_name:
            value = re.sub(r"[\s]", "", value)
            value = value.replace("-", "/").replace(".", "/")
        
        return value

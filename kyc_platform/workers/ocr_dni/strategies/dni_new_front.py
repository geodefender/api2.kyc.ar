import re
from typing import Any
from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None

from kyc_platform.workers.ocr_dni.strategies.base import DNIOCRStrategy
from kyc_platform.workers.ocr_dni.strategies.text_normalizers import (
    normalize_bilingual_date,
    extract_value_after_label,
    extract_document_number,
    extract_tramite,
    extract_sex,
    extract_ejemplar,
)
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class DNINewFrontStrategy(DNIOCRStrategy):
    
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
            fields = self._parse_front_text(text)
            
            self._calculate_confidence(fields)
            
            return {
                "source": self._source,
                "fields": fields,
                "confidence": self._confidence,
            }
        except Exception as e:
            logger.error(f"DNI New Front OCR extraction failed: {e}")
            return {
                "source": "error",
                "fields": {},
                "confidence": 0.0,
            }
    
    def _parse_front_text(self, text: str) -> dict[str, Any]:
        fields = {}
        text_upper = text.upper()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        doc_num = extract_document_number(lines)
        if doc_num:
            fields["numero_documento"] = doc_num
        
        apellido = extract_value_after_label(
            lines,
            [r'APELLIDO[S]?\s*[/]?\s*SURNAME', r'SURNAME\s*[/]?\s*APELLIDO']
        )
        if apellido:
            fields["apellido"] = apellido
        
        nombre = extract_value_after_label(
            lines,
            [r'NOMBRE[S]?\s*[/]?\s*NAME', r'NAME\s*[/]?\s*NOMBRE']
        )
        if nombre:
            fields["nombre"] = nombre
        
        sexo = extract_sex(text_upper)
        if sexo:
            fields["sexo"] = sexo
        
        if "ARGENTIN" in text_upper:
            fields["nacionalidad"] = "ARGENTINA"
        
        ejemplar = extract_ejemplar(text_upper)
        if ejemplar:
            fields["ejemplar"] = ejemplar
        
        tramite = extract_tramite(lines)
        if tramite:
            fields["tramite"] = tramite
        
        self._extract_dates(lines, text_upper, fields)
        
        return fields
    
    def _extract_dates(self, lines: list[str], text_upper: str, fields: dict[str, Any]) -> None:
        date_labels = [
            (r'FECHA\s*DE\s*NACIMIENTO|DATE\s*OF\s*BIRTH', 'fecha_nacimiento'),
            (r'FECHA\s*DE\s*EMISI[OÓ]N|DATE\s*OF\s*ISSUE', 'fecha_emision'),
            (r'FECHA\s*DE\s*VENCIMIENTO|DATE\s*OF\s*EXPIRY', 'fecha_vencimiento'),
        ]
        
        for i, line in enumerate(lines):
            line_upper = line.upper()
            for pattern, field_name in date_labels:
                if re.search(pattern, line_upper):
                    if i + 1 < len(lines):
                        date_str = normalize_bilingual_date(lines[i + 1])
                        if date_str:
                            fields[field_name] = date_str
                            break
                    
                    date_on_same_line = re.search(
                        r'(\d{1,2}\s+[A-Z]{3,}\s*[/]?\s*[A-Z]*\s+\d{4})',
                        line_upper
                    )
                    if date_on_same_line:
                        date_str = normalize_bilingual_date(date_on_same_line.group(1))
                        if date_str:
                            fields[field_name] = date_str
    
    def _calculate_confidence(self, fields: dict[str, Any]) -> None:
        fields_found = sum(1 for v in fields.values() if v)
        
        has_doc = bool(fields.get("numero_documento"))
        has_name = bool(fields.get("nombre") or fields.get("apellido"))
        has_dates = bool(fields.get("fecha_nacimiento"))
        
        if has_doc and has_name and has_dates and fields_found >= 5:
            self._confidence = 0.90
        elif has_doc and has_name and fields_found >= 4:
            self._confidence = 0.85
        elif has_doc and fields_found >= 3:
            self._confidence = 0.75
        elif has_doc:
            self._confidence = 0.65
        elif fields_found >= 2:
            self._confidence = 0.50
        else:
            self._confidence = 0.30
    
    def get_confidence(self) -> float:
        return self._confidence

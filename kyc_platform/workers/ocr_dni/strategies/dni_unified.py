import re
from typing import Any, Optional
from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from pdf417decoder import PDF417Decoder
    pdf417_available = True
except ImportError:
    PDF417Decoder = None
    pdf417_available = False

from kyc_platform.workers.ocr_dni.strategies.base import DNIOCRStrategy
from kyc_platform.workers.ocr_dni.strategies.mrz_parser import mrz_parser
from kyc_platform.workers.ocr_dni.strategies.text_normalizers import (
    normalize_document_number,
    normalize_bilingual_date,
    extract_value_after_label,
    extract_document_number,
    extract_sex,
)
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class DNIUnifiedStrategy(DNIOCRStrategy):
    
    def __init__(self):
        self._confidence = 0.0
        self._sources_used = []
    
    def extract(self, image: Image.Image) -> dict[str, Any]:
        self._sources_used = []
        self._confidence = 0.0
        
        pdf417_fields = self._extract_pdf417(image)
        mrz_fields = self._extract_mrz(image)
        ocr_fields = self._extract_ocr(image)
        
        merged = self._merge_results(pdf417_fields, mrz_fields, ocr_fields)
        
        confidence = self._calculate_confidence(pdf417_fields, mrz_fields, ocr_fields, merged)
        
        source = self._determine_source()
        
        return {
            "source": source,
            "fields": merged,
            "confidence": confidence,
            "sources_used": self._sources_used,
        }
    
    def _extract_pdf417(self, image: Image.Image) -> dict[str, Any]:
        if not pdf417_available:
            logger.debug("PDF417 decoder not available")
            return {}
        
        try:
            decoder = PDF417Decoder(image)
            num_barcodes = decoder.decode()
            
            if num_barcodes > 0:
                raw_data = decoder.barcode_data_index_to_string(0)
                if raw_data:
                    logger.info("PDF417 barcode detected and decoded")
                    self._sources_used.append("pdf417")
                    return self._parse_pdf417(raw_data)
        except Exception as e:
            logger.debug(f"PDF417 extraction failed: {e}")
        
        return {}
    
    def _parse_pdf417(self, raw_data: str) -> dict[str, Any]:
        fields = {}
        
        parts = raw_data.split("@")
        
        if raw_data.startswith("@") and len(parts) >= 10:
            fields = self._parse_pdf417_old_format(parts)
        elif len(parts) >= 8:
            fields = self._parse_pdf417_new_format(parts)
        
        return fields
    
    def _parse_pdf417_new_format(self, parts: list[str]) -> dict[str, Any]:
        fields = {}
        if parts[0].strip():
            fields["tramite"] = parts[0].strip()
        if parts[1].strip():
            fields["apellido"] = parts[1].strip().title()
        if parts[2].strip():
            fields["nombre"] = parts[2].strip().title()
        if parts[3].strip() in ('M', 'F'):
            fields["sexo"] = parts[3].strip()
        if parts[4].strip():
            doc_num = normalize_document_number(parts[4].strip())
            if doc_num:
                fields["numero_documento"] = doc_num
        if parts[5].strip():
            fields["ejemplar"] = parts[5].strip()
        if parts[6].strip():
            fields["fecha_nacimiento"] = self._normalize_pdf417_date(parts[6].strip())
        if parts[7].strip():
            fields["fecha_emision"] = self._normalize_pdf417_date(parts[7].strip())
        
        if len(parts) > 8 and parts[8].strip():
            cuil = parts[8].strip()
            if '-' in cuil or len(cuil) == 11:
                fields["cuil"] = cuil
        
        return fields
    
    def _parse_pdf417_old_format(self, parts: list[str]) -> dict[str, Any]:
        fields = {}
        if len(parts) >= 11:
            if parts[1].strip():
                doc_num = normalize_document_number(parts[1].strip())
                if doc_num:
                    fields["numero_documento"] = doc_num
            if parts[2].strip():
                fields["ejemplar"] = parts[2].strip()
            if parts[4].strip():
                fields["apellido"] = parts[4].strip().title()
            if parts[5].strip():
                fields["nombre"] = parts[5].strip().title()
            if parts[6].strip():
                if "ARGENTIN" in parts[6].upper():
                    fields["nacionalidad"] = "ARGENTINA"
            if parts[7].strip():
                fields["fecha_nacimiento"] = self._normalize_pdf417_date(parts[7].strip())
            if parts[8].strip() in ('M', 'F'):
                fields["sexo"] = parts[8].strip()
            if parts[9].strip():
                fields["fecha_emision"] = self._normalize_pdf417_date(parts[9].strip())
            if len(parts) > 10 and parts[10].strip():
                cuil = parts[10].strip()
                if len(cuil) == 11 or '-' in cuil:
                    fields["cuil"] = cuil
            if len(parts) > 12 and parts[12].strip():
                fields["fecha_vencimiento"] = self._normalize_pdf417_date(parts[12].strip())
        return fields
    
    def _normalize_pdf417_date(self, date_str: str) -> str:
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[0:2]}/{date_str[2:4]}/{date_str[4:8]}"
        return date_str
    
    def _extract_mrz(self, image: Image.Image) -> dict[str, Any]:
        if pytesseract is None:
            return {}
        
        try:
            text = pytesseract.image_to_string(image, lang="spa+eng")
            mrz_result = mrz_parser.extract_mrz_from_text(text)
            
            if mrz_result:
                logger.info("MRZ detected and parsed")
                self._sources_used.append("mrz")
                return mrz_result
        except Exception as e:
            logger.debug(f"MRZ extraction failed: {e}")
        
        return {}
    
    def _extract_ocr(self, image: Image.Image) -> dict[str, Any]:
        if pytesseract is None:
            return {}
        
        try:
            text = pytesseract.image_to_string(image, lang="spa")
            fields = self._parse_ocr_text(text)
            
            if fields:
                logger.info(f"OCR extracted {len(fields)} fields")
                self._sources_used.append("ocr")
            
            return fields
        except Exception as e:
            logger.debug(f"OCR extraction failed: {e}")
        
        return {}
    
    def _parse_ocr_text(self, text: str) -> dict[str, Any]:
        fields = {}
        text_upper = text.upper()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        doc_num = extract_document_number(lines)
        if doc_num:
            fields["numero_documento"] = doc_num
        
        apellido = extract_value_after_label(
            lines,
            [r'APELLIDO[S]?\s*[/]?\s*SURNAME', r'SURNAME\s*[/]?\s*APELLIDO', r'APELLIDOS?:']
        )
        if apellido:
            fields["apellido"] = apellido
        
        nombre = extract_value_after_label(
            lines,
            [r'NOMBRE[S]?\s*[/]?\s*NAME', r'NAME\s*[/]?\s*NOMBRE', r'NOMBRES?:']
        )
        if nombre:
            fields["nombre"] = nombre
        
        sexo = extract_sex(text_upper)
        if sexo:
            fields["sexo"] = sexo
        
        if "ARGENTIN" in text_upper:
            fields["nacionalidad"] = "ARGENTINA"
        
        self._extract_dates_from_text(lines, text_upper, fields)
        
        cuil_match = re.search(r'CUIL[:\s]*(\d{2}[-\s]?\d{8}[-\s]?\d{1})', text_upper)
        if cuil_match:
            cuil = re.sub(r'[^\d-]', '', cuil_match.group(1))
            fields["cuil"] = cuil
        
        domicilio_match = re.search(r'DOMICILIO[:\s]*(.+?)(?=\n|$)', text, re.IGNORECASE)
        if domicilio_match:
            fields["domicilio"] = domicilio_match.group(1).strip()
        
        return fields
    
    def _extract_dates_from_text(self, lines: list[str], text_upper: str, fields: dict[str, Any]) -> None:
        date_labels = [
            (r'FECHA\s*DE\s*NACIMIENTO|DATE\s*OF\s*BIRTH|NACIMIENTO', 'fecha_nacimiento'),
            (r'FECHA\s*DE\s*EMISI[OÓ]N|DATE\s*OF\s*ISSUE|EXPEDICION', 'fecha_emision'),
            (r'FECHA\s*DE\s*VENCIMIENTO|DATE\s*OF\s*EXPIRY|VENCIMIENTO', 'fecha_vencimiento'),
        ]
        
        for i, line in enumerate(lines):
            line_upper = line.upper()
            for pattern, field_name in date_labels:
                if re.search(pattern, line_upper):
                    date_on_line = re.search(
                        r'(\d{1,2}\s+[A-Z]{3,}\s*[/]?\s*[A-Z]*\s+\d{4})',
                        line_upper
                    )
                    if date_on_line:
                        date_str = normalize_bilingual_date(date_on_line.group(1))
                        if date_str:
                            fields[field_name] = date_str
                    elif i + 1 < len(lines):
                        date_str = normalize_bilingual_date(lines[i + 1])
                        if date_str:
                            fields[field_name] = date_str
    
    def _merge_results(
        self,
        pdf417: dict[str, Any],
        mrz: dict[str, Any],
        ocr: dict[str, Any],
    ) -> dict[str, Any]:
        merged = {}
        
        priority_order = [pdf417, mrz, ocr]
        
        all_keys = set()
        for source in priority_order:
            all_keys.update(source.keys())
        
        for key in all_keys:
            for source in priority_order:
                if key in source and source[key]:
                    merged[key] = source[key]
                    break
        
        self._cross_validate(merged, pdf417, mrz, ocr)
        
        return merged
    
    def _cross_validate(
        self,
        merged: dict[str, Any],
        pdf417: dict[str, Any],
        mrz: dict[str, Any],
        ocr: dict[str, Any],
    ) -> None:
        doc_sources = []
        if pdf417.get("numero_documento"):
            doc_sources.append(("pdf417", pdf417["numero_documento"]))
        if mrz.get("numero_documento"):
            doc_sources.append(("mrz", mrz["numero_documento"]))
        if ocr.get("numero_documento"):
            doc_sources.append(("ocr", ocr["numero_documento"]))
        
        if len(doc_sources) >= 2:
            values = [v for _, v in doc_sources]
            if len(set(values)) == 1:
                merged["_documento_verificado"] = True
            else:
                merged["_documento_discrepancia"] = True
                logger.warning(f"Document number discrepancy: {doc_sources}")
    
    def _calculate_confidence(
        self,
        pdf417: dict[str, Any],
        mrz: dict[str, Any],
        ocr: dict[str, Any],
        merged: dict[str, Any],
    ) -> float:
        base_confidence = 0.0
        
        if pdf417:
            base_confidence = max(base_confidence, 0.90)
        if mrz:
            base_confidence = max(base_confidence, 0.85)
        if ocr and len(ocr) >= 3:
            base_confidence = max(base_confidence, 0.70)
        elif ocr:
            base_confidence = max(base_confidence, 0.50)
        
        sources_count = sum(1 for s in [pdf417, mrz, ocr] if s)
        if sources_count >= 2:
            base_confidence = min(base_confidence + 0.05, 1.0)
        
        if merged.get("_documento_verificado"):
            base_confidence = min(base_confidence + 0.05, 1.0)
        elif merged.get("_documento_discrepancia"):
            base_confidence = max(base_confidence - 0.10, 0.30)
        
        self._confidence = base_confidence
        return base_confidence
    
    def _determine_source(self) -> str:
        if not self._sources_used:
            return "none"
        
        if "pdf417" in self._sources_used:
            if len(self._sources_used) > 1:
                return "pdf417+verified"
            return "pdf417"
        
        if "mrz" in self._sources_used:
            if "ocr" in self._sources_used:
                return "mrz+ocr"
            return "mrz"
        
        return "ocr"
    
    def get_confidence(self) -> float:
        return self._confidence

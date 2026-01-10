import re
from typing import Optional


MONTH_MAP = {
    "ENE": "01", "JAN": "01", "ENERO": "01", "JANUARY": "01",
    "FEB": "02", "FEBRERO": "02", "FEBRUARY": "02",
    "MAR": "03", "MARZO": "03", "MARCH": "03",
    "ABR": "04", "APR": "04", "ABRIL": "04", "APRIL": "04",
    "MAY": "05", "MAYO": "05",
    "JUN": "06", "JUNIO": "06", "JUNE": "06",
    "JUL": "07", "JULIO": "07", "JULY": "07",
    "AGO": "08", "AUG": "08", "AGOSTO": "08", "AUGUST": "08",
    "SEP": "09", "SET": "09", "SEPT": "09", "SEPTIEMBRE": "09", "SEPTEMBER": "09",
    "OCT": "10", "OCTUBRE": "10", "OCTOBER": "10",
    "NOV": "11", "NOVIEMBRE": "11", "NOVEMBER": "11",
    "DIC": "12", "DEC": "12", "DICIEMBRE": "12", "DECEMBER": "12",
}


def normalize_document_number(raw: str) -> Optional[str]:
    if not raw:
        return None
    cleaned = re.sub(r'[^\d]', '', raw)
    if 7 <= len(cleaned) <= 9:
        return cleaned
    return None


def normalize_bilingual_date(raw: str) -> Optional[str]:
    if not raw:
        return None
    
    raw_upper = raw.upper().strip()
    
    pattern = r'(\d{1,2})\s+([A-Z]{3,})\s*[/]?\s*[A-Z]*\s+(\d{4})'
    match = re.search(pattern, raw_upper)
    
    if match:
        day = match.group(1).zfill(2)
        month_text = match.group(2)
        year = match.group(3)
        
        month = MONTH_MAP.get(month_text)
        if month:
            return f"{day}/{month}/{year}"
    
    numeric_pattern = r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})'
    match = re.search(numeric_pattern, raw)
    if match:
        day = match.group(1).zfill(2)
        month = match.group(2).zfill(2)
        year = match.group(3)
        return f"{day}/{month}/{year}"
    
    return None


def extract_value_after_label(lines: list[str], label_patterns: list[str]) -> Optional[str]:
    for i, line in enumerate(lines):
        line_upper = line.upper()
        for pattern in label_patterns:
            if re.search(pattern, line_upper):
                match = re.search(pattern + r'\s*(.+)', line_upper)
                if match:
                    value = match.group(1).strip()
                    value = re.sub(r'[^A-ZÁÉÍÓÚÑ\s]', '', value)
                    if value and len(value) > 1:
                        return value.title()
                
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    next_upper = next_line.upper()
                    if next_upper and not any(lbl in next_upper for lbl in ['/', 'SEXO', 'NACIONALIDAD', 'FECHA', 'DOCUMENTO', 'TRAMITE']):
                        value = re.sub(r'[^A-ZÁÉÍÓÚÑ\s]', '', next_upper)
                        if value and len(value) > 1:
                            return value.title()
    return None


def extract_document_number(lines: list[str]) -> Optional[str]:
    for line in lines:
        line_upper = line.upper()
        if 'DOCUMENTO' in line_upper or 'DOCUMENT' in line_upper:
            match = re.search(r'(\d{1,2}[.\s]\d{3}[.\s]\d{3})', line)
            if match:
                return normalize_document_number(match.group(1))
    
    for line in lines:
        match = re.search(r'(\d{2}[.]\d{3}[.]\d{3})', line)
        if match:
            return normalize_document_number(match.group(1))
    
    for line in lines:
        match = re.search(r'(\d{1,2}[.\s]\d{3}[.\s]\d{3})', line)
        if match:
            return normalize_document_number(match.group(1))
    
    for line in lines:
        line_upper = line.upper()
        if 'TRAMITE' not in line_upper and 'TRÁMITE' not in line_upper:
            match = re.search(r'\b(\d{7,8})\b', line)
            if match and len(match.group(1)) <= 8:
                return match.group(1)
    
    return None


def extract_tramite(lines: list[str]) -> Optional[str]:
    for i, line in enumerate(lines):
        if 'TRAMITE' in line.upper() or 'TRÁMITE' in line.upper():
            match = re.search(r'(\d{10,15})', line)
            if match:
                return match.group(1)
            if i + 1 < len(lines):
                match = re.search(r'(\d{10,15})', lines[i + 1])
                if match:
                    return match.group(1)
    return None


def extract_sex(text_upper: str) -> Optional[str]:
    if "MASCULINO" in text_upper:
        return "M"
    if "FEMENINO" in text_upper:
        return "F"
    
    sexo_match = re.search(r'SEXO\s*[/]?\s*SEX\s*\n?\s*([MF])\b', text_upper)
    if sexo_match:
        return sexo_match.group(1)
    
    return None


def extract_ejemplar(text_upper: str) -> Optional[str]:
    match = re.search(r'EJEMPLAR\s*\n?\s*([A-Z])\b', text_upper)
    if match:
        return match.group(1)
    return None

import re
from typing import Any, Optional
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class MRZParser:
    
    def extract_mrz_from_text(self, text: str) -> Optional[dict[str, Any]]:
        lines = text.strip().split("\n")
        mrz_lines = []
        
        for line in lines:
            cleaned = re.sub(r'[^A-Z0-9<]', '', line.upper())
            if len(cleaned) >= 28 and '<' in cleaned:
                mrz_lines.append(cleaned)
        
        if len(mrz_lines) >= 3:
            return self._parse_td1_mrz(mrz_lines[-3:])
        
        if len(mrz_lines) >= 2:
            return self._parse_td2_mrz(mrz_lines[-2:])
        
        return None
    
    def _parse_td1_mrz(self, lines: list[str]) -> Optional[dict[str, Any]]:
        if len(lines) < 3:
            return None
        
        try:
            line1 = lines[0].ljust(30, '<')[:30]
            line2 = lines[1].ljust(30, '<')[:30]
            line3 = lines[2].ljust(30, '<')[:30]
            
            fields = {}
            
            doc_type = line1[0:2].replace('<', '')
            country = line1[2:5].replace('<', '')
            doc_number_raw = line1[5:14].replace('<', '')
            
            if doc_number_raw:
                fields["numero_documento"] = doc_number_raw
            
            if country:
                fields["pais_emisor"] = country
                if country == "ARG":
                    fields["nacionalidad"] = "ARGENTINA"
            
            birth_date_raw = line2[0:6]
            if birth_date_raw.isdigit():
                fields["fecha_nacimiento"] = self._format_mrz_date(birth_date_raw)
            
            sex = line2[7:8]
            if sex in ('M', 'F'):
                fields["sexo"] = sex
            
            expiry_date_raw = line2[8:14]
            if expiry_date_raw.isdigit():
                fields["fecha_vencimiento"] = self._format_mrz_date(expiry_date_raw)
            
            nationality = line2[15:18].replace('<', '')
            if nationality and not fields.get("nacionalidad"):
                fields["nacionalidad"] = "ARGENTINA" if nationality == "ARG" else nationality
            
            names_raw = line3.replace('<', ' ').strip()
            name_parts = [p.strip() for p in names_raw.split('  ') if p.strip()]
            
            if len(name_parts) >= 1:
                fields["apellido"] = name_parts[0].title()
            if len(name_parts) >= 2:
                fields["nombre"] = ' '.join(name_parts[1:]).title()
            
            return fields if fields else None
            
        except Exception as e:
            logger.error(f"TD1 MRZ parsing failed: {e}")
            return None
    
    def _parse_td2_mrz(self, lines: list[str]) -> Optional[dict[str, Any]]:
        if len(lines) < 2:
            return None
        
        try:
            line1 = lines[0].ljust(36, '<')[:36]
            line2 = lines[1].ljust(36, '<')[:36]
            
            fields = {}
            
            country = line1[2:5].replace('<', '')
            
            names_raw = line1[5:].replace('<', ' ').strip()
            name_parts = [p.strip() for p in names_raw.split('  ') if p.strip()]
            
            if len(name_parts) >= 1:
                fields["apellido"] = name_parts[0].title()
            if len(name_parts) >= 2:
                fields["nombre"] = ' '.join(name_parts[1:]).title()
            
            if country:
                fields["pais_emisor"] = country
                if country == "ARG":
                    fields["nacionalidad"] = "ARGENTINA"
            
            doc_number_raw = line2[0:9].replace('<', '')
            if doc_number_raw:
                fields["numero_documento"] = doc_number_raw
            
            birth_date_raw = line2[13:19]
            if birth_date_raw.isdigit():
                fields["fecha_nacimiento"] = self._format_mrz_date(birth_date_raw)
            
            sex = line2[20:21]
            if sex in ('M', 'F'):
                fields["sexo"] = sex
            
            expiry_date_raw = line2[21:27]
            if expiry_date_raw.isdigit():
                fields["fecha_vencimiento"] = self._format_mrz_date(expiry_date_raw)
            
            return fields if fields else None
            
        except Exception as e:
            logger.error(f"TD2 MRZ parsing failed: {e}")
            return None
    
    def _format_mrz_date(self, date_raw: str) -> str:
        if len(date_raw) != 6:
            return date_raw
        
        yy = date_raw[0:2]
        mm = date_raw[2:4]
        dd = date_raw[4:6]
        
        year_int = int(yy)
        if year_int > 50:
            year = f"19{yy}"
        else:
            year = f"20{yy}"
        
        return f"{dd}/{mm}/{year}"


mrz_parser = MRZParser()

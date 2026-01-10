import re
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)

PDF417_THRESHOLD = 0.55
MRZ_THRESHOLD = 0.60
DNI_FRONT_THRESHOLD = 0.60
DNI_OLD_THRESHOLD = 0.60


@dataclass
class HeuristicSignals:
    pdf417_score: float = 0.0
    mrz_score: float = 0.0
    dni_front_score: float = 0.0
    dni_old_score: float = 0.0
    notes: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "pdf417_score": round(self.pdf417_score, 3),
            "mrz_score": round(self.mrz_score, 3),
            "dni_front_score": round(self.dni_front_score, 3),
            "dni_old_score": round(self.dni_old_score, 3),
            "notes": self.notes,
        }


@dataclass
class HeuristicResult:
    document_variant: str
    confidence: float
    signals: HeuristicSignals
    
    def to_dict(self) -> dict:
        return {
            "document_variant": self.document_variant,
            "confidence": round(self.confidence, 3),
            "signals": self.signals.to_dict(),
        }


class DniHeuristicAnalyzer:
    
    def __init__(self):
        self._mrz_pattern = re.compile(r'^[A-Z0-9<]{20,44}$')
        self._skin_lower = np.array([0, 20, 70], dtype=np.uint8)
        self._skin_upper = np.array([20, 255, 255], dtype=np.uint8)
    
    def analyze(self, image: np.ndarray) -> HeuristicResult:
        if image is None or image.size == 0:
            return HeuristicResult(
                document_variant="unknown",
                confidence=0.0,
                signals=HeuristicSignals(notes=["Invalid input image"]),
            )
        
        signals = HeuristicSignals()
        
        signals.pdf417_score = self._detect_pdf417(image)
        if signals.pdf417_score >= PDF417_THRESHOLD:
            signals.notes.append("PDF417 barcode detected")
        
        signals.mrz_score = self._detect_mrz(image)
        if signals.mrz_score >= MRZ_THRESHOLD:
            signals.notes.append("MRZ pattern detected")
        
        signals.dni_front_score = self._detect_dni_front(image)
        if signals.dni_front_score >= DNI_FRONT_THRESHOLD:
            signals.notes.append("DNI front features detected")
        
        signals.dni_old_score = self._detect_dni_old(image)
        if signals.dni_old_score >= DNI_OLD_THRESHOLD:
            signals.notes.append("DNI old format detected")
        
        document_variant, confidence = self._decide_variant(signals)
        
        return HeuristicResult(
            document_variant=document_variant,
            confidence=confidence,
            signals=signals,
        )
    
    def _detect_pdf417(self, image: np.ndarray) -> float:
        h, w = image.shape[:2]
        
        roi_x = int(w * 0.55)
        roi_y = int(h * 0.50)
        roi = image[roi_y:, roi_x:]
        
        if roi.size == 0:
            return 0.0
        
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
        
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        density_score = self._calculate_barcode_density(binary)
        repetition_score = self._calculate_vertical_repetition(binary)
        position_score = self._calculate_position_score(roi_x, roi_y, w, h)
        
        pdf417_score = 0.5 * density_score + 0.3 * repetition_score + 0.2 * position_score
        
        return min(1.0, pdf417_score)
    
    def _calculate_barcode_density(self, binary: np.ndarray) -> float:
        total_pixels = binary.size
        if total_pixels == 0:
            return 0.0
        
        black_pixels = np.sum(binary == 0)
        white_pixels = np.sum(binary == 255)
        
        ratio = min(black_pixels, white_pixels) / max(black_pixels, white_pixels) if max(black_pixels, white_pixels) > 0 else 0
        
        return ratio
    
    def _calculate_vertical_repetition(self, binary: np.ndarray) -> float:
        if binary.shape[0] < 10:
            return 0.0
        
        transitions = []
        for row in range(min(50, binary.shape[0])):
            row_data = binary[row, :]
            diff = np.abs(np.diff(row_data.astype(np.int16)))
            transition_count = np.sum(diff > 127)
            transitions.append(transition_count)
        
        if not transitions:
            return 0.0
        
        avg_transitions = np.mean(transitions)
        std_transitions = np.std(transitions)
        
        if avg_transitions < 20:
            return 0.0
        
        consistency = 1 - (std_transitions / avg_transitions) if avg_transitions > 0 else 0
        density = min(1.0, avg_transitions / 100)
        
        return (consistency + density) / 2
    
    def _calculate_position_score(self, roi_x: int, roi_y: int, w: int, h: int) -> float:
        x_ratio = roi_x / w
        y_ratio = roi_y / h
        
        if x_ratio >= 0.55 and y_ratio >= 0.50:
            return 1.0
        elif x_ratio >= 0.45 and y_ratio >= 0.40:
            return 0.7
        else:
            return 0.3
    
    def _detect_mrz(self, image: np.ndarray) -> float:
        h, w = image.shape[:2]
        
        roi_y = int(h * 0.70)
        roi = image[roi_y:, :]
        
        if roi.size == 0:
            return 0.0
        
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
        
        small = cv2.resize(gray, (0, 0), fx=0.5, fy=0.5)
        
        try:
            import pytesseract
            text = pytesseract.image_to_string(small, config='--psm 6')
        except Exception:
            return 0.0
        
        lines = text.strip().split('\n')
        mrz_lines = []
        
        for line in lines:
            clean_line = ''.join(c.upper() if c.isalnum() or c == '<' else '' for c in line)
            if len(clean_line) >= 20 and self._mrz_pattern.match(clean_line):
                mrz_lines.append(clean_line)
        
        if len(mrz_lines) < 2:
            return len(mrz_lines) * 0.3
        
        score = 0.6
        
        for line in mrz_lines:
            if 'ARG' in line:
                score += 0.15
                break
        
        for line in mrz_lines:
            if line.startswith('ID') or line.startswith('P<'):
                score += 0.1
                break
        
        return min(1.0, score)
    
    def _detect_dni_front(self, image: np.ndarray) -> float:
        h, w = image.shape[:2]
        score = 0.0
        
        photo_roi_x = int(w * 0.05)
        photo_roi_y = int(h * 0.15)
        photo_roi_w = int(w * 0.35)
        photo_roi_h = int(h * 0.70)
        
        photo_roi = image[photo_roi_y:photo_roi_y+photo_roi_h, photo_roi_x:photo_roi_x+photo_roi_w]
        
        if photo_roi.size > 0:
            skin_score = self._detect_skin_tone(photo_roi)
            if skin_score > 0.1:
                score += 0.25
            
            aspect = photo_roi_w / photo_roi_h if photo_roi_h > 0 else 0
            if 0.6 < aspect < 0.9:
                score += 0.1
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        try:
            import pytesseract
            text = pytesseract.image_to_string(gray, config='--psm 6').upper()
            
            bilingual_terms = ['SURNAME', 'NAME', 'NATIONALITY', 'APELLIDO', 'NOMBRE', 'NACIONALIDAD']
            found_terms = sum(1 for term in bilingual_terms if term in text)
            
            if found_terms >= 2:
                score += 0.3
            elif found_terms >= 1:
                score += 0.15
        except Exception:
            pass
        
        signature_score = self._detect_signature_area(image)
        score += signature_score * 0.15
        
        hologram_score = self._detect_hologram(image)
        score += hologram_score * 0.2
        
        return min(1.0, score)
    
    def _detect_skin_tone(self, image: np.ndarray) -> float:
        if len(image.shape) != 3:
            return 0.0
        
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        skin_mask = cv2.inRange(hsv, self._skin_lower, self._skin_upper)
        
        skin_pixels = np.sum(skin_mask > 0)
        total_pixels = image.shape[0] * image.shape[1]
        
        return skin_pixels / total_pixels if total_pixels > 0 else 0.0
    
    def _detect_signature_area(self, image: np.ndarray) -> float:
        h, w = image.shape[:2]
        
        sig_x = int(w * 0.55)
        sig_y = int(h * 0.50)
        sig_roi = image[sig_y:, sig_x:]
        
        if sig_roi.size == 0:
            return 0.0
        
        gray = cv2.cvtColor(sig_roi, cv2.COLOR_BGR2GRAY) if len(sig_roi.shape) == 3 else sig_roi
        edges = cv2.Canny(gray, 50, 150)
        
        edge_density = np.sum(edges > 0) / edges.size
        
        if 0.05 < edge_density < 0.25:
            return 0.8
        elif edge_density > 0.02:
            return 0.4
        return 0.0
    
    def _detect_hologram(self, image: np.ndarray) -> float:
        if len(image.shape) != 3:
            return 0.0
        
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        s_channel = hsv[:, :, 1]
        v_channel = hsv[:, :, 2]
        
        high_sat_bright = (s_channel > 100) & (v_channel > 200)
        ratio = np.sum(high_sat_bright) / image.size
        
        if ratio > 0.01:
            return 0.6
        return 0.0
    
    def _detect_dni_old(self, image: np.ndarray) -> float:
        h, w = image.shape[:2]
        score = 0.0
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        std_dev = np.std(gray)
        
        if std_dev < 50:
            score += 0.2
        
        photo_roi_x = int(w * 0.60)
        photo_roi = image[:, photo_roi_x:]
        
        if photo_roi.size > 0:
            skin_score = self._detect_skin_tone(photo_roi)
            if skin_score > 0.1:
                score += 0.2
        
        try:
            import pytesseract
            text = pytesseract.image_to_string(gray, config='--psm 6').upper()
            
            if 'NUMERO DE DOCUMENTO' in text or 'DOCUMENTO NACIONAL' in text:
                score += 0.4
            elif 'DOCUMENTO' in text:
                score += 0.2
        except Exception:
            pass
        
        return min(1.0, score)
    
    def _decide_variant(self, signals: HeuristicSignals) -> tuple[str, float]:
        if signals.pdf417_score >= PDF417_THRESHOLD:
            return "dni_new_back", signals.pdf417_score
        
        if signals.mrz_score >= MRZ_THRESHOLD:
            return "dni_new_front", signals.mrz_score
        
        if signals.dni_front_score >= DNI_FRONT_THRESHOLD:
            return "dni_new_front", signals.dni_front_score
        
        if signals.dni_old_score >= DNI_OLD_THRESHOLD:
            return "dni_old", signals.dni_old_score
        
        best_score = max(
            signals.pdf417_score,
            signals.mrz_score,
            signals.dni_front_score,
            signals.dni_old_score,
        )
        
        return "unknown", best_score

import re
import cv2
import numpy as np
from dataclasses import dataclass, field

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
        self._skin_lower_hsv = np.array([0, 20, 70], dtype=np.uint8)
        self._skin_upper_hsv = np.array([20, 255, 255], dtype=np.uint8)
        self._skin_lower_ycrcb = np.array([0, 135, 85], dtype=np.uint8)
        self._skin_upper_ycrcb = np.array([255, 180, 135], dtype=np.uint8)
    
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
        
        signals.mrz_score = self._detect_mrz_geometry(image)
        if signals.mrz_score >= MRZ_THRESHOLD:
            signals.notes.append("MRZ geometry detected")
        
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
        
        aspect_score = self._calculate_barcode_aspect(roi)
        
        pdf417_score = (
            0.4 * density_score +
            0.3 * repetition_score +
            0.15 * position_score +
            0.15 * aspect_score
        )
        
        return min(1.0, pdf417_score)
    
    def _calculate_barcode_density(self, binary: np.ndarray) -> float:
        total_pixels = binary.size
        if total_pixels == 0:
            return 0.0
        
        black_pixels = np.sum(binary == 0)
        white_pixels = np.sum(binary == 255)
        
        if max(black_pixels, white_pixels) == 0:
            return 0.0
        
        ratio = min(black_pixels, white_pixels) / max(black_pixels, white_pixels)
        
        if 0.35 < ratio < 0.65:
            return ratio * 1.5
        return ratio * 0.8
    
    def _calculate_vertical_repetition(self, binary: np.ndarray) -> float:
        if binary.shape[0] < 10 or binary.shape[1] < 20:
            return 0.0
        
        transitions = []
        sample_rows = min(50, binary.shape[0])
        
        for row in range(sample_rows):
            row_data = binary[row, :]
            diff = np.abs(np.diff(row_data.astype(np.int16)))
            transition_count = np.sum(diff > 127)
            transitions.append(transition_count)
        
        if not transitions:
            return 0.0
        
        avg_transitions = np.mean(transitions)
        std_transitions = np.std(transitions)
        
        if avg_transitions < 15:
            return 0.0
        
        consistency = 1 - (std_transitions / avg_transitions) if avg_transitions > 0 else 0
        density = min(1.0, avg_transitions / 80)
        
        return min(1.0, (consistency * 0.6 + density * 0.4))
    
    def _calculate_position_score(self, roi_x: int, roi_y: int, w: int, h: int) -> float:
        x_ratio = roi_x / w if w > 0 else 0
        y_ratio = roi_y / h if h > 0 else 0
        
        if x_ratio >= 0.55 and y_ratio >= 0.50:
            return 1.0
        elif x_ratio >= 0.45 and y_ratio >= 0.40:
            return 0.7
        else:
            return 0.3
    
    def _calculate_barcode_aspect(self, roi: np.ndarray) -> float:
        h, w = roi.shape[:2]
        if h == 0:
            return 0.0
        
        aspect = w / h
        
        if 2.5 <= aspect <= 3.5:
            return 1.0
        elif 2.0 <= aspect <= 4.0:
            return 0.6
        else:
            return 0.2
    
    def _detect_mrz_geometry(self, image: np.ndarray) -> float:
        h, w = image.shape[:2]
        
        roi_y = int(h * 0.70)
        roi = image[roi_y:, :]
        
        if roi.size == 0:
            return 0.0
        
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
        
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
        dilated = cv2.dilate(binary, kernel, iterations=2)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        horizontal_strips = []
        roi_h, roi_w = roi.shape[:2]
        
        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour)
            
            aspect = cw / ch if ch > 0 else 0
            width_ratio = cw / roi_w if roi_w > 0 else 0
            
            if aspect > 8 and width_ratio > 0.6:
                horizontal_strips.append((x, y, cw, ch))
        
        if len(horizontal_strips) >= 2:
            horizontal_strips.sort(key=lambda s: s[1])
            
            y_positions = [s[1] for s in horizontal_strips[:3]]
            if len(y_positions) >= 2:
                gaps = np.diff(y_positions)
                if len(gaps) > 0 and np.std(gaps) < 15:
                    return 0.85
            
            return 0.70
        elif len(horizontal_strips) == 1:
            return 0.40
        
        return 0.0
    
    def _detect_dni_front(self, image: np.ndarray) -> float:
        h, w = image.shape[:2]
        score = 0.0
        
        photo_x = int(w * 0.05)
        photo_y = int(h * 0.15)
        photo_w = int(w * 0.35)
        photo_h = int(h * 0.65)
        
        photo_roi = image[photo_y:photo_y+photo_h, photo_x:photo_x+photo_w]
        
        if photo_roi.size > 0:
            skin_score = self._detect_skin_tone(photo_roi)
            if skin_score > 0.15:
                score += 0.35
            elif skin_score > 0.08:
                score += 0.20
            
            photo_aspect = photo_w / photo_h if photo_h > 0 else 0
            if 0.65 < photo_aspect < 0.85:
                score += 0.10
        
        sig_x = int(w * 0.50)
        sig_y = int(h * 0.55)
        sig_roi = image[sig_y:, sig_x:]
        
        if sig_roi.size > 0:
            signature_score = self._detect_signature_texture(sig_roi)
            score += signature_score * 0.20
        
        hologram_score = self._detect_hologram(image)
        score += hologram_score * 0.20
        
        structure_score = self._detect_card_structure(image)
        score += structure_score * 0.15
        
        return min(1.0, score)
    
    def _detect_skin_tone(self, image: np.ndarray) -> float:
        if len(image.shape) != 3:
            return 0.0
        
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        skin_mask_hsv = cv2.inRange(hsv, self._skin_lower_hsv, self._skin_upper_hsv)
        
        ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
        skin_mask_ycrcb = cv2.inRange(ycrcb, self._skin_lower_ycrcb, self._skin_upper_ycrcb)
        
        skin_mask = cv2.bitwise_and(skin_mask_hsv, skin_mask_ycrcb)
        
        skin_pixels = np.sum(skin_mask > 0)
        total_pixels = image.shape[0] * image.shape[1]
        
        return skin_pixels / total_pixels if total_pixels > 0 else 0.0
    
    def _detect_signature_texture(self, image: np.ndarray) -> float:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        edges = cv2.Canny(gray, 50, 150)
        
        edge_density = np.sum(edges > 0) / edges.size if edges.size > 0 else 0
        
        if 0.03 < edge_density < 0.20:
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if 5 < len(contours) < 100:
                return 0.8
            elif len(contours) > 2:
                return 0.5
        
        return 0.0
    
    def _detect_hologram(self, image: np.ndarray) -> float:
        if len(image.shape) != 3:
            return 0.0
        
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        s_channel = hsv[:, :, 1]
        v_channel = hsv[:, :, 2]
        
        high_sat_bright = (s_channel > 100) & (v_channel > 180)
        ratio = np.sum(high_sat_bright) / (image.shape[0] * image.shape[1])
        
        if ratio > 0.015:
            return 0.7
        elif ratio > 0.008:
            return 0.4
        return 0.0
    
    def _detect_card_structure(self, image: np.ndarray) -> float:
        h, w = image.shape[:2]
        
        aspect = w / h if h > 0 else 0
        
        if 1.4 < aspect < 1.7:
            return 0.8
        elif 1.3 < aspect < 1.8:
            return 0.5
        return 0.2
    
    def _detect_dni_old(self, image: np.ndarray) -> float:
        h, w = image.shape[:2]
        score = 0.0
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        std_dev = np.std(gray)
        if std_dev < 45:
            score += 0.25
        elif std_dev < 55:
            score += 0.15
        
        photo_x = int(w * 0.60)
        photo_roi = image[:, photo_x:]
        
        if photo_roi.size > 0 and len(photo_roi.shape) == 3:
            skin_score = self._detect_skin_tone(photo_roi)
            if skin_score > 0.12:
                score += 0.30
            elif skin_score > 0.06:
                score += 0.15
        
        text_region = gray[:int(h * 0.6), :int(w * 0.55)]
        if text_region.size > 0:
            edges = cv2.Canny(text_region, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            
            if 0.02 < edge_density < 0.15:
                score += 0.25
        
        aspect = w / h if h > 0 else 0
        if 1.4 < aspect < 1.7:
            score += 0.10
        
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

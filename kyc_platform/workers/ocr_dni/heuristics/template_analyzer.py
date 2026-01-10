import json
import os
from typing import Any, Optional
from pathlib import Path
from PIL import Image
import numpy as np

try:
    import cv2
    cv2_available = True
except ImportError:
    cv2 = None
    cv2_available = False

from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)

TEMPLATES_PATH = Path(__file__).parent.parent.parent.parent.parent / "data" / "reference_samples" / "dni" / "templates.json"


class TemplateAnalyzer:
    
    def __init__(self):
        self.templates = self._load_templates()
        self.variant_detector = VariantDetector()
    
    def _load_templates(self) -> dict:
        try:
            if TEMPLATES_PATH.exists():
                with open(TEMPLATES_PATH, "r") as f:
                    return json.load(f)
            else:
                logger.warning(f"Templates file not found: {TEMPLATES_PATH}")
                return {"variants": {}}
        except Exception as e:
            logger.error(f"Failed to load templates: {e}")
            return {"variants": {}}
    
    def analyze(
        self,
        image: np.ndarray,
        side: str = "front",
        variant: Optional[str] = None,
    ) -> dict[str, Any]:
        if not cv2_available:
            return self._empty_result("opencv_unavailable")
        
        if variant is None:
            variant = self.variant_detector.detect(image, side)
        
        if variant not in self.templates.get("variants", {}):
            return self._empty_result(f"unknown_variant: {variant}")
        
        template = self.templates["variants"][variant]
        side_template = template.get(side, {})
        zones = side_template.get("zones", {})
        
        if not zones:
            return self._empty_result(f"no_zones_defined: {variant}/{side}")
        
        h, w = image.shape[:2]
        zone_results = {}
        total_score = 0.0
        zone_count = 0
        
        for zone_name, zone_config in zones.items():
            if zone_config.get("optional", False):
                continue
            
            coords = zone_config["coords"]
            x = int(w * coords[0] / 100)
            y = int(h * coords[1] / 100)
            zone_w = int(w * coords[2] / 100)
            zone_h = int(h * coords[3] / 100)
            
            x = max(0, min(x, w - 1))
            y = max(0, min(y, h - 1))
            zone_w = min(zone_w, w - x)
            zone_h = min(zone_h, h - y)
            
            if zone_w < 10 or zone_h < 10:
                zone_results[zone_name] = {
                    "score": 0.0,
                    "flags": ["zone_too_small"],
                    "verified": False,
                }
                continue
            
            zone_image = image[y:y+zone_h, x:x+zone_w]
            
            verifications = zone_config.get("verification", [])
            zone_score, zone_flags = self._verify_zone(zone_name, zone_image, verifications)
            
            zone_results[zone_name] = {
                "score": round(zone_score, 2),
                "flags": zone_flags,
                "verified": zone_score >= 0.5,
                "coords": {"x": x, "y": y, "w": zone_w, "h": zone_h},
            }
            
            total_score += zone_score
            zone_count += 1
        
        overall_score = total_score / zone_count if zone_count > 0 else 0.0
        
        critical_zones = self._get_critical_zones(side)
        critical_passed = all(
            zone_results.get(z, {}).get("verified", False) 
            for z in critical_zones if z in zone_results
        )
        
        return {
            "template_score": round(overall_score, 2),
            "variant_detected": variant,
            "side": side,
            "zones_analyzed": zone_count,
            "zones_passed": sum(1 for z in zone_results.values() if z.get("verified", False)),
            "critical_zones_passed": critical_passed,
            "zone_results": zone_results,
            "flags": self._generate_flags(zone_results, critical_passed),
        }
    
    def _verify_zone(self, zone_name: str, zone_image: np.ndarray, verifications: list) -> tuple[float, list]:
        scores = []
        flags = []
        
        for verification in verifications:
            score, flag = self._run_verification(zone_name, zone_image, verification)
            scores.append(score)
            if flag:
                flags.append(flag)
        
        if not scores:
            return self._basic_zone_check(zone_image)
        
        avg_score = sum(scores) / len(scores)
        return avg_score, flags
    
    def _run_verification(self, zone_name: str, zone_image: np.ndarray, verification: str) -> tuple[float, Optional[str]]:
        if verification == "saturation_check":
            return self._check_saturation(zone_image)
        elif verification == "iridescence":
            return self._check_iridescence(zone_image)
        elif verification == "color_variance":
            return self._check_color_variance(zone_image)
        elif verification == "face_detection":
            return self._check_face_presence(zone_image)
        elif verification == "border_integrity":
            return self._check_border_integrity(zone_image)
        elif verification == "fingerprint_presence":
            return self._check_fingerprint(zone_image)
        elif verification == "text_presence":
            return self._check_text_presence(zone_image)
        elif verification == "barcode_decode":
            return self._check_barcode(zone_image)
        elif verification == "shape_recognition":
            return self._check_shape(zone_image, zone_name)
        elif verification == "color_check":
            return self._check_expected_colors(zone_image, zone_name)
        elif verification == "pattern_presence":
            return self._check_pattern(zone_image)
        else:
            return 0.7, None
    
    def _check_saturation(self, zone_image: np.ndarray) -> tuple[float, Optional[str]]:
        try:
            hsv = cv2.cvtColor(zone_image, cv2.COLOR_BGR2HSV)
            saturation = hsv[:, :, 1]
            mean_sat = np.mean(saturation)
            high_sat_ratio = np.sum(saturation > 80) / saturation.size
            
            if high_sat_ratio > 0.1 and mean_sat > 40:
                return 0.9, None
            elif high_sat_ratio > 0.05 or mean_sat > 30:
                return 0.6, "low_saturation"
            else:
                return 0.3, "very_low_saturation"
        except Exception:
            return 0.5, "saturation_check_failed"
    
    def _check_iridescence(self, zone_image: np.ndarray) -> tuple[float, Optional[str]]:
        try:
            hsv = cv2.cvtColor(zone_image, cv2.COLOR_BGR2HSV)
            hue = hsv[:, :, 0]
            hue_variance = np.var(hue)
            
            if hue_variance > 500:
                return 0.9, None
            elif hue_variance > 200:
                return 0.7, None
            else:
                return 0.4, "low_hue_variance"
        except Exception:
            return 0.5, "iridescence_check_failed"
    
    def _check_color_variance(self, zone_image: np.ndarray) -> tuple[float, Optional[str]]:
        try:
            hsv = cv2.cvtColor(zone_image, cv2.COLOR_BGR2HSV)
            color_variance = np.var(hsv[:, :, 0]) + np.var(hsv[:, :, 1])
            
            if color_variance > 1000:
                return 0.9, None
            elif color_variance > 300:
                return 0.6, None
            else:
                return 0.3, "low_color_variance"
        except Exception:
            return 0.5, "color_variance_check_failed"
    
    def _check_face_presence(self, zone_image: np.ndarray) -> tuple[float, Optional[str]]:
        try:
            gray = cv2.cvtColor(zone_image, cv2.COLOR_BGR2GRAY)
            
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            
            color_variance = np.var(zone_image)
            
            if edge_density > 0.05 and color_variance > 500:
                return 0.8, None
            elif edge_density > 0.02:
                return 0.5, "weak_photo_signal"
            else:
                return 0.2, "no_face_detected"
        except Exception:
            return 0.5, "face_detection_failed"
    
    def _check_border_integrity(self, zone_image: np.ndarray) -> tuple[float, Optional[str]]:
        try:
            gray = cv2.cvtColor(zone_image, cv2.COLOR_BGR2GRAY)
            
            top_row = gray[0:5, :]
            bottom_row = gray[-5:, :]
            left_col = gray[:, 0:5]
            right_col = gray[:, -5:]
            
            border_variance = np.var(top_row) + np.var(bottom_row) + np.var(left_col) + np.var(right_col)
            
            if border_variance < 5000:
                return 0.8, None
            else:
                return 0.5, "irregular_borders"
        except Exception:
            return 0.5, "border_check_failed"
    
    def _check_fingerprint(self, zone_image: np.ndarray) -> tuple[float, Optional[str]]:
        try:
            gray = cv2.cvtColor(zone_image, cv2.COLOR_BGR2GRAY)
            
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            laplacian_var = np.var(laplacian)
            
            if laplacian_var > 100:
                return 0.85, None
            elif laplacian_var > 30:
                return 0.6, "weak_fingerprint"
            else:
                return 0.2, "no_fingerprint_detected"
        except Exception:
            return 0.5, "fingerprint_check_failed"
    
    def _check_text_presence(self, zone_image: np.ndarray) -> tuple[float, Optional[str]]:
        try:
            gray = cv2.cvtColor(zone_image, cv2.COLOR_BGR2GRAY)
            
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            black_ratio = 1 - (np.sum(binary > 127) / binary.size)
            
            if 0.05 < black_ratio < 0.5:
                return 0.8, None
            elif 0.02 < black_ratio < 0.7:
                return 0.5, "unusual_text_density"
            else:
                return 0.2, "no_text_detected"
        except Exception:
            return 0.5, "text_check_failed"
    
    def _check_barcode(self, zone_image: np.ndarray) -> tuple[float, Optional[str]]:
        try:
            gray = cv2.cvtColor(zone_image, cv2.COLOR_BGR2GRAY)
            
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
            
            white_ratio = np.sum(binary > 127) / binary.size
            black_ratio = 1 - white_ratio
            
            if 0.3 < black_ratio < 0.7:
                horizontal_var = np.var(np.mean(binary, axis=0))
                if horizontal_var > 5000:
                    return 0.9, None
                else:
                    return 0.6, "weak_barcode_pattern"
            else:
                return 0.3, "no_barcode_detected"
        except Exception:
            return 0.5, "barcode_check_failed"
    
    def _check_shape(self, zone_image: np.ndarray, zone_name: str) -> tuple[float, Optional[str]]:
        try:
            if "argentina" in zone_name.lower() or "map" in zone_name.lower():
                hsv = cv2.cvtColor(zone_image, cv2.COLOR_BGR2HSV)
                green_mask = cv2.inRange(hsv, (35, 30, 30), (85, 255, 255))
                dark_mask = cv2.inRange(zone_image, (0, 0, 0), (80, 80, 80))
                
                shape_ratio = max(np.sum(green_mask > 0), np.sum(dark_mask > 0)) / zone_image.size * 3
                
                if shape_ratio > 0.15:
                    return 0.85, None
                elif shape_ratio > 0.05:
                    return 0.5, "weak_map_shape"
                else:
                    return 0.2, "no_map_detected"
            
            return 0.7, None
        except Exception:
            return 0.5, "shape_check_failed"
    
    def _check_expected_colors(self, zone_image: np.ndarray, zone_name: str) -> tuple[float, Optional[str]]:
        try:
            hsv = cv2.cvtColor(zone_image, cv2.COLOR_BGR2HSV)
            
            if "green" in zone_name.lower():
                mask = cv2.inRange(hsv, (35, 30, 30), (85, 255, 255))
            elif "pink" in zone_name.lower() or "decorative" in zone_name.lower():
                mask = cv2.inRange(hsv, (140, 20, 100), (180, 255, 255))
            else:
                return 0.7, None
            
            ratio = np.sum(mask > 0) / mask.size
            if ratio > 0.1:
                return 0.85, None
            else:
                return 0.4, "expected_color_not_found"
        except Exception:
            return 0.5, "color_check_failed"
    
    def _check_pattern(self, zone_image: np.ndarray) -> tuple[float, Optional[str]]:
        try:
            hsv = cv2.cvtColor(zone_image, cv2.COLOR_BGR2HSV)
            color_variance = np.var(hsv)
            
            if color_variance > 500:
                return 0.8, None
            else:
                return 0.4, "weak_pattern"
        except Exception:
            return 0.5, "pattern_check_failed"
    
    def _basic_zone_check(self, zone_image: np.ndarray) -> tuple[float, list]:
        try:
            mean_brightness = np.mean(zone_image)
            variance = np.var(zone_image)
            
            if 20 < mean_brightness < 240 and variance > 100:
                return 0.7, []
            else:
                return 0.4, ["unusual_zone_content"]
        except Exception:
            return 0.5, ["zone_check_failed"]
    
    def _get_critical_zones(self, side: str) -> list[str]:
        if side == "front":
            return ["photo", "document_number", "barcode_pdf417", "hologram_sun"]
        else:
            return ["mrz", "fingerprint", "hologram_circle", "cuil"]
    
    def _generate_flags(self, zone_results: dict, critical_passed: bool) -> list[str]:
        flags = []
        
        if not critical_passed:
            flags.append("critical_zones_failed")
        
        failed_zones = [name for name, result in zone_results.items() if not result.get("verified", False)]
        if len(failed_zones) > len(zone_results) / 2:
            flags.append("majority_zones_failed")
        
        for zone_name, result in zone_results.items():
            for flag in result.get("flags", []):
                if flag and flag not in flags:
                    flags.append(f"{zone_name}:{flag}")
        
        return flags[:10]
    
    def _empty_result(self, reason: str) -> dict[str, Any]:
        return {
            "template_score": None,
            "variant_detected": None,
            "side": None,
            "zones_analyzed": 0,
            "zones_passed": 0,
            "critical_zones_passed": False,
            "zone_results": {},
            "flags": [f"analysis_unavailable: {reason}"],
        }


class VariantDetector:
    
    def detect(self, image: np.ndarray, side: str = "front") -> str:
        if not cv2_available:
            return "nuevo_2019"
        
        try:
            h, w = image.shape[:2]
            
            if side == "front":
                return self._detect_front_variant(image, h, w)
            else:
                return self._detect_back_variant(image, h, w)
        except Exception as e:
            logger.warning(f"Variant detection failed: {e}, defaulting to nuevo_2019")
            return "nuevo_2019"
    
    def _detect_front_variant(self, image: np.ndarray, h: int, w: int) -> str:
        has_pink = self._check_pink_presence(image)
        if has_pink:
            return "nuevo_2023"
        
        is_antiguo = self._check_antiguo_layout(image, h, w)
        if is_antiguo:
            return "antiguo"
        
        center_region = image[int(h*0.4):int(h*0.7), int(w*0.3):int(w*0.6)]
        has_face_in_sun = self._check_face_in_hologram(center_region)
        
        if has_face_in_sun:
            return "nuevo_2016"
        
        return "nuevo_2019"
    
    def _check_antiguo_layout(self, image: np.ndarray, h: int, w: int) -> bool:
        try:
            right_photo_region = image[int(h*0.05):int(h*0.65), int(w*0.52):int(w*0.98)]
            left_photo_region = image[int(h*0.05):int(h*0.55), 0:int(w*0.30)]
            
            def has_skin_tones(region):
                hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
                skin_mask1 = cv2.inRange(hsv, (0, 20, 70), (20, 255, 255))
                skin_mask2 = cv2.inRange(hsv, (0, 10, 100), (25, 150, 255))
                skin_ratio = (np.sum(skin_mask1 > 0) + np.sum(skin_mask2 > 0)) / (2 * region.size / 3)
                return skin_ratio
            
            right_skin = has_skin_tones(right_photo_region)
            left_skin = has_skin_tones(left_photo_region)
            
            if right_skin > 0.08 and right_skin > left_skin * 1.2:
                return True
            
            bottom_region = image[int(h*0.72):h, :]
            gray = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2GRAY)
            
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            row_profile = np.mean(binary, axis=1)
            transitions = np.sum(np.abs(np.diff(row_profile)) > 40)
            
            if transitions >= 4:
                return True
            
            return False
        except Exception:
            return False
    
    def _get_photo_presence_score(self, region: np.ndarray) -> float:
        try:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            
            color_variance = np.var(region)
            
            h, w = gray.shape
            center_region = gray[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)]
            center_brightness = np.mean(center_region)
            
            skin_like = 80 < center_brightness < 200
            
            score = edge_density * 5
            if color_variance > 500:
                score += 0.2
            if skin_like:
                score += 0.15
            
            return min(1.0, score)
        except Exception:
            return 0.0
    
    def _check_mrz_on_front(self, image: np.ndarray, h: int, w: int) -> bool:
        try:
            bottom_region = image[int(h*0.70):h, :]
            gray = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2GRAY)
            
            _, binary = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)
            dark_ratio = 1 - (np.sum(binary > 127) / binary.size)
            
            if 0.15 < dark_ratio < 0.45:
                horizontal_projection = np.mean(binary, axis=1)
                text_lines = np.sum(np.abs(np.diff(horizontal_projection)) > 30)
                return text_lines >= 3
            return False
        except Exception:
            return False
    
    def _detect_back_variant(self, image: np.ndarray, h: int, w: int) -> str:
        has_pink = self._check_pink_presence(image)
        if has_pink:
            return "nuevo_2023"
        
        mrz_region = image[int(h*0.72):h, :]
        has_mrz = self._check_mrz_presence(mrz_region)
        
        if has_mrz:
            center_hologram = image[int(h*0.25):int(h*0.55), int(w*0.32):int(w*0.58)]
            hsv = cv2.cvtColor(center_hologram, cv2.COLOR_BGR2HSV)
            
            blue_mask = cv2.inRange(hsv, (90, 50, 50), (130, 255, 255))
            blue_ratio = np.sum(blue_mask > 0) / blue_mask.size
            
            hologram_hue_var = np.var(hsv[:, :, 0])
            
            if hologram_hue_var > 600 and blue_ratio > 0.15:
                return "nuevo_2016"
            
            return "nuevo_2019"
        
        return "antiguo"
    
    def _get_barcode_density(self, region: np.ndarray) -> float:
        try:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
            
            dark_ratio = 1 - (np.sum(binary > 127) / binary.size)
            
            vertical_edges = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            edge_strength = np.mean(np.abs(vertical_edges))
            
            if dark_ratio > 0.2 and edge_strength > 20:
                return dark_ratio
            return 0.0
        except Exception:
            return 0.0
    
    def _check_pink_presence(self, image: np.ndarray) -> bool:
        try:
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            pink_mask = cv2.inRange(hsv, (140, 20, 100), (180, 255, 255))
            pink_ratio = np.sum(pink_mask > 0) / pink_mask.size
            return pink_ratio > 0.02
        except Exception:
            return False
    
    def _get_edge_density(self, region: np.ndarray) -> float:
        try:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            return np.sum(edges > 0) / edges.size
        except Exception:
            return 0.0
    
    def _check_face_in_hologram(self, region: np.ndarray) -> bool:
        try:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            
            circles = cv2.HoughCircles(
                gray, cv2.HOUGH_GRADIENT, 1, 20,
                param1=50, param2=30, minRadius=10, maxRadius=50
            )
            
            return circles is not None and len(circles[0]) > 0
        except Exception:
            return False
    
    def _check_mrz_presence(self, region: np.ndarray) -> bool:
        try:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            dark_ratio = 1 - (np.sum(binary > 127) / binary.size)
            
            if dark_ratio < 0.08 or dark_ratio > 0.60:
                return False
            
            h, w = gray.shape
            num_rows = 3
            row_height = h // num_rows
            
            text_lines_detected = 0
            for i in range(num_rows):
                row = binary[i*row_height:(i+1)*row_height, :]
                row_dark = 1 - (np.sum(row > 127) / row.size)
                if row_dark > 0.10:
                    text_lines_detected += 1
            
            return text_lines_detected >= 2
        except Exception:
            return False
    
    def _check_text_density(self, region: np.ndarray) -> float:
        try:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
            return np.sum(binary > 0) / binary.size
        except Exception:
            return 0.0


template_analyzer = TemplateAnalyzer()

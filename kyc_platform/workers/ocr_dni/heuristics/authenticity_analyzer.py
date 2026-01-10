import numpy as np
from typing import Any
from PIL import Image

try:
    import cv2
    cv2_available = True
except ImportError:
    cv2 = None
    cv2_available = False

from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class AuthenticityAnalyzer:
    
    def __init__(self):
        self.thresholds = {
            "saturation_min": 0.15,
            "saturation_max": 0.85,
            "laplacian_min": 50.0,
            "glare_max_ratio": 0.15,
            "moire_threshold": 0.3,
        }
    
    def analyze(self, image: Image.Image) -> dict[str, Any]:
        if not cv2_available:
            logger.warning("OpenCV not available, skipping authenticity analysis")
            return self._empty_result()
        
        try:
            img_array = np.array(image.convert("RGB"))
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            saturation = self._analyze_saturation(img_bgr)
            sharpness = self._analyze_sharpness(img_bgr)
            glare = self._analyze_glare(img_bgr)
            moire = self._analyze_moire(img_bgr)
            
            flags = self._generate_flags(saturation, sharpness, glare, moire)
            score = self._calculate_score(saturation, sharpness, glare, moire)
            
            return {
                "authenticity_score": round(score, 2),
                "metrics": {
                    "saturation": round(saturation["mean"], 3),
                    "sharpness": round(sharpness["variance"], 2),
                    "glare_ratio": round(glare["ratio"], 3),
                    "moire_score": round(moire["score"], 3),
                },
                "flags": flags,
                "is_likely_authentic": len(flags) == 0,
            }
        except Exception as e:
            logger.error(f"Authenticity analysis failed: {e}")
            return self._empty_result()
    
    def _analyze_saturation(self, img_bgr: np.ndarray) -> dict[str, float]:
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        saturation_channel = hsv[:, :, 1] / 255.0
        
        return {
            "mean": float(np.mean(saturation_channel)),
            "std": float(np.std(saturation_channel)),
            "low_ratio": float(np.sum(saturation_channel < 0.1) / saturation_channel.size),
        }
    
    def _analyze_sharpness(self, img_bgr: np.ndarray) -> dict[str, float]:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = float(laplacian.var())
        
        return {
            "variance": variance,
            "is_sharp": variance > self.thresholds["laplacian_min"],
        }
    
    def _analyze_glare(self, img_bgr: np.ndarray) -> dict[str, float]:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        
        _, bright_mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        bright_pixels = np.sum(bright_mask > 0)
        total_pixels = gray.size
        bright_ratio = bright_pixels / total_pixels
        
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        low_sat_high_val = (hsv[:, :, 1] < 30) & (hsv[:, :, 2] > 230)
        glare_ratio = float(np.sum(low_sat_high_val) / total_pixels)
        
        return {
            "ratio": glare_ratio,
            "bright_ratio": float(bright_ratio),
            "has_glare": glare_ratio > 0.02,
        }
    
    def _analyze_moire(self, img_bgr: np.ndarray) -> dict[str, float]:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        
        f_transform = np.fft.fft2(gray)
        f_shift = np.fft.fftshift(f_transform)
        magnitude = np.abs(f_shift)
        
        rows, cols = gray.shape
        crow, ccol = rows // 2, cols // 2
        
        mask = np.zeros((rows, cols), np.uint8)
        r_inner = min(rows, cols) // 8
        r_outer = min(rows, cols) // 3
        cv2.circle(mask, (ccol, crow), r_outer, 1, -1)
        cv2.circle(mask, (ccol, crow), r_inner, 0, -1)
        
        mid_freq_energy = np.sum(magnitude * mask)
        total_energy = np.sum(magnitude)
        
        moire_score = mid_freq_energy / total_energy if total_energy > 0 else 0
        
        return {
            "score": float(moire_score),
            "has_moire": moire_score > self.thresholds["moire_threshold"],
        }
    
    def _generate_flags(
        self,
        saturation: dict,
        sharpness: dict,
        glare: dict,
        moire: dict,
    ) -> list[str]:
        flags = []
        
        if saturation["mean"] < self.thresholds["saturation_min"]:
            flags.append("low_saturation")
        
        if sharpness["variance"] < self.thresholds["laplacian_min"]:
            flags.append("low_sharpness")
        
        if glare["ratio"] > self.thresholds["glare_max_ratio"]:
            flags.append("excessive_glare")
        
        if moire["has_moire"]:
            flags.append("moire_pattern_detected")
        
        if saturation["low_ratio"] > 0.5:
            flags.append("possible_photocopy")
        
        return flags
    
    def _calculate_score(
        self,
        saturation: dict,
        sharpness: dict,
        glare: dict,
        moire: dict,
    ) -> float:
        score = 1.0
        
        sat_mean = saturation["mean"]
        if sat_mean < self.thresholds["saturation_min"]:
            score -= 0.25
        elif sat_mean > self.thresholds["saturation_max"]:
            score -= 0.1
        
        if sharpness["variance"] < self.thresholds["laplacian_min"]:
            penalty = min(0.3, (self.thresholds["laplacian_min"] - sharpness["variance"]) / 100)
            score -= penalty
        
        if glare["ratio"] > self.thresholds["glare_max_ratio"]:
            score -= 0.15
        elif glare["has_glare"]:
            score += 0.1
        
        if moire["has_moire"]:
            score -= 0.3
        
        return max(0.0, min(1.0, score))
    
    def _empty_result(self) -> dict[str, Any]:
        return {
            "authenticity_score": None,
            "metrics": {},
            "flags": ["analysis_unavailable"],
            "is_likely_authentic": None,
        }


authenticity_analyzer = AuthenticityAnalyzer()


class CombinedAuthenticityAnalyzer:
    
    def __init__(self):
        self.basic_analyzer = AuthenticityAnalyzer()
        self._template_analyzer = None
    
    @property
    def template_analyzer(self):
        if self._template_analyzer is None:
            from kyc_platform.workers.ocr_dni.heuristics.template_analyzer import TemplateAnalyzer
            self._template_analyzer = TemplateAnalyzer()
        return self._template_analyzer
    
    def analyze(
        self,
        image: Image.Image,
        cv_image: np.ndarray = None,
        side: str = "front",
        use_template: bool = True,
    ) -> dict[str, Any]:
        basic_result = self.basic_analyzer.analyze(image)
        
        template_result = None
        if use_template and cv_image is not None and cv2_available:
            try:
                template_result = self.template_analyzer.analyze(cv_image, side=side)
            except Exception as e:
                logger.warning(f"Template analysis failed: {e}")
                template_result = None
        
        if template_result and template_result.get("template_score") is not None:
            combined_score = (
                basic_result.get("authenticity_score", 0.5) * 0.4 +
                template_result.get("template_score", 0.5) * 0.6
            )
            
            all_flags = basic_result.get("flags", []).copy()
            for flag in template_result.get("flags", []):
                if flag not in all_flags:
                    all_flags.append(flag)
            
            return {
                "authenticity_score": round(combined_score, 2),
                "basic_score": basic_result.get("authenticity_score"),
                "template_score": template_result.get("template_score"),
                "variant_detected": template_result.get("variant_detected"),
                "zones_passed": template_result.get("zones_passed", 0),
                "zones_analyzed": template_result.get("zones_analyzed", 0),
                "critical_zones_passed": template_result.get("critical_zones_passed", False),
                "metrics": basic_result.get("metrics", {}),
                "zone_results": template_result.get("zone_results", {}),
                "flags": all_flags,
                "is_likely_authentic": combined_score >= 0.6 and len(all_flags) <= 3,
            }
        
        return basic_result


combined_authenticity_analyzer = CombinedAuthenticityAnalyzer()

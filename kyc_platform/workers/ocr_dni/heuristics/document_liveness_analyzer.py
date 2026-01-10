import numpy as np
from typing import Any
from PIL import Image
import io
import base64

try:
    import cv2
    cv2_available = True
except ImportError:
    cv2 = None
    cv2_available = False

from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class DocumentLivenessAnalyzer:
    
    def __init__(self):
        self.min_frames = 3
        self.max_frames = 10
        self.thresholds = {
            "reflection_change_min": 0.05,
            "hologram_change_min": 0.03,
            "position_variance_max": 0.3,
        }
    
    def analyze(self, frames_base64: list[str]) -> dict[str, Any]:
        if not cv2_available:
            logger.warning("OpenCV not available, skipping liveness analysis")
            return self._empty_result("opencv_unavailable")
        
        if not frames_base64 or len(frames_base64) < self.min_frames:
            return self._empty_result(
                f"insufficient_frames: need {self.min_frames}, got {len(frames_base64) if frames_base64 else 0}"
            )
        
        if len(frames_base64) > self.max_frames:
            frames_base64 = frames_base64[:self.max_frames]
        
        try:
            frames = self._decode_frames(frames_base64)
            if len(frames) < self.min_frames:
                return self._empty_result("frame_decode_failed")
            
            reflection_analysis = self._analyze_reflection_changes(frames)
            hologram_analysis = self._analyze_hologram_regions(frames)
            motion_analysis = self._analyze_document_motion(frames)
            
            score = self._calculate_liveness_score(
                reflection_analysis, hologram_analysis, motion_analysis
            )
            
            flags = self._generate_flags(
                reflection_analysis, hologram_analysis, motion_analysis
            )
            
            return {
                "liveness_score": round(score, 2),
                "is_live_document": score >= 0.6,
                "frames_analyzed": len(frames),
                "metrics": {
                    "reflection_variance": round(reflection_analysis["variance"], 4),
                    "hologram_change": round(hologram_analysis["change_score"], 4),
                    "motion_detected": motion_analysis["has_motion"],
                },
                "flags": flags,
            }
        except Exception as e:
            logger.error(f"Document liveness analysis failed: {e}")
            return self._empty_result(f"analysis_error: {str(e)}")
    
    def _decode_frames(self, frames_base64: list[str]) -> list[np.ndarray]:
        frames = []
        for i, b64 in enumerate(frames_base64):
            try:
                if "," in b64:
                    b64 = b64.split(",")[1]
                
                image_data = base64.b64decode(b64)
                pil_image = Image.open(io.BytesIO(image_data))
                img_array = np.array(pil_image.convert("RGB"))
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                frames.append(img_bgr)
            except Exception as e:
                logger.warning(f"Failed to decode frame {i}: {e}")
        return frames
    
    def _analyze_reflection_changes(self, frames: list[np.ndarray]) -> dict[str, Any]:
        highlight_intensities = []
        
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            _, highlights = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
            intensity = np.sum(highlights) / highlights.size
            highlight_intensities.append(intensity)
        
        variance = np.var(highlight_intensities)
        mean_change = np.mean(np.abs(np.diff(highlight_intensities)))
        
        return {
            "variance": float(variance),
            "mean_change": float(mean_change),
            "has_reflection_change": variance > self.thresholds["reflection_change_min"],
            "intensities": [float(x) for x in highlight_intensities],
        }
    
    def _analyze_hologram_regions(self, frames: list[np.ndarray]) -> dict[str, Any]:
        color_variances = []
        
        for frame in frames:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            saturation = hsv[:, :, 1]
            value = hsv[:, :, 2]
            
            high_sat_mask = saturation > 100
            high_val_mask = value > 150
            hologram_mask = high_sat_mask & high_val_mask
            
            if np.any(hologram_mask):
                hue_in_hologram = hsv[:, :, 0][hologram_mask]
                color_variances.append(float(np.var(hue_in_hologram)))
            else:
                color_variances.append(0.0)
        
        change_between_frames = []
        for i in range(1, len(color_variances)):
            change = abs(color_variances[i] - color_variances[i-1])
            change_between_frames.append(change)
        
        avg_change = np.mean(change_between_frames) if change_between_frames else 0
        
        return {
            "change_score": float(avg_change),
            "variances": color_variances,
            "has_hologram_change": avg_change > self.thresholds["hologram_change_min"],
        }
    
    def _analyze_document_motion(self, frames: list[np.ndarray]) -> dict[str, Any]:
        if len(frames) < 2:
            return {"has_motion": False, "motion_score": 0.0}
        
        motion_scores = []
        
        for i in range(1, len(frames)):
            prev_gray = cv2.cvtColor(frames[i-1], cv2.COLOR_BGR2GRAY)
            curr_gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
            
            if prev_gray.shape != curr_gray.shape:
                curr_gray = cv2.resize(curr_gray, (prev_gray.shape[1], prev_gray.shape[0]))
            
            diff = cv2.absdiff(prev_gray, curr_gray)
            motion_score = np.mean(diff) / 255.0
            motion_scores.append(float(motion_score))
        
        avg_motion = np.mean(motion_scores)
        
        return {
            "has_motion": avg_motion > 0.01,
            "motion_score": float(avg_motion),
            "frame_differences": motion_scores,
        }
    
    def _calculate_liveness_score(
        self,
        reflection: dict,
        hologram: dict,
        motion: dict,
    ) -> float:
        score = 0.0
        
        if reflection["has_reflection_change"]:
            score += 0.35
        elif reflection["variance"] > 0.02:
            score += 0.15
        
        if hologram["has_hologram_change"]:
            score += 0.35
        elif hologram["change_score"] > 0.01:
            score += 0.15
        
        if motion["has_motion"]:
            motion_val = min(motion["motion_score"] * 10, 0.3)
            score += motion_val
        
        return min(1.0, score)
    
    def _generate_flags(
        self,
        reflection: dict,
        hologram: dict,
        motion: dict,
    ) -> list[str]:
        flags = []
        
        if not reflection["has_reflection_change"]:
            flags.append("no_reflection_change")
        
        if not hologram["has_hologram_change"]:
            flags.append("no_hologram_change")
        
        if not motion["has_motion"]:
            flags.append("no_document_motion")
        
        if reflection["variance"] < 0.001 and hologram["change_score"] < 0.001:
            flags.append("possible_static_image")
        
        return flags
    
    def _empty_result(self, reason: str) -> dict[str, Any]:
        return {
            "liveness_score": None,
            "is_live_document": None,
            "frames_analyzed": 0,
            "metrics": {},
            "flags": [f"analysis_unavailable: {reason}"],
        }


document_liveness_analyzer = DocumentLivenessAnalyzer()

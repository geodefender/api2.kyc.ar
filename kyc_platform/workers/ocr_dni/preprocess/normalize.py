import cv2
import numpy as np

from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)

TARGET_WIDTH = 1200
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_SIZE = (8, 8)


def normalize_image(image: np.ndarray) -> np.ndarray:
    if image is None or image.size == 0:
        raise ValueError("Invalid input image")
    
    normalized = image.copy()
    
    try:
        normalized = _auto_rotate_deskew(normalized)
    except Exception as e:
        logger.warning(f"Deskew failed, continuing: {e}")
    
    try:
        normalized = _trim_margins(normalized)
    except Exception as e:
        logger.warning(f"Trim margins failed, continuing: {e}")
    
    try:
        normalized = _detect_and_crop_document(normalized)
    except Exception as e:
        logger.warning(f"Document crop failed, continuing: {e}")
    
    try:
        normalized = _resize_to_standard(normalized)
    except Exception as e:
        logger.warning(f"Resize failed, continuing: {e}")
    
    try:
        normalized = _apply_clahe(normalized)
    except Exception as e:
        logger.warning(f"CLAHE failed, continuing: {e}")
    
    return normalized


def _auto_rotate_deskew(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10)
    
    if lines is None or len(lines) == 0:
        return image
    
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if -45 < angle < 45:
            angles.append(angle)
    
    if not angles:
        return image
    
    median_angle = np.median(angles)
    
    if abs(median_angle) < 0.5:
        return image
    
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(image, rotation_matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    
    return rotated


def _trim_margins(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    
    _, binary = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    
    coords = cv2.findNonZero(binary)
    if coords is None:
        return image
    
    x, y, w, h = cv2.boundingRect(coords)
    
    padding = 10
    x = max(0, x - padding)
    y = max(0, y - padding)
    w = min(image.shape[1] - x, w + 2 * padding)
    h = min(image.shape[0] - y, h + 2 * padding)
    
    if w < 100 or h < 100:
        return image
    
    return image[y:y+h, x:x+w]


def _detect_and_crop_document(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    
    total_pixels = gray.shape[0] * gray.shape[1]
    white_pixels = np.sum(gray > 240)
    white_ratio = white_pixels / total_pixels
    
    if white_ratio < 0.15:
        return image
    
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.dilate(edges, kernel, iterations=2)
    
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return image
    
    largest_contour = max(contours, key=cv2.contourArea)
    
    contour_area = cv2.contourArea(largest_contour)
    image_area = image.shape[0] * image.shape[1]
    
    if contour_area < 0.3 * image_area:
        return image
    
    x, y, w, h = cv2.boundingRect(largest_contour)
    
    aspect_ratio = w / h if h > 0 else 0
    if aspect_ratio < 1.2 or aspect_ratio > 2.0:
        return image
    
    padding = 5
    x = max(0, x - padding)
    y = max(0, y - padding)
    w = min(image.shape[1] - x, w + 2 * padding)
    h = min(image.shape[0] - y, h + 2 * padding)
    
    cropped = image[y:y+h, x:x+w]
    
    return cropped


def _resize_to_standard(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    
    if w == TARGET_WIDTH:
        return image
    
    scale = TARGET_WIDTH / w
    new_h = int(h * scale)
    
    resized = cv2.resize(image, (TARGET_WIDTH, new_h), interpolation=cv2.INTER_CUBIC)
    return resized


def _apply_clahe(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 2:
        clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_SIZE)
        return clahe.apply(image)
    
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_SIZE)
    l_clahe = clahe.apply(l)
    
    lab_clahe = cv2.merge([l_clahe, a, b])
    result = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)
    
    return result

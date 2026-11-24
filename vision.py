"""Image matching for a fixed region; all arrays use OpenCV BGR ordering."""
import cv2
import numpy as np


def measure(template: np.ndarray, current: np.ndarray, mask: np.ndarray) -> tuple[float, float, float]:
    if template.shape != current.shape or template.ndim != 3:
        raise ValueError('Ảnh hiện tại phải cùng kích thước với ảnh mẫu')
    if mask.shape != template.shape[:2] or not np.any(mask):
        raise ValueError('Mặt nạ trống hoặc không đúng kích thước')
    # Normalized squared error, evaluated only at selected pixels. Unlike correlation,
    # this compares both color and brightness and remains stable for solid colors.
    selected = mask > 0
    a = template[selected].astype(np.float32)
    b = current[selected].astype(np.float32)
    similarity = max(0.0, 1.0 - float(np.mean((a - b) ** 2)) / (255.0 ** 2))
    brightness = float(np.mean(cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)[selected])) / 255.0
    # Mean of the per-pixel maximum absolute B/G/R-channel difference.
    # This is a concrete, brightness-sensitive color comparison; uniform RGB
    # differences are not diluted by unchanged channels.
    color_similarity = max(0.0, min(1.0, 1.0 - float(np.mean(np.max(np.abs(a-b), axis=1))) / 255.0))
    return similarity, brightness, color_similarity


def score(template: np.ndarray, current: np.ndarray, mask: np.ndarray) -> tuple[float, float]:
    """Compatibility helper retaining the legacy two-value public API."""
    similarity,brightness,_ = measure(template,current,mask)
    return similarity,brightness

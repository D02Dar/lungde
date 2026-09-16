from __future__ import annotations

import cv2
import numpy as np
from .video import VideoData
from ..schemas import CaptureMetadata, NormalizedRoi, PixelRoi


def normalized_to_pixels(roi: NormalizedRoi, width: int, height: int) -> PixelRoi:
    x = max(0, min(width - 1, round(roi.x * width)))
    y = max(0, min(height - 1, round(roi.y * height)))
    right = max(x + 1, min(width, round((roi.x + roi.width) * width)))
    bottom = max(y + 1, min(height, round((roi.y + roi.height) * height)))
    return PixelRoi(x=x, y=y, width=right - x, height=bottom - y)


def ensure_inside(inner: PixelRoi, outer: PixelRoi) -> None:
    outside = (inner.x < outer.x or inner.y < outer.y or
               inner.x + inner.width > outer.x + outer.width or
               inner.y + inner.height > outer.y + outer.height)
    if outside:
        raise ValueError("Analysis ROI must stay inside the operator capture box")
    if inner.width < 8 or inner.height < 4:
        raise ValueError("Manual ROI is too small")


def clip_pixel_roi(roi: PixelRoi, width: int, height: int) -> PixelRoi:
    x = max(0, min(width - 1, roi.x))
    y = max(0, min(height - 1, roi.y))
    right = max(x + 1, min(width, roi.x + roi.width))
    bottom = max(y + 1, min(height, roi.y + roi.height))
    return PixelRoi(x=x, y=y, width=right - x, height=bottom - y)


def locate_jugular_notch(video: VideoData, metadata: CaptureMetadata) -> tuple[PixelRoi, float]:
    capture_roi = normalized_to_pixels(metadata.roi, video.width, video.height)
    sample_count = min(video.frame_count, max(5, round(video.fps)))
    gray_stack = []
    for decoded in video.iter_frames():
        frame = decoded.frame
        crop = frame[capture_roi.y:capture_roi.y + capture_roi.height,
                     capture_roi.x:capture_roi.x + capture_roi.width]
        gray_stack.append(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))
        if len(gray_stack) >= sample_count:
            break
    if not gray_stack:
        return fallback_roi(capture_roi), 0.0
    median = np.median(np.stack(gray_stack), axis=0).astype(np.uint8)
    edges = cv2.Canny(cv2.GaussianBlur(median, (7, 7), 0), 40, 120)
    h, w = median.shape
    y0, y1 = int(h * 0.08), max(int(h * 0.36), int(h * 0.08) + 4)
    x0, x1 = int(w * 0.2), max(int(w * 0.8), int(w * 0.2) + 8)
    band = edges[y0:y1, x0:x1]
    if band.size == 0:
        return fallback_roi(capture_roi), 0.0

    row_energy = band.mean(axis=1) / 255.0
    col_energy = band.mean(axis=0) / 255.0
    row = int(np.argmax(row_energy))
    centre = band.shape[1] // 2
    radius = max(2, band.shape[1] // 4)
    lo, hi = max(0, centre - radius), min(len(col_energy), centre + radius + 1)
    col = lo + int(np.argmax(col_energy[lo:hi]))
    roi_w = max(16, round(capture_roi.width * 0.30))
    roi_h = max(8, round(capture_roi.height * 0.12))
    cx, cy = capture_roi.x + x0 + col, capture_roi.y + y0 + row
    x = max(capture_roi.x, min(cx - roi_w // 2, capture_roi.x + capture_roi.width - roi_w))
    y = max(capture_roi.y, min(cy - roi_h // 3, capture_roi.y + capture_roi.height - roi_h))
    edge_score = float(min(1.0, row_energy[row] * 2.2))
    centre_score = float(max(0.0, 1.0 - abs(col - centre) / max(1, band.shape[1] * 0.5)))
    temporal_score = temporal_stability(gray_stack, x - capture_roi.x, y - capture_roi.y, roi_w, roi_h)
    confidence = float(np.clip(0.45 * edge_score + 0.30 * centre_score + 0.25 * temporal_score, 0, 1))
    return PixelRoi(x=x, y=y, width=roi_w, height=roi_h), confidence


def temporal_stability(frames: list[np.ndarray], x: int, y: int, width: int, height: int) -> float:
    means = [float(frame[y:y+height, x:x+width].mean()) for frame in frames if frame[y:y+height, x:x+width].size]
    if len(means) < 2:
        return 0.0
    return float(np.clip(1.0 - np.std(means) / 35.0, 0, 1))


def fallback_roi(capture_roi: PixelRoi) -> PixelRoi:
    width = max(16, round(capture_roi.width * 0.30))
    height = max(8, round(capture_roi.height * 0.12))
    return PixelRoi(x=capture_roi.x + (capture_roi.width - width) // 2,
                    y=capture_roi.y + round(capture_roi.height * 0.16),
                    width=width, height=height)

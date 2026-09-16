from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .roi import clip_pixel_roi
from .video import VideoData
from ..schemas import PixelRoi


@dataclass(frozen=True)
class AreaSignal:
    reference_threshold: int
    dark_subject: bool
    search_roi: PixelRoi
    analysis_roi: PixelRoi
    row_selection_method: str
    signal_method: str
    row_profiles: np.ndarray
    raw: np.ndarray
    timestamps_ms: np.ndarray
    selected_rows: np.ndarray
    row_scores: np.ndarray
    valid_frame_ratio: float
    texture_coverage: float
    temporal_coherence: float
    saturation_ratio: float
    highlight_saturation_ratio: float
    noise_estimate: float


def extract_area_signal(
    video: VideoData,
    roi: PixelRoi,
    *,
    reference_seconds: float = 1.0,
    reference_threshold: float | None = None,
    dark_subject: bool | None = None,
    phase_windows: dict[str, tuple[float, float]] | None = None,
) -> AreaSignal:
    clipped = clip_pixel_roi(roi, video.width, video.height)
    reference_count = max(5, min(video.frame_count, round(video.fps * reference_seconds)))
    reference_frames = []
    for decoded in video.iter_frames():
        gray = _gray_crop(decoded.frame, clipped)
        if gray is not None:
            reference_frames.append(gray)
        if len(reference_frames) >= reference_count:
            break
    if len(reference_frames) < 3:
        raise ValueError("Too few valid frames inside ROI")

    reference = np.median(np.stack(reference_frames, axis=0), axis=0).astype(np.uint8)
    inferred_threshold, inferred_dark_subject = _threshold(reference)
    threshold = int(np.clip(round(reference_threshold), 0, 255)) if reference_threshold is not None and np.isfinite(reference_threshold) else inferred_threshold
    if dark_subject is None:
        polarity_candidates = (inferred_dark_subject, not inferred_dark_subject)
        reference_mask = None
        for candidate in polarity_candidates:
            reference_mask = _subject_mask(reference, threshold, candidate)
            if reference_mask is not None:
                dark_subject = candidate
                break
    else:
        reference_mask = _subject_mask(reference, threshold, dark_subject)
    if reference_mask is None:
        raise ValueError("Offline ROI does not contain a stable body silhouette")

    reference_widths = _row_widths(reference_mask)
    minimum_reference_width = max(3.0, clipped.width * 0.08)
    supported_rows = np.flatnonzero(reference_widths >= minimum_reference_width)
    if len(supported_rows) < max(3, round(clipped.height * 0.15)):
        supported_rows = np.flatnonzero(reference_widths > 0)
    width_profiles, timestamps, valid, saturations, highlight_saturations = [], [], 0, [], []
    for decoded in video.iter_frames():
        gray = _gray_crop(decoded.frame, clipped)
        if gray is None:
            continue
        mask = _subject_mask(gray, threshold, dark_subject)
        if mask is None:
            continue
        # Keep every row until all protocol phases are available. Spatial
        # selection happens once, from the phase-constrained Vt/Vc evidence.
        width_profiles.append(_measurement_profile(mask, dark_subject))
        timestamps.append(decoded.timestamp_ms)
        saturations.append(float(np.mean((gray <= 8) | (gray >= 247))))
        highlight_saturations.append(float(np.mean(gray >= 247)))
        valid += 1

    minimum = max(12, round(video.fps * 3))
    if valid < minimum:
        raise ValueError("Too few stable silhouette frames inside ROI")
    timestamps_array = np.asarray(timestamps, dtype=np.float64)
    profile_matrix = np.asarray(width_profiles, dtype=np.float64)
    selected_rows, row_scores, row_selection_method = _select_phase_rows(
        profile_matrix, timestamps_array, reference_widths, supported_rows,
        phase_windows or {}, video.fps,
    )
    raw = np.sum(profile_matrix[:, selected_rows], axis=1)
    changes = np.abs(np.diff(raw))
    first_row, last_row = int(np.min(selected_rows)), int(np.max(selected_rows))
    analysis_roi = PixelRoi(x=clipped.x, y=clipped.y + first_row,
                            width=clipped.width, height=last_row - first_row + 1)
    signal_scale = max(float(np.std(raw)), 1e-9)
    noise = float(np.median(changes)) if len(changes) else 0.0
    coherence = float(np.clip(1.0 - noise / signal_scale, 0.0, 1.0))
    texture_coverage = float(np.count_nonzero(reference_mask) / (clipped.width * clipped.height))
    return AreaSignal(
        reference_threshold=threshold,
        dark_subject=bool(dark_subject),
        search_roi=clipped,
        analysis_roi=analysis_roi,
        row_selection_method=row_selection_method,
        signal_method="dark_row_width" if dark_subject else "light_front_contour",
        row_profiles=profile_matrix,
        raw=raw,
        timestamps_ms=timestamps_array,
        selected_rows=selected_rows,
        row_scores=row_scores,
        valid_frame_ratio=valid / max(1, video.frame_count),
        texture_coverage=texture_coverage,
        temporal_coherence=coherence,
        saturation_ratio=float(np.mean(saturations)),
        highlight_saturation_ratio=float(np.mean(highlight_saturations)),
        noise_estimate=noise,
    )


def _select_phase_rows(
    profiles: np.ndarray,
    timestamps_ms: np.ndarray,
    reference_widths: np.ndarray,
    supported_rows: np.ndarray,
    phase_windows: dict[str, tuple[float, float]],
    fps: float,
) -> tuple[np.ndarray, np.ndarray, str]:
    """Select one anatomical band where both Vt and Vc are well supported.

    The full saved chest ROI remains the segmentation/search region. Restricting
    selection to a continuous inner band avoids chasing isolated arm, shoulder,
    waist, or compression rows.
    """
    height = profiles.shape[1]
    eligible = np.zeros(height, dtype=bool)
    eligible[supported_rows] = True

    def phase(name: str, tail: str | None = None) -> np.ndarray | None:
        window = phase_windows.get(name)
        if not window:
            return None
        start, end = window
        if tail and phase_windows.get(tail):
            end = phase_windows[tail][1]
        selected = profiles[(timestamps_ms >= start * 1000) & (timestamps_ms < end * 1000)]
        return selected if len(selected) >= max(3, round(fps * .5)) else None

    tidal = phase("tidal")
    inhale = phase("maxInhale", "exhalePrep")
    exhale = phase("maxExhale")
    if tidal is None or inhale is None or exhale is None:
        rows = supported_rows if len(supported_rows) else np.arange(height)
        return rows, reference_widths.copy(), "reference_support"

    temporal_noise = np.median(np.abs(np.diff(tidal, axis=0)), axis=0) * 1.4826
    tidal_change = np.percentile(tidal, 90, axis=0) - np.percentile(tidal, 10, axis=0)
    vital_change = np.percentile(inhale, 90, axis=0) - np.percentile(exhale, 10, axis=0)
    denominator = temporal_noise * 4 + 1.0
    vt_support = np.maximum(tidal_change, 0) / denominator
    vc_support = np.maximum(vital_change, 0) / denominator
    # Vt has repeated cycles and is therefore the defensible signal for
    # locating the band. Vc is a secondary support term: choosing the largest
    # one-off maximal manoeuvre directly overfits body sway and made repeated
    # recordings jump between upper- and lower-chest bands.
    scores = vt_support + .08 * vc_support
    scores[~eligible] = 0

    band_height = max(8, round(height * .28))
    first_start = max(0, round(height * .12))
    # Keep the anatomical band locked between runs. Maximising phase amplitude
    # independently for every video caused the band to jump towards the waist
    # whenever body sway was larger than chest motion.
    start, stop = first_start, first_start + band_height
    rows = np.flatnonzero(eligible & (np.arange(height) >= start) & (np.arange(height) < stop))
    if len(rows) < max(4, round(band_height * .7)):
        rows = np.arange(start, stop)
    return rows, scores, "locked_upper_thorax_vt_vc_supported_v5"


def _gray_crop(frame: np.ndarray, roi: PixelRoi) -> np.ndarray | None:
    crop = frame[roi.y:roi.y + roi.height, roi.x:roi.x + roi.width]
    if crop.shape[:2] != (roi.height, roi.width):
        return None
    return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)


def _threshold(gray: np.ndarray) -> tuple[int, bool]:
    threshold, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark = gray <= threshold
    light = gray > threshold
    # A body silhouette normally occupies a minority of the ROI. Choose the
    # candidate that is neither empty nor almost the full background.
    dark_ratio, light_ratio = float(np.mean(dark)), float(np.mean(light))
    dark_score = abs(dark_ratio - 0.42)
    light_score = abs(light_ratio - 0.42)
    return int(threshold), dark_score <= light_score


def _subject_mask(gray: np.ndarray, threshold: int, dark_subject: bool) -> np.ndarray | None:
    binary = (gray <= threshold if dark_subject else gray > threshold).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)
    for candidate in (opened, closed, binary):
        selected = _largest_component_mask(candidate)
        if selected is not None:
            return selected
    return None


def _largest_component_mask(binary: np.ndarray) -> np.ndarray | None:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count <= 1:
        return None
    height, width = binary.shape
    candidates = []
    for index in range(1, count):
        x, y, component_width, component_height, area = stats[index]
        ratio = area / max(1, width * height)
        if ratio < 0.03 or ratio > 0.92:
            continue
        edge_contact = int(x == 0) + int(y == 0) + int(x + component_width >= width) + int(y + component_height >= height)
        candidates.append((area + edge_contact * width * 0.1, index))
    if not candidates:
        return None
    _, selected = max(candidates)
    return labels == selected


def _row_widths(mask: np.ndarray) -> np.ndarray:
    widths = np.zeros(mask.shape[0], dtype=np.float64)
    for y in range(mask.shape[0]):
        nonzero_indices = np.flatnonzero(mask[y, :])
        if len(nonzero_indices):
            widths[y] = float(nonzero_indices[-1] - nonzero_indices[0] + 1)
    return widths


def _row_front_extents(mask: np.ndarray) -> np.ndarray:
    """Measure the anterior contour against the ROI's fixed right anchor.

    The capture guide places the subject's back in the right-hand reference
    band. For a light subject, skin and the rear arm can cross the clothing
    threshold and intermittently join the shirt component. Using only the
    left/anterior edge prevents that rear connection from changing the signal.
    """
    extents = np.zeros(mask.shape[0], dtype=np.float64)
    for y in range(mask.shape[0]):
        nonzero_indices = np.flatnonzero(mask[y, :])
        if len(nonzero_indices):
            extents[y] = float(mask.shape[1] - nonzero_indices[0])
    return extents


def _measurement_profile(mask: np.ndarray, dark_subject: bool) -> np.ndarray:
    # Preserve the proven width signal for dark clothing. Light clothing needs
    # a polarity-specific contour because its rear edge can merge with skin.
    return _row_widths(mask) if dark_subject else _row_front_extents(mask)


def _row_weighted_signal(
    gray: np.ndarray,
    mask: np.ndarray,
    *,
    selected_rows: np.ndarray | None = None,
    reference_widths: np.ndarray | None = None,
) -> float:
    """Compute row-width signal based on body silhouette extent.

    For each row, measure the horizontal width of the body region.
    Sum across all rows. This captures anterior-posterior chest wall
    motion: inhale increases width (chest expands forward), exhale
    decreases width (chest retracts).
    """
    del gray  # Kept in the signature for notebook and caller compatibility.
    widths = _row_widths(mask)
    rows = selected_rows if selected_rows is not None and len(selected_rows) else np.arange(len(widths))
    rows = rows[(rows >= 0) & (rows < len(widths))]
    if reference_widths is not None and len(reference_widths) == len(widths):
        # Chest motion is small relative to ROI width. Clamp only implausible
        # per-row excursions caused by compression blocks or mask edge leaks.
        allowance = max(2.0, mask.shape[1] * 0.08)
        widths[rows] = np.clip(
            widths[rows],
            np.maximum(0.0, reference_widths[rows] - allowance),
            reference_widths[rows] + allowance,
        )
    return float(np.sum(widths[rows]))

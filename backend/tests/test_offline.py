from pathlib import Path

import cv2
import numpy as np

from app.analysis.offline import _measurement_profile, _row_front_extents, _row_weighted_signal, _row_widths, _select_phase_rows, _subject_mask, _threshold, extract_area_signal
from app.analysis.video import read_video
from app.schemas import PixelRoi


def test_recovers_silhouette_area_motion(tmp_path: Path):
    fps, count, height, width = 30.0, 180, 40, 64
    time = np.arange(count) / fps
    path = tmp_path / "textured-motion.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (width, height))
    assert writer.isOpened()
    base = np.full((height, width), 105, dtype=np.uint8)
    for x in range(4, width, 8):
        base[:, x:x + 2] = 175
    expected = np.sin(2 * np.pi * 0.25 * time)
    for displacement in expected:
        transform = np.float32([[1, 0, 2.5 * displacement], [0, 1, 0]])
        gray = cv2.warpAffine(base, transform, (width, height), borderMode=cv2.BORDER_REFLECT)
        frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        writer.write(frame)
    writer.release()

    video = read_video(path, declared_duration_ms=count * 1000 / fps)
    try:
        signal = extract_area_signal(video, PixelRoi(x=0, y=0, width=width, height=height))
        assert len(signal.raw) >= 12
        assert signal.valid_frame_ratio > 0.5
        assert signal.texture_coverage > 0.03
    finally:
        video.close()


def test_row_width_signal_clamps_single_row_edge_leak():
    reference = np.zeros((8, 40), dtype=bool)
    reference[:, 10:30] = True
    noisy = reference.copy()
    noisy[4, 30:40] = True
    rows = np.arange(reference.shape[0])
    reference_widths = _row_widths(reference)

    baseline = _row_weighted_signal(
        np.zeros(reference.shape, dtype=np.uint8),
        reference,
        selected_rows=rows,
        reference_widths=reference_widths,
    )
    stabilized = _row_weighted_signal(
        np.zeros(reference.shape, dtype=np.uint8),
        noisy,
        selected_rows=rows,
        reference_widths=reference_widths,
    )

    assert baseline == 160
    assert stabilized - baseline <= 4, "one leaking row must not dominate the width sum"


def test_light_front_contour_ignores_rear_arm_connection():
    torso = np.zeros((8, 40), dtype=bool)
    torso[:, 10:30] = True
    rear_arm_connected = torso.copy()
    rear_arm_connected[2:6, 30:40] = True
    anterior_expansion = torso.copy()
    anterior_expansion[:, 6:10] = True

    baseline = _row_front_extents(torso)
    assert np.array_equal(_measurement_profile(torso, True), _row_widths(torso))
    assert np.array_equal(_measurement_profile(torso, False), baseline)
    assert np.array_equal(_row_front_extents(rear_arm_connected), baseline)
    assert np.sum(_row_front_extents(anterior_expansion) - baseline) == 32


def test_threshold_and_mask_support_both_subject_polarities():
    dark_subject = np.full((100, 80), 225, dtype=np.uint8)
    dark_subject[10:90, 20:65] = 25
    dark_threshold, is_dark = _threshold(dark_subject)
    dark_mask = _subject_mask(dark_subject, dark_threshold, is_dark)
    assert is_dark is True
    assert dark_mask is not None
    assert dark_mask[50, 40]
    assert not dark_mask[0, 0]

    light_subject = np.full((100, 80), 20, dtype=np.uint8)
    light_subject[10:90, 20:65] = 230
    light_threshold, is_dark = _threshold(light_subject)
    light_mask = _subject_mask(light_subject, light_threshold, is_dark)
    assert is_dark is False
    assert light_mask is not None
    assert light_mask[50, 40]
    assert not light_mask[0, 0]


def test_phase_row_selection_keeps_locked_contiguous_thorax_band():
    fps = 10.0
    time = np.arange(300) / fps
    profiles = np.full((len(time), 100), 20.0)
    band = slice(12, 40)
    tidal = time < 10
    inhale = (time >= 12) & (time < 18)
    exhale = (time >= 20) & (time < 28)
    profiles[tidal, band] += 2 * np.sin(2 * np.pi * .25 * time[tidal, None])
    profiles[inhale, band] += 8
    profiles[exhale, band] -= 8
    rows, scores, method = _select_phase_rows(
        profiles, time * 1000, np.full(100, 20.0), np.arange(100),
        {"tidal": (0, 10), "maxInhale": (12, 18), "maxExhale": (20, 28)}, fps,
    )
    assert method == "locked_upper_thorax_vt_vc_supported_v5"
    assert rows[0] == 12 and rows[-1] == 39
    assert np.all(scores[12:40] > scores[:12].max())

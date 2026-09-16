import numpy as np

from app.analysis.fusion import fuse_signals
from app.schemas import RealtimeSample


def samples(times, values):
    return [RealtimeSample(elapsed_ms=float(time), value=float(value), phase="tidal")
            for time, value in zip(times, values)]


def test_fusion_aligns_matching_paths_without_changing_length_contract():
    times = np.arange(0, 8000, 100, dtype=float)
    values = np.sin(2 * np.pi * 0.25 * times / 1000)
    result = fuse_signals(
        samples(times, values), times, values, {"tidal": (0, 8)},
        realtime_quality=0.6, offline_quality=0.9,
    )
    assert result is not None
    assert result.correlation > 0.99
    assert result.alignment_sign == 1
    assert abs(result.alignment_lag_ms) <= 100
    assert len(result.timestamps_ms) == len(result.realtime_waveform)
    assert len(result.timestamps_ms) == len(result.offline_waveform)
    assert len(result.timestamps_ms) == len(result.primary_waveform)
    assert all(np.isfinite(result.offline_waveform))


def test_fusion_detects_reversed_signal_direction():
    times = np.arange(0, 8000, 100, dtype=float)
    values = np.sin(2 * np.pi * 0.27 * times / 1000) + 0.2 * np.sin(2 * np.pi * 0.11 * times / 1000)
    result = fuse_signals(
        samples(times, values), times, -values, {"tidal": (0, 8)},
        realtime_quality=0.6, offline_quality=0.9,
    )
    assert result is not None
    assert result.correlation > 0.99
    assert result.alignment_sign == -1


def test_fusion_requires_three_seconds_of_overlap():
    times = np.arange(0, 2000, 100, dtype=float)
    values = np.sin(times / 500)
    assert fuse_signals(
        samples(times, values), times, values, {},
        realtime_quality=0.5, offline_quality=0.5,
    ) is None

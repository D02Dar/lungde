from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfiltfilt


def clean_respiratory_signal(values: np.ndarray, timestamps_ms: np.ndarray, fps: float) -> tuple[np.ndarray, np.ndarray]:
    signal = np.asarray(values, dtype=np.float64)
    timestamps = np.asarray(timestamps_ms, dtype=np.float64)
    valid = np.isfinite(signal) & np.isfinite(timestamps)
    signal, timestamps = signal[valid], timestamps[valid]
    if len(signal) < 16:
        raise ValueError("Signal is too short to filter")
    order = np.argsort(timestamps)
    signal, timestamps = signal[order], timestamps[order]
    signal = _hampel(signal, max(3, round(fps * 0.35)))
    # Preserve slow maximal manoeuvres and absolute levels for Vc/Vt.
    # A respiratory bandpass belongs only to the independent RR path.
    window = min(len(signal) // 2 * 2 - 1, max(3, round(fps * 0.3) | 1))
    radius = window // 2
    filtered = np.convolve(np.pad(signal, (radius, radius), mode="edge"), np.ones(window) / window, mode="valid")
    display = filtered.copy()
    return filtered, display


def uniform_samples(values: np.ndarray, timestamps_ms: np.ndarray, fps: float):
    """Resample without losing the video clock; gaps remain explicit diagnostics."""
    values, times = np.asarray(values, dtype=float), np.asarray(timestamps_ms, dtype=float)
    valid = np.isfinite(values) & np.isfinite(times)
    values, times = values[valid], times[valid]
    order = np.argsort(times)
    times, indices = np.unique(times[order], return_index=True)
    values = values[order][indices]
    if len(times) < 16 or not np.isfinite(fps) or fps <= 0:
        raise ValueError("Too few timestamped frames for analysis")
    grid = np.arange(times[0], times[-1] + 0.001, 1000.0 / fps)
    return np.interp(grid, times, values), grid


def butterworth_bandpass(signal: np.ndarray, fs: float, low_hz: float = 0.05, high_hz: float = 2.0, order: int = 3) -> np.ndarray:
    values = np.asarray(signal, dtype=np.float64)
    if values.ndim != 1 or len(values) < 16:
        raise ValueError("Signal is too short to filter")
    nyquist = fs * 0.5
    high = min(high_hz, nyquist * 0.95)
    if low_hz <= 0 or high <= low_hz:
        raise ValueError("Sampling rate is too low for the requested band")
    sos = butter(order, [low_hz, high], btype="bandpass", fs=fs, output="sos")
    padlen = 3 * (2 * len(sos) + 1)
    if len(values) <= padlen:
        raise ValueError("Video is too short for zero-phase respiratory filtering")
    return sosfiltfilt(sos, values)


def _hampel(values: np.ndarray, window: int) -> np.ndarray:
    output = values.copy()
    radius = max(1, window // 2)
    for index, value in enumerate(values):
        left, right = max(0, index - radius), min(len(values), index + radius + 1)
        local = values[left:right]
        median = float(np.median(local))
        scale = float(np.median(np.abs(local - median))) * 1.4826
        if scale > 1e-9 and abs(value - median) > 3.5 * scale:
            output[index] = median
    return output

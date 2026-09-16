from __future__ import annotations

import numpy as np


def smoothed_extremum_index(values: np.ndarray, direction: str, radius: int = 2) -> int:
    """Return the strongest peak/trough after a short edge-safe smoothing pass."""
    signal = np.asarray(values, dtype=np.float64)
    if not len(signal):
        raise ValueError("Cannot find an extremum in an empty signal")
    if len(signal) < 3:
        return int(np.argmin(signal) if direction == "low" else np.argmax(signal))

    radius = min(max(0, int(radius)), (len(signal) - 1) // 2)
    if radius:
        padded = np.pad(signal, (radius, radius), mode="edge")
        kernel = np.ones(radius * 2 + 1, dtype=np.float64) / (radius * 2 + 1)
        signal = np.convolve(padded, kernel, mode="valid")
    return int(np.argmin(signal) if direction == "low" else np.argmax(signal))

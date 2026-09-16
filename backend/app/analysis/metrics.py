from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.signal import find_peaks, periodogram



@dataclass(frozen=True)
class SignalMetrics:
    rr_hz: float | None
    rr_bpm: float | None
    vt_px: float | None
    vc_px: float | None
    ratio: float | None
    snr: float
    periodicity: float


@dataclass(frozen=True)
class StableInterval:
    start_index: int
    end_index: int
    coverage: float
    cycle_count: int


def analyze_signal(signal: np.ndarray, fs: float,
                   phase_windows: dict[str, tuple[float, float]], timestamps_ms: np.ndarray | None = None) -> SignalMetrics:
    values = np.asarray(signal, dtype=np.float64)
    tidal = _window(values, fs, phase_windows.get("tidal"), timestamps_ms)
    rr_values = tidal if tidal is not None else values
    rr_hz, snr = _spectral_rate(rr_values, fs)
    peaks, _ = find_peaks(rr_values, distance=max(1, round(fs * 0.5)),
                          prominence=max(np.std(rr_values) * 0.2, 1e-6))
    periodicity = _periodicity(peaks, fs)
    inhale_window = phase_windows.get("maxInhale")
    exhale_prep = phase_windows.get("exhalePrep")
    if inhale_window and exhale_prep and exhale_prep[0] >= inhale_window[0]:
        inhale_window = (inhale_window[0], exhale_prep[1])
    inhale = _window(values, fs, inhale_window, timestamps_ms)
    exhale = _window(values, fs, phase_windows.get("maxExhale"), timestamps_ms)
    vt = _tidal_amplitude(tidal, fs) if tidal is not None else None
    vc = _vital_amplitude(inhale, exhale, fs) if inhale is not None and exhale is not None else None
    ratio = vc / vt if vc is not None and vt is not None and vt > 1e-12 else None
    return SignalMetrics(rr_hz=rr_hz, rr_bpm=rr_hz * 60 if rr_hz is not None else None,
                         vt_px=vt, vc_px=vc, ratio=ratio, snr=snr, periodicity=periodicity)


def _spectral_rate(values: np.ndarray, fs: float) -> tuple[float | None, float]:
    if len(values) < max(16, round(fs * 4)) or np.std(values) < 1e-9:
        return None, 0.0
    frequencies, power = periodogram(values, fs=fs)
    # Ordinary adult breathing is normally below 0.8 Hz. The wider 0.05-2 Hz
    # filter removes artefacts, while RR selection avoids choosing a motion
    # transient near the lower cutoff or its high-frequency harmonics.
    mask = (frequencies >= 0.08) & (frequencies <= min(0.8, fs * 0.45))
    if not np.any(mask):
        return None, 0.0
    band_f, band_p = frequencies[mask], power[mask]
    local_maxima = np.flatnonzero((band_p >= np.roll(band_p, 1)) & (band_p >= np.roll(band_p, -1)))
    local_maxima = local_maxima[(local_maxima > 0) & (local_maxima < len(band_p) - 1)]
    if not len(local_maxima):
        index = int(np.argmax(band_p))
    else:
        peak_power = float(np.max(band_p[local_maxima]))
        eligible = local_maxima[band_p[local_maxima] >= peak_power * 0.35]
        # Prefer the strongest plausible fundamental above 0.1 Hz. A very low
        # edge peak is commonly residual protocol drift from maximal manoeuvres.
        plausible = eligible[band_f[eligible] >= 0.1]
        pool = plausible if len(plausible) else eligible
        index = int(pool[np.argmax(band_p[pool])])
    total = float(np.sum(band_p))
    snr = float(band_p[index] / total) if total > 0 else 0.0
    return float(band_f[index]), snr


def stable_confidence_interval(signal: np.ndarray, fs: float,
                               phase_windows: dict[str, tuple[float, float]]) -> StableInterval | None:
    values = np.asarray(signal, dtype=np.float64)
    if not np.isfinite(fs) or fs <= 0 or len(values) < 3:
        return None

    tidal_window = phase_windows.get("tidal")
    if tidal_window:
        start_seconds, end_seconds = tidal_window
        left = max(0, round(start_seconds * fs))
        right = min(len(values), round(end_seconds * fs))
    else:
        left, right = 0, len(values)
    tidal = values[left:right]
    if len(tidal) < max(12, round(fs * 4)) or np.std(tidal) < 1e-9:
        return None

    prominence = max(float(np.std(tidal)) * 0.2, 1e-6)
    peaks, _ = find_peaks(tidal, distance=max(1, round(fs * 0.75)), prominence=prominence)
    if len(peaks) < 3:
        return None

    periods = np.diff(peaks).astype(np.float64)
    median_period = float(np.median(periods))
    if median_period <= 0:
        return None
    stable = np.abs(periods - median_period) <= median_period * 0.25

    best_start = best_end = -1
    run_start = 0
    for index in range(len(stable) + 1):
        if index < len(stable) and stable[index]:
            continue
        if index - run_start >= 2 and index - run_start > best_end - best_start:
            best_start, best_end = run_start, index
        run_start = index + 1
    if best_start < 0:
        return None

    start_index = left + int(peaks[best_start])
    end_index = left + int(peaks[best_end])
    cycle_count = best_end - best_start
    interval_samples = end_index - start_index
    available_samples = max(1, right - left - 1)
    coverage = float(np.clip(interval_samples / available_samples, 0, 1))
    return StableInterval(start_index=start_index, end_index=end_index,
                          coverage=coverage, cycle_count=cycle_count)

def _window(values: np.ndarray, fs: float,
            window: tuple[float, float] | None, timestamps_ms: np.ndarray | None = None) -> np.ndarray | None:
    if not window:
        return None
    start, end = window
    if timestamps_ms is not None:
        selected = values[(timestamps_ms >= start * 1000) & (timestamps_ms < end * 1000)]
        return selected if len(selected) >= 3 else None
    left, right = max(0, round(start * fs)), min(len(values), round(end * fs))
    return values[left:right] if right - left >= 3 else None


def _tidal_amplitude(values: np.ndarray, fs: float) -> float | None:
    prominence = max(float(np.std(values)) * 0.2, 1e-6)
    peaks, _ = find_peaks(values, distance=max(1, round(fs * 0.5)), prominence=prominence)
    troughs, _ = find_peaks(-values, distance=max(1, round(fs * 0.5)), prominence=prominence)
    extrema = sorted([(int(index), 1) for index in peaks] + [(int(index), -1) for index in troughs])
    amplitudes = [abs(float(values[b[0]] - values[a[0]]))
                  for a, b in zip(extrema, extrema[1:]) if a[1] != b[1]]
    if not amplitudes:
        return None
    ordered = np.sort(amplitudes)
    trim = int(len(ordered) * 0.1)
    kept = ordered[trim:len(ordered)-trim] if trim and len(ordered) > trim * 2 else ordered
    return float(np.mean(kept))


def _vital_amplitude(inhale: np.ndarray, exhale: np.ndarray, fs: float) -> float | None:
    """Measure the robust phase-constrained maximum inhale/exhale difference."""
    inhale_value = _supported_extreme(inhale, fs, "high")
    exhale_value = _supported_extreme(exhale, fs, "low")
    if inhale_value is None or exhale_value is None:
        return None
    return float(abs(inhale_value - exhale_value))


def supported_extremum(values: np.ndarray, fs: float, direction: str):
    signal = np.asarray(values, dtype=np.float64)
    support_radius = max(1, round(fs * 0.25))
    candidates = [i for i in range(len(signal)) if (min(len(signal)-1, i+support_radius)-max(0,i-support_radius))/fs >= .4]
    if not candidates:
        return None
    supported = np.array([np.median(signal[max(0, i-support_radius):min(len(signal), i+support_radius+1)]) for i in candidates])
    index = candidates[int(np.argmin(supported) if direction == "low" else np.argmax(supported))]
    left = max(0, index - support_radius)
    right = min(len(signal), index + support_radius + 1)
    return index, float(np.median(signal[left:right]))


def _supported_extreme(values: np.ndarray, fs: float, direction: str) -> float | None:
    result = supported_extremum(values, fs, direction)
    return result[1] if result else None


def _periodicity(peaks: np.ndarray, fs: float) -> float:
    if len(peaks) < 3:
        return 0.0
    periods = np.diff(peaks) / fs
    average = float(np.mean(periods))
    return float(np.clip(1.0 - np.std(periods) / average, 0, 1)) if average > 0 else 0.0

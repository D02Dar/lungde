from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..schemas import ComparisonDetails, RealtimeSample


@dataclass(frozen=True)
class _Series:
    timestamps_ms: np.ndarray
    values: np.ndarray


def fuse_signals(
    realtime_samples: list[RealtimeSample],
    offline_timestamps_ms: np.ndarray,
    offline_values: np.ndarray,
    phase_windows: dict[str, tuple[float, float]],
    *,
    realtime_quality: float,
    offline_quality: float,
    target_hz: float = 10.0,
    max_lag_ms: float = 1500.0,
) -> ComparisonDetails | None:
    realtime = _realtime_series(realtime_samples)
    offline = _ordered_series(offline_timestamps_ms, offline_values)
    if realtime is None or offline is None:
        return None
    start_ms = max(float(realtime.timestamps_ms[0]), float(offline.timestamps_ms[0]))
    end_ms = min(float(realtime.timestamps_ms[-1]), float(offline.timestamps_ms[-1]))
    if end_ms - start_ms < 3000.0:
        return None
    step_ms = 1000.0 / target_hz
    timeline = np.arange(start_ms, end_ms + step_ms * 0.25, step_ms, dtype=np.float64)
    realtime_values = _robust_normalize(np.interp(timeline, realtime.timestamps_ms, realtime.values))
    offline_values = _robust_normalize(np.interp(timeline, offline.timestamps_ms, offline.values))

    tidal = phase_windows.get("tidal")
    if tidal:
        mask = (timeline >= tidal[0] * 1000.0) & (timeline <= tidal[1] * 1000.0)
    else:
        mask = np.ones(len(timeline), dtype=bool)
    if int(np.sum(mask)) < max(20, round(target_hz * 3)):
        mask = np.ones(len(timeline), dtype=bool)

    lag_samples, sign, correlation = _alignment(
        realtime_values[mask], offline_values[mask], max_lag_samples=max(1, round(max_lag_ms / step_ms)),
    )
    aligned_offline = _shift(offline_values * sign, lag_samples)
    valid = np.isfinite(aligned_offline)
    warnings: list[str] = []
    realtime_weight = float(np.clip(realtime_quality, 0.05, 1.0))
    offline_weight = float(np.clip(offline_quality, 0.05, 1.0))
    if correlation < 0.35:
        warnings.append("Realtime and offline waveforms disagree; Primary uses the higher-quality source.")
        primary = realtime_values.copy() if realtime_weight >= offline_weight else np.where(valid, aligned_offline, offline_values)
        if realtime_weight >= offline_weight:
            realtime_weight, offline_weight = 1.0, 0.0
        else:
            realtime_weight, offline_weight = 0.0, 1.0
    else:
        total = realtime_weight + offline_weight
        realtime_weight /= total
        offline_weight /= total
        primary = realtime_values.copy()
        primary[valid] = realtime_weight * realtime_values[valid] + offline_weight * aligned_offline[valid]
        primary = _robust_normalize(primary)
    confidence = float(np.clip(correlation * (0.5 + 0.5 * max(realtime_quality, offline_quality)), 0.0, 1.0))
    # Do not serialize the shifted edges as zero-valued samples: those zeros
    # would look like real respiratory excursions in the frontend chart.
    valid_indices = np.flatnonzero(valid)
    if len(valid_indices) < 3:
        return None
    first, last = int(valid_indices[0]), int(valid_indices[-1]) + 1
    timeline = timeline[first:last]
    realtime_values = realtime_values[first:last]
    aligned_offline = aligned_offline[first:last]
    primary = primary[first:last]
    return ComparisonDetails(
        realtime_waveform=[float(value) for value in realtime_values],
        offline_waveform=[float(value) for value in aligned_offline],
        primary_waveform=[float(value) for value in primary],
        timestamps_ms=[float(value) for value in timeline],
        alignment_lag_ms=float(lag_samples * step_ms),
        alignment_sign=sign,
        correlation=correlation,
        realtime_weight=realtime_weight,
        offline_weight=offline_weight,
        confidence=confidence,
        warnings=warnings,
    )


def _realtime_series(samples: list[RealtimeSample]) -> _Series | None:
    usable = sorted(
        ((sample.elapsed_ms, sample.value) for sample in samples if np.isfinite(sample.elapsed_ms) and np.isfinite(sample.value)),
        key=lambda item: item[0],
    )
    if len(usable) < 3:
        return None
    timestamps, values = zip(*usable)
    return _ordered_series(np.asarray(timestamps, dtype=np.float64), np.asarray(values, dtype=np.float64))


def _ordered_series(timestamps_ms: np.ndarray, values: np.ndarray) -> _Series | None:
    timestamps = np.asarray(timestamps_ms, dtype=np.float64)
    signal = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(timestamps) & np.isfinite(signal)
    timestamps, signal = timestamps[valid], signal[valid]
    if len(timestamps) < 3:
        return None
    order = np.argsort(timestamps)
    timestamps, signal = timestamps[order], signal[order]
    unique, indices = np.unique(timestamps, return_index=True)
    if len(unique) < 3:
        return None
    return _Series(timestamps_ms=unique, values=signal[indices])


def _alignment(realtime: np.ndarray, offline: np.ndarray, *, max_lag_samples: int) -> tuple[int, int, float]:
    best_lag, best_sign, best_correlation = 0, 1, -1.0
    for sign in (1, -1):
        candidate = offline * sign
        for lag in range(-max_lag_samples, max_lag_samples + 1):
            if lag < 0:
                left, right = realtime[-lag:], candidate[:len(candidate) + lag]
            elif lag > 0:
                left, right = realtime[:-lag], candidate[lag:]
            else:
                left, right = realtime, candidate
            if len(left) < 10 or np.std(left) < 1e-9 or np.std(right) < 1e-9:
                continue
            correlation = float(np.corrcoef(left, right)[0, 1])
            if np.isfinite(correlation) and correlation > best_correlation:
                best_lag, best_sign, best_correlation = lag, sign, correlation
    return best_lag, best_sign, float(max(0.0, best_correlation))


def _shift(values: np.ndarray, lag: int) -> np.ndarray:
    output = np.full(len(values), np.nan, dtype=np.float64)
    if lag < 0:
        output[-lag:] = values[:len(values) + lag]
    elif lag > 0:
        output[:-lag] = values[lag:]
    else:
        output[:] = values
    return output


def _robust_normalize(values: np.ndarray) -> np.ndarray:
    centre = float(np.median(values))
    mad = float(np.median(np.abs(values - centre))) * 1.4826
    scale = mad if mad > 1e-9 else float(np.std(values))
    return (values - centre) / scale if scale > 1e-9 else np.zeros_like(values)

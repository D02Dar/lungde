from __future__ import annotations

import numpy as np

from ..schemas import CaptureMetadata, EvidenceRequest, RealtimeSample


def realtime_platform_requests(metadata: CaptureMetadata) -> list[EvidenceRequest]:
    requests: list[EvidenceRequest] = []
    for phase, key, label, direction in (
        ("maxInhale", "maxInhale", "Maximum inhale stable hold", "high"),
        ("maxExhale", "maxExhale", "Maximum exhale stable hold", "low"),
    ):
        samples = sorted(
            (sample for sample in metadata.realtime_samples if sample.phase == phase),
            key=lambda sample: sample.elapsed_ms,
        )
        selected = stable_hold(samples, direction)
        if selected is None:
            continue
        requests.append(EvidenceRequest(
            key=key,
            label=label,
            elapsed_ms=selected.elapsed_ms,
            phase=phase,
            area_px=selected.value,
            roi_kind="realtime",
        ))
    return requests


def analysis_evidence_requests(
    metadata: CaptureMetadata,
    offline_landmarks: dict[str, dict[str, float]],
) -> list[EvidenceRequest]:
    """Merge client requests with backend-selected Realtime and Offline evidence.

    Backend stable-hold requests replace same-key client extrema. Other client
    requests (for example bestSignal) are preserved.
    """
    merged = {request.key: request for request in metadata.evidence_requests}
    for request in realtime_platform_requests(metadata):
        merged[request.key] = request
    for phase, key, label in (
        ("maxInhale", "offlinePeak", "Supported inhale level"),
        ("maxExhale", "offlineTrough", "Supported exhale level"),
    ):
        point = offline_landmarks.get(phase)
        if not point or not np.isfinite(point.get("ms", np.nan)):
            continue
        level = point.get("level_px")
        merged[key] = EvidenceRequest(
            key=key,
            label=label,
            elapsed_ms=float(point["ms"]),
            phase=phase,
            area_px=float(level) if level is not None and np.isfinite(level) else None,
            roi_kind="offline",
        )
    return list(merged.values())


def stable_hold(samples: list[RealtimeSample], direction: str) -> RealtimeSample | None:
    if len(samples) < 3:
        return None
    latter = samples[max(0, len(samples) // 2):]
    values = np.asarray([sample.value for sample in latter], dtype=np.float64)
    cutoff = float(np.quantile(values, 0.65 if direction == "high" else 0.35))
    candidates = [
        index for index, value in enumerate(values)
        if (value >= cutoff if direction == "high" else value <= cutoff)
    ] or list(range(len(values)))
    scale = max(float(np.ptp(values)), 1e-9)
    best_index = min(candidates, key=lambda index: platform_score(values, index, scale))
    return latter[best_index]


def platform_score(values: np.ndarray, index: int, scale: float) -> float:
    left = max(0, index - 2)
    right = min(len(values), index + 3)
    window = values[left:right]
    local_variation = float(np.std(window)) / scale
    derivative = abs(float(values[min(index + 1, len(values) - 1)] - values[max(index - 1, 0)])) / scale
    return local_variation + derivative

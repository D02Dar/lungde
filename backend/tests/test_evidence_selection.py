from app.analysis.evidence_selection import analysis_evidence_requests, realtime_platform_requests
from app.schemas import CaptureMetadata, EvidenceRequest, NormalizedRoi, RealtimeSample


def _metadata(samples: list[RealtimeSample]) -> CaptureMetadata:
    roi = NormalizedRoi(x=0, y=0, width=1, height=1)
    return CaptureMetadata(
        roi=roi,
        operator_roi=roi,
        frame_width=100,
        frame_height=100,
        realtime_samples=samples,
    )


def test_platform_evidence_ignores_transient_extrema_and_uses_late_stable_hold():
    samples = []
    inhale = [10, 20, 35, 90, 44, 50, 51, 50.5, 50.8, 50.7]
    exhale = [50, 42, 32, -20, 22, 15, 14.8, 15.1, 15.0, 15.2]
    for index, value in enumerate(inhale):
        samples.append(RealtimeSample(elapsed_ms=1000 + index * 100, value=value, phase="maxInhale"))
    for index, value in enumerate(exhale):
        samples.append(RealtimeSample(elapsed_ms=3000 + index * 100, value=value, phase="maxExhale"))

    requests = {request.key: request for request in realtime_platform_requests(_metadata(samples))}
    assert set(requests) == {"maxInhale", "maxExhale"}
    assert requests["maxInhale"].elapsed_ms >= 1500
    assert requests["maxInhale"].area_px < 60, "the early inhale spike must not be selected"
    assert requests["maxExhale"].elapsed_ms >= 3500
    assert requests["maxExhale"].area_px > 0, "the early exhale spike must not be selected"
    assert abs(requests["maxInhale"].area_px - 50.7) < 1.0
    assert abs(requests["maxExhale"].area_px - 15.0) < 1.0


def test_platform_evidence_requires_enough_phase_samples():
    requests = realtime_platform_requests(_metadata([
        RealtimeSample(elapsed_ms=0, value=1, phase="maxInhale"),
        RealtimeSample(elapsed_ms=100, value=2, phase="maxInhale"),
    ]))
    assert requests == []


def test_analysis_requests_replace_transient_client_extrema_and_add_offline_landmarks():
    samples = [
        RealtimeSample(elapsed_ms=1000 + index * 100, value=value, phase="maxInhale")
        for index, value in enumerate([90, 40, 48, 50, 50.5, 50.2])
    ]
    metadata = _metadata(samples)
    metadata.evidence_requests = [
        EvidenceRequest(key="maxInhale", label="Client peak", elapsed_ms=1000, area_px=90),
        EvidenceRequest(key="bestSignal", label="Client quality frame", elapsed_ms=1200),
    ]
    requests = {request.key: request for request in analysis_evidence_requests(metadata, {
        "maxInhale": {"ms": 5000, "level_px": 700},
        "maxExhale": {"ms": 7000, "level_px": 200},
    })}
    assert requests["maxInhale"].label == "Maximum inhale stable hold"
    assert requests["maxInhale"].elapsed_ms >= 1300
    assert requests["bestSignal"].elapsed_ms == 1200
    assert requests["offlinePeak"].phase == "maxInhale"
    assert requests["offlinePeak"].area_px == 700
    assert requests["offlineTrough"].phase == "maxExhale"

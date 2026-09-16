"""Amplitude-preserving analysis shared by the API and notebook.

Quality thresholds are engineering checks, not calibrated probabilities.
Raw traces and provisional estimates are always retained for investigation.
"""
from dataclasses import asdict
import numpy as np
from scipy.signal import find_peaks
from .filtering import uniform_samples, clean_respiratory_signal
from .metrics import analyze_signal, _window, supported_extremum

VERSION = "phase-roi-amplitude-v5"


def review_signal(raw, timestamps_ms, fps, phase_windows, *, roi_pixels=None, valid_frame_ratio=1.0):
    raw = np.asarray(raw, dtype=float)
    source_times = np.asarray(timestamps_ms, dtype=float)
    resampled, times = uniform_samples(raw, source_times, fps)
    clean, _ = clean_respiratory_signal(resampled, times, fps)
    estimates = analyze_signal(clean, fps, phase_windows, times)
    tidal = _window(clean, fps, phase_windows.get("tidal"), times)
    vt_reasons, vc_reasons, vt_warnings, vc_warnings = [], [], [], []
    residual = np.abs(resampled-clean)
    noise = float(np.median(residual)) * 1.4826
    tidal_residual = _window(residual, fps, phase_windows.get('tidal'), times)
    vital_parts = [part for phase in ('maxInhale', 'maxExhale')
                   if (part := _window(residual, fps, phase_windows.get(phase), times)) is not None]
    vital_residual = np.concatenate(vital_parts) if vital_parts else np.array([])
    tidal_noise = float(np.median(tidal_residual))*1.4826 if tidal_residual is not None else noise
    vital_noise = float(np.median(vital_residual))*1.4826 if len(vital_residual) else noise
    amplitudes = []
    drift = None
    if tidal is not None:
        peaks, _ = find_peaks(tidal, distance=max(1, round(fps*.6)), prominence=max(tidal_noise*3, np.ptp(tidal)*.08, 1e-6))
        for left, right in zip(peaks[:-1], peaks[1:]):
            trough = left + int(np.argmin(tidal[left:right+1]))
            if left < trough < right:
                amplitudes.append(float((tidal[left]+tidal[right])/2-tidal[trough]))
        n = max(1, round(fps))
        drift = float(abs(np.median(tidal[-n:])-np.median(tidal[:n])))
    vt = float(np.median(amplitudes)) if amplitudes else None
    cv = float(np.std(amplitudes)/max(vt, 1e-9)) if amplitudes else None
    if len(amplitudes) < 2: vt_reasons.append("insufficient_complete_tidal_cycles")
    if cv is not None and cv > .5: vt_reasons.append("severely_inconsistent_tidal_amplitudes")
    elif cv is not None and cv > .3: vt_warnings.append("variable_tidal_amplitudes")
    if vt is None or vt <= max(tidal_noise*4, 1e-6): vt_reasons.append("tidal_below_noise")
    if vt and drift is not None and drift > vt*2: vt_warnings.append("tidal_baseline_drift")
    vc = estimates.vc_px
    landmarks = {}
    for phase, direction in (("maxInhale", "high"), ("maxExhale", "low")):
        window = phase_windows.get(phase)
        if not window: continue
        start, end = window
        if phase == "maxInhale": end = phase_windows.get("exhalePrep", window)[1]
        indices = np.flatnonzero((times >= start*1000)&(times < end*1000))
        result = supported_extremum(clean[indices], fps, direction)
        if result:
            index, level = result
            landmarks[phase] = {"ms": float(times[indices[index]]), "level_px": level}
    if len(landmarks) == 2 and landmarks["maxInhale"]["level_px"] <= landmarks["maxExhale"]["level_px"]:
        vc_reasons.append("reversed_vital_levels")
    if vc is None or vc <= max(vital_noise*6, 1e-6): vc_reasons.append("vital_below_noise")
    if vc is not None and vt and vc <= vt: vc_reasons.append("vital_not_greater_than_tidal")
    steps = np.diff(source_times)
    max_gap = float(np.max(steps)) if len(steps) else 0.0
    common = []
    if valid_frame_ratio < .9: common.append("insufficient_valid_frames")
    for phase in ("tidal", "maxInhale", "maxExhale"):
        window = phase_windows.get(phase)
        if not window:
            (vt_reasons if phase == "tidal" else vc_reasons).append("missing_"+phase)
            continue
        start, end = np.asarray(window)*1000
        phase_times = source_times[(source_times >= start)&(source_times < end)]
        phase_raw = raw[(source_times >= start)&(source_times < end)]
        if len(phase_raw)>1 and np.max(np.abs(np.diff(phase_raw))) > max(abs(np.median(phase_raw))*.16,1):
            (vt_reasons if phase == 'tidal' else vc_reasons).append('large_area_jump_'+phase)
        coverage = len(phase_times)/max(1, (end-start)*fps/1000)
        gaps = np.diff(np.r_[start, phase_times, end])
        if coverage < .85 or np.max(gaps) > 500:
            (vt_reasons if phase == "tidal" else vc_reasons).append("incomplete_"+phase)
    if roi_pixels and (np.min(raw) < 0 or np.max(raw) > roi_pixels): common.append("area_exceeds_roi")
    vt_reasons += common
    vc_reasons += common
    ratio = vc/vt if vt and vc is not None else None
    diagnostics = {**asdict(estimates), "vt_px": vt, "vc_px": vc, "ratio": ratio,
                   "noise_px": noise, "tidal_noise_px": tidal_noise, "vital_noise_px": vital_noise,
                   "tidal_cycles": len(amplitudes), "tidal_amplitudes": amplitudes,
                   "tidal_cv": cv, "tidal_drift_px": drift, "max_gap_ms": max_gap,
                   "landmarks": landmarks, "vt_reasons": sorted(set(vt_reasons)), "vc_reasons": sorted(set(vc_reasons)),
                   "vt_warnings": sorted(set(vt_warnings)), "vc_warnings": sorted(set(vc_warnings))}
    metrics = {**asdict(estimates), "vt_px": None if vt_reasons else vt,
               "vc_px": None if vc_reasons else vc, "ratio": None if vt_reasons or vc_reasons else ratio}
    if vt_reasons:
        metrics.update(rr_hz=None, rr_bpm=None)
    quality_status = "review_required" if vt_reasons or vc_reasons else "usable_with_caution" if vt_warnings or vc_warnings else "checks_passed"
    return {"metrics": metrics, "diagnostic": diagnostics, "raw": resampled,
            "waveform": clean, "timestamps_ms": times,
            "quality_status": quality_status}

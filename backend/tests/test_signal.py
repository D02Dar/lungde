import numpy as np
from app.analysis.filtering import butterworth_bandpass
from app.analysis.metrics import analyze_signal, stable_confidence_interval


def test_rate_and_vc_over_vt_ratio():
    fs = 30.0
    seconds = 30
    time = np.arange(int(fs * seconds)) / fs
    signal = np.sin(2 * np.pi * 0.25 * time)
    signal[(time >= 15) & (time < 20)] += 2.5
    signal[(time >= 20) & (time < 26)] -= 2.5
    filtered = butterworth_bandpass(signal, fs)
    metrics = analyze_signal(filtered, fs, {
        "tidal": (0, 12), "maxInhale": (15, 20), "maxExhale": (20, 26),
    })
    assert abs(metrics.rr_hz - 0.25) < 0.04
    assert metrics.vt_px and metrics.vt_px > 0
    assert metrics.vc_px and metrics.vc_px > metrics.vt_px
    assert abs(metrics.ratio - metrics.vc_px / metrics.vt_px) < 1e-9


def test_volume_proxies_require_phase_windows():
    fs = 30.0
    time = np.arange(600) / fs
    metrics = analyze_signal(np.sin(2 * np.pi * 0.2 * time), fs, {})
    assert metrics.rr_hz is not None
    assert metrics.vt_px is None
    assert metrics.vc_px is None
    assert metrics.ratio is None


def test_stable_confidence_interval_uses_complete_tidal_cycles():
    fs = 30.0
    time = np.arange(int(fs * 16)) / fs
    signal = np.sin(2 * np.pi * 0.25 * time)
    interval = stable_confidence_interval(signal, fs, {"tidal": (0, 12)})
    assert interval is not None
    assert interval.cycle_count >= 2
    assert 0 <= interval.start_index < interval.end_index < int(fs * 12)
    assert 0 < interval.coverage <= 1


def test_stable_confidence_interval_is_none_without_complete_cycles():
    fs = 30.0
    signal = np.linspace(0, 1, int(fs * 5))
    assert stable_confidence_interval(signal, fs, {"tidal": (0, 5)}) is None


def test_vc_uses_robust_phase_extrema_instead_of_phase_tail():
    fs = 20.0
    signal = np.zeros(int(fs * 24), dtype=np.float64)
    time = np.arange(len(signal)) / fs
    signal += 0.4 * np.sin(2 * np.pi * 0.25 * time)
    signal[(time >= 13) & (time < 15)] += 4.0
    signal[(time >= 15) & (time < 17)] += 1.0
    signal[(time >= 19) & (time < 21)] -= 3.5
    signal[(time >= 21) & (time < 23)] -= 0.5
    metrics = analyze_signal(signal, fs, {
        "tidal": (0, 10),
        "maxInhale": (12, 17),
        "maxExhale": (18, 23),
    })
    assert metrics.vc_px is not None
    assert metrics.vc_px > 6.5, "VC should use the strongest supported inhale/exhale contrast"


def test_rr_uses_tidal_window_not_maximum_manoeuvre_transients():
    fs = 20.0
    time = np.arange(int(fs * 30)) / fs
    signal = np.sin(2 * np.pi * 0.25 * time)
    signal[(time >= 15) & (time < 22)] += np.linspace(0, 20, np.count_nonzero((time >= 15) & (time < 22)))
    signal[(time >= 22)] -= np.linspace(0, 20, np.count_nonzero(time >= 22))
    metrics = analyze_signal(signal, fs, {
        "tidal": (0, 12),
        "maxInhale": (15, 22),
        "maxExhale": (22, 30),
    })
    assert metrics.rr_hz is not None
    assert abs(metrics.rr_hz - 0.25) < 0.04

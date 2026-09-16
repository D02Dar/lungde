import numpy as np

from app.analysis.peaks import smoothed_extremum_index


def test_smoothed_extremum_ignores_single_frame_spike():
    values = np.array([10, 20, 35, 90, 44, 50, 51, 50.5, 50.8, 50.7])
    index = smoothed_extremum_index(values, "high")
    assert index >= 5


def test_smoothed_extremum_follows_late_inhale_turning_point():
    values = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 8.5, 8.2, 7.0])
    index = smoothed_extremum_index(values, "high")
    assert index >= 8


def test_smoothed_extremum_finds_exhale_trough():
    values = np.array([8, 7, 6, 4, 2, 0, -1, -2, -2.2, -2.0, -1.5])
    index = smoothed_extremum_index(values, "low")
    assert index >= 7

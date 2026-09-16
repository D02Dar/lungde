import numpy as np
import pytest
from app.analysis.roi import ensure_inside, normalized_to_pixels
from app.schemas import CaptureMetadata, NormalizedRoi, PixelRoi, PositionQuality


def test_normalized_roi_maps_to_pixels():
    pixel = normalized_to_pixels(NormalizedRoi(x=0.25, y=0.1, width=0.5, height=0.8), 1000, 500)
    assert pixel == PixelRoi(x=250, y=50, width=500, height=400)


def test_analysis_roi_must_stay_inside_capture_box():
    outer = PixelRoi(x=100, y=50, width=500, height=400)
    ensure_inside(PixelRoi(x=150, y=80, width=100, height=60), outer)
    with pytest.raises(ValueError):
        ensure_inside(PixelRoi(x=50, y=80, width=100, height=60), outer)


def test_roi_profile_id_is_optional_and_round_trips():
    roi = NormalizedRoi(x=0.2, y=0.1, width=0.5, height=0.8)
    chest = NormalizedRoi(x=0.2, y=0.276, width=0.5, height=0.44)
    search = NormalizedRoi(x=0.365, y=0.18, width=0.17, height=0.144)
    metadata = CaptureMetadata(
        operator_roi=roi,
        realtime_chest_roi=chest,
        offline_search_roi=search,
        frame_width=1280,
        frame_height=720,
        roi_contract_version="went-roi-v2",
        roi_profile_id="standing-side-upper-body-v1",
        position_quality=PositionQuality(status="locked"),
    )
    assert metadata.roi_profile_id == "standing-side-upper-body-v1"
    assert metadata.model_dump()["roi_profile_id"] == "standing-side-upper-body-v1"

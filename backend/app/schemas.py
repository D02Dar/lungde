from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

## normalized coordinates are in [0,1] relative to the frame size
class NormalizedRoi(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def inside_frame(self):
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("ROI must stay inside the frame")
        return self

## evidence and analysis use pixel coordinates relative to the frame size
class EvidenceRequest(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=160)
    elapsed_ms: float = Field(ge=0)
    phase: str = Field(default="", max_length=64)
    area_px: float | None = None
    threshold: float | None = None
    roi_kind: Literal["operator", "realtime", "offline"] = "realtime"


class RealtimeSample(BaseModel):
    elapsed_ms: float = Field(ge=0)
    value: float
    quality: float | None = None
    phase: str = Field(default="", max_length=64)
    signal_method: str | None = Field(default=None, max_length=64)
    saturation_ratio: float | None = Field(default=None, ge=0, le=1)
    highlight_saturation_ratio: float | None = Field(default=None, ge=0, le=1)


class PositionQuality(BaseModel):
    status: Literal["locked", "legacy", "unknown"] = "unknown"
    occupancy: float | None = None
    variation: float | None = None
    contrast: float | None = None
    subject_polarity: Literal["dark", "light"] | None = None
    edge_clearance: dict[str, float] = Field(default_factory=dict)
    band_occupancy: dict[str, float] = Field(default_factory=dict)
    calibration_ratio: float | None = None
    calibration_samples: int | None = None


class CaptureMetadata(BaseModel):
    roi: NormalizedRoi | None = None
    operator_roi: NormalizedRoi | None = None
    realtime_chest_roi: NormalizedRoi | None = None
    offline_search_roi: NormalizedRoi | None = None
    frame_width: int = Field(gt=0)
    frame_height: int = Field(gt=0)
    mirrored: bool = False
    phase_windows: dict[str, tuple[float, float]] = Field(default_factory=dict)
    roi_contract_version: str = "legacy-v1"
    roi_profile_id: str | None = Field(default=None, max_length=80)
    position_quality: PositionQuality = Field(default_factory=PositionQuality)
    calibration: dict[str, Any] = Field(default_factory=dict)
    camera_settings: dict[str, Any] = Field(default_factory=dict)
    realtime_samples: list[RealtimeSample] = Field(default_factory=list)
    evidence_requests: list[EvidenceRequest] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalise_contract(self):
        if self.operator_roi is None:
            self.operator_roi = self.roi
        if self.roi is None:
            self.roi = self.operator_roi
        if self.operator_roi is None:
            raise ValueError("operator_roi is required")
        if self.roi_contract_version == "went-roi-v2":
            if self.realtime_chest_roi is None or self.offline_search_roi is None:
                raise ValueError("went-roi-v2 requires realtime_chest_roi and offline_search_roi")
        return self


class PixelRoi(BaseModel):
    x: int
    y: int
    width: int
    height: int


class EvidenceFrame(BaseModel):
    id: str
    key: str
    label: str
    elapsed_ms: float
    actual_elapsed_ms: float | None = None
    timestamp_error_ms: float | None = None
    phase: str = ""
    area_px: float | None = None
    threshold: float | None = None
    roi_kind: Literal["operator", "realtime", "offline"]
    roi: PixelRoi | None = None
    frame_width: int
    frame_height: int
    image_url: str


class QualityDetails(BaseModel):
    status: str | None = None
    diagnostic: dict[str, Any] = Field(default_factory=dict)
    snr: float
    periodicity: float
    roi_confidence: float | None
    valid_frame_ratio: float
    selected_row_fraction: float
    texture_coverage: float | None = None
    temporal_coherence: float | None = None
    saturation_ratio: float | None = None
    noise_estimate: float | None = None
    volume_signal_score: float | None = None
    volume_metrics_valid: bool | None = None
    warnings: list[str]


class ConfidenceInterval(BaseModel):
    start_index: int
    end_index: int
    start_ms: float
    end_ms: float
    coverage: float
    cycle_count: int
    method: Literal["stable_tidal_cycles"] = "stable_tidal_cycles"


class ComparisonDetails(BaseModel):
    """Normalized waveform agreement for review; never used as formal Vc/Vt."""

    realtime_waveform: list[float]
    offline_waveform: list[float]
    primary_waveform: list[float]
    timestamps_ms: list[float]
    alignment_lag_ms: float
    alignment_sign: Literal[-1, 1]
    correlation: float = Field(ge=0, le=1)
    realtime_weight: float = Field(ge=0, le=1)
    offline_weight: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class ComparisonExportRequest(BaseModel):
    analysis_ids: list[str] = Field(min_length=2, max_length=8)

    @model_validator(mode="after")
    def unique_analysis_ids(self):
        if len(set(self.analysis_ids)) != len(self.analysis_ids):
            raise ValueError("analysis_ids must be unique")
        return self



class AnalysisResponse(BaseModel):
    status: Literal["complete"] = "complete"
    analysis_id: str | None = None
    rr_hz: float | None
    rr_bpm: float | None
    vt_px: float | None
    vc_px: float | None
    ratio: float | None
    waveform: list[float]
    timestamps_ms: list[float]
    confidence: float | None
    diagnostic: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    raw_waveform: list[float] = Field(default_factory=list)
    raw_timestamps_ms: list[float] = Field(default_factory=list)
    source_waveform: list[float] = Field(default_factory=list)
    confidence_interval: ConfidenceInterval | None = None
    roi: PixelRoi
    roi_source: Literal["locked_contract", "legacy_auto"]
    selected_rows: list[int]
    quality: QualityDetails
    comparison: ComparisonDetails | None = None
    evidence: list[EvidenceFrame] = Field(default_factory=list)
    algorithm_version: str = "offline-texture-motion-v3"

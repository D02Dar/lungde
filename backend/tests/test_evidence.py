from pathlib import Path

import cv2
import numpy as np

from app.analysis.evidence import _nearest_frames, extract_evidence
from app.analysis.video import read_video
from app.schemas import CaptureMetadata, EvidenceRequest, NormalizedRoi, PixelRoi
from app.storage import AnalysisStore


def _write_index_video(path: Path, fps: float = 10.0, count: int = 40) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (32, 24))
    assert writer.isOpened()
    for index in range(count):
        writer.write(np.full((24, 32, 3), index, dtype=np.uint8))
    writer.release()


def _metadata() -> CaptureMetadata:
    roi = NormalizedRoi(x=0, y=0, width=1, height=1)
    return CaptureMetadata(
        roi=roi,
        operator_roi=roi,
        frame_width=32,
        frame_height=24,
    )


def test_nearest_frame_uses_decoded_timestamp(tmp_path: Path):
    path = tmp_path / "frames.avi"
    _write_index_video(path)
    video = read_video(path, declared_duration_ms=4000)
    try:
        request = EvidenceRequest(key="near", label="Nearest", elapsed_ms=1260, roi_kind="operator")
        selected = _nearest_frames(video, [request])["near"]
        assert abs(selected.timestamp_ms - 1260) <= 60
    finally:
        video.close()


def test_failed_image_encode_is_logged_and_not_persisted(tmp_path: Path, monkeypatch, caplog):
    path = tmp_path / "frames.avi"
    _write_index_video(path)
    video = read_video(path, declared_duration_ms=4000)
    store = AnalysisStore(tmp_path / "data")
    analysis_id, video_path = store.allocate_video(".avi")
    video_path.write_bytes(path.read_bytes())
    store.create(
        analysis_id=analysis_id,
        frontend_record_id=None,
        filename="frames.avi",
        mime_type="video/avi",
        byte_size=video_path.stat().st_size,
        declared_duration_ms=4000,
        video_path=video_path,
        capture_metadata=_metadata().model_dump(),
    )
    monkeypatch.setattr(cv2, "imencode", lambda *_args, **_kwargs: (False, None))
    try:
        result = extract_evidence(
            store,
            analysis_id,
            video,
            _metadata(),
            [EvidenceRequest(key="failed", label="Failed", elapsed_ms=1000, roi_kind="operator")],
            PixelRoi(x=0, y=0, width=16, height=12),
        )
        assert result == []
        assert store.list_evidence(analysis_id) == []
        assert "Failed to write evidence frame" in caplog.text
    finally:
        video.close()


def test_evidence_persists_under_unicode_storage_path(tmp_path: Path):
    path = tmp_path / "frames.avi"
    _write_index_video(path)
    video = read_video(path, declared_duration_ms=4000)
    unicode_root = "resume\u548c\u5b9e\u4e60" + "/" + "\u65e5\u672c\u4fe1\u5dde"
    store = AnalysisStore(tmp_path / unicode_root / "data")
    analysis_id, video_path = store.allocate_video(".avi")
    video_path.write_bytes(path.read_bytes())
    store.create(
        analysis_id=analysis_id,
        frontend_record_id=None,
        filename="frames.avi",
        mime_type="video/avi",
        byte_size=video_path.stat().st_size,
        declared_duration_ms=4000,
        video_path=video_path,
        capture_metadata=_metadata().model_dump(),
    )
    try:
        result = extract_evidence(
            store,
            analysis_id,
            video,
            _metadata(),
            [EvidenceRequest(key="unicode", label="Unicode", elapsed_ms=1000, roi_kind="operator")],
            PixelRoi(x=0, y=0, width=16, height=12),
        )
        assert [item.key for item in result] == ["unicode"]
        saved = store.list_evidence(analysis_id)
        assert [item["key"] for item in saved] == ["unicode"]
        assert store.evidence_path(saved[0]).read_bytes()
    finally:
        video.close()

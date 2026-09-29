from pathlib import Path
from threading import Event, Thread
import time

from app.storage import AnalysisStore


def test_store_persists_and_deletes_video(tmp_path: Path):
    store = AnalysisStore(tmp_path / "data")
    analysis_id, video_path = store.allocate_video(".webm")
    video_path.write_bytes(b"browser-video")
    created = store.create(
        analysis_id=analysis_id,
        frontend_record_id="local-record-1",
        filename="capture.webm",
        mime_type="video/webm;codecs=vp8",
        byte_size=video_path.stat().st_size,
        declared_duration_ms=37000,
        video_path=video_path,
        capture_metadata={"roi": {"x": .2, "y": .1, "width": .5, "height": .7}},
    )
    assert created["status"] == "uploaded"
    assert created["frontend_record_id"] == "local-record-1"
    assert created["declared_duration_ms"] == 37000
    assert store.video_path(created).exists()

    updated = store.update(
        analysis_id,
        status="failed",
        diagnostics_json='{"decoded_frame_count": 4}',
        error_code="video_decode_incomplete",
        error_message="not enough frames",
    )
    assert updated["diagnostics"]["decoded_frame_count"] == 4
    assert updated["error_code"] == "video_decode_incomplete"

    evidence_id, evidence_path = store.allocate_evidence(analysis_id, "maxInhale")
    evidence_path.write_bytes(b"webp-frame")
    saved_evidence = store.add_evidence(analysis_id, {
        "id": evidence_id,
        "key": "maxInhale",
        "label": "Maximum inhale stable hold",
        "elapsed_ms": 4200.0,
        "phase": "maxInhale",
        "area_px": 1200,
        "threshold": 88,
        "roi_kind": "realtime",
        "roi": {"x": 10, "y": 20, "width": 30, "height": 40},
        "frame_width": 1280,
        "frame_height": 720,
        "image_url": f"/api/analyses/{analysis_id}/evidence/{evidence_id}",
    }, evidence_path)
    assert saved_evidence["key"] == "maxInhale"
    assert store.evidence_path(saved_evidence).read_bytes() == b"webp-frame"
    assert len(store.list_evidence(analysis_id)) == 1

    assert store.delete(analysis_id) is True
    assert store.get(analysis_id) is None
    assert not video_path.exists()
    assert not evidence_path.exists()
    assert store.list_evidence(analysis_id) == []


def test_analysis_lock_serializes_same_record_without_blocking_other_records(tmp_path: Path):
    store = AnalysisStore(tmp_path / "data")
    first_entered = Event()
    release_first = Event()
    same_entered = Event()
    other_entered = Event()

    def first():
        with store.analysis_lock("same"):
            first_entered.set()
            release_first.wait(2)

    def same():
        first_entered.wait(2)
        with store.analysis_lock("same"):
            same_entered.set()

    def other():
        first_entered.wait(2)
        with store.analysis_lock("other"):
            other_entered.set()

    threads = [Thread(target=first), Thread(target=same), Thread(target=other)]
    for thread in threads:
        thread.start()
    assert first_entered.wait(1)
    assert other_entered.wait(1), "an unrelated analysis should not wait on the same lock"
    time.sleep(0.05)
    assert not same_entered.is_set(), "the same analysis must remain serialized"
    release_first.set()
    assert same_entered.wait(1)
    for thread in threads:
        thread.join(1)

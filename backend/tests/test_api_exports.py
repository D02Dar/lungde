import io
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.main import app
from app.api import analyze


def stored(analysis_id):
    return {
        "id": analysis_id,
        "status": "complete",
        "capture_metadata": {"phase_windows": {"tidal": [0, 1]}},
        "result": {
            "vc_px": 400,
            "vt_px": 100,
            "ratio": 4,
            "waveform": [1, 2, 1],
            "timestamps_ms": [0, 100, 200],
            "source_waveform": [1, 2, 1],
            "raw_timestamps_ms": [0, 100, 200],
            "diagnostic": {},
            "quality": {"status": "checks_passed", "warnings": []},
        },
    }


def test_single_backend_export_is_available_from_api(monkeypatch):
    monkeypatch.setattr(analyze.analysis_store, "get", lambda analysis_id: stored(analysis_id))
    response = TestClient(app).get("/api/analyses/run-one/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "went-run-one-analysis.zip" in response.headers["content-disposition"]
    with ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {"analysis.csv", "analysis.json", "waveform.svg", "README.txt"}


def test_multi_run_backend_export_validates_and_combines_ids(monkeypatch):
    monkeypatch.setattr(analyze.analysis_store, "get", lambda analysis_id: stored(analysis_id))
    client = TestClient(app)
    response = client.post("/api/exports/comparison", json={"analysis_ids": ["run-one", "run-two"]})
    assert response.status_code == 200
    with ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {"comparison.csv", "comparison.json", "comparison.svg", "README.txt"}
    duplicate = client.post("/api/exports/comparison", json={"analysis_ids": ["run-one", "run-one"]})
    assert duplicate.status_code == 422

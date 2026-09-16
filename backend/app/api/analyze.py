from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import ValidationError

from ..analysis.evidence import extract_evidence
from ..analysis.evidence_selection import analysis_evidence_requests
from ..analysis.export import export_comparison_zip, export_zip
from ..analysis.review import VERSION
from ..analysis.pipeline import review_capture, review_comparison
from types import SimpleNamespace
from ..analysis.video import VideoDecodeError, read_video
from ..schemas import (
    AnalysisResponse, CaptureMetadata, ComparisonExportRequest, QualityDetails,
)
from ..storage import analysis_store

router = APIRouter()


def max_video_bytes(value: str | None = None) -> int:
    """Keep a safe default while permitting a school gateway to set its own limit."""
    configured = os.environ.get("WENT_MAX_VIDEO_MB", "250") if value is None else value
    try:
        megabytes = int(configured)
    except (TypeError, ValueError):
        megabytes = 250
    return max(1, min(megabytes, 1024)) * 1024 * 1024


MAX_VIDEO_BYTES = max_video_bytes()


def _parse_metadata(capture_roi: str) -> CaptureMetadata:
    try:
        return CaptureMetadata.model_validate_json(capture_roi)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_metadata", "message": str(exc)}) from exc


def _stored_view(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "analysis_id": record["id"],
        "frontend_record_id": record.get("frontend_record_id"),
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "status": record["status"],
        "original_filename": record.get("original_filename"),
        "mime_type": record.get("mime_type"),
        "byte_size": record.get("byte_size", 0),
        "declared_duration_ms": record.get("declared_duration_ms"),
        "capture_metadata": record.get("capture_metadata"),
        "diagnostics": record.get("diagnostics"),
        "result": record.get("result"),
        "evidence": analysis_store.list_evidence(record["id"]),
        "error": ({"code": record.get("error_code"), "message": record.get("error_message")}
                  if record.get("error_code") or record.get("error_message") else None),
    }


def _analyze_saved(
    analysis_id: str,
    video_path: Path,
    metadata: CaptureMetadata,
    declared_duration_ms: float | None,
) -> AnalysisResponse:
    with analysis_store.analysis_lock(analysis_id):
        return _analyze_saved_locked(analysis_id, video_path, metadata, declared_duration_ms)


def _analyze_saved_locked(
    analysis_id: str,
    video_path: Path,
    metadata: CaptureMetadata,
    declared_duration_ms: float | None,
) -> AnalysisResponse:
    analysis_store.update(analysis_id, status="processing", error_code=None, error_message=None)
    analysis_store.clear_evidence(analysis_id)
    source = read_video(video_path, declared_duration_ms=declared_duration_ms)
    try:
        analysis_store.update(analysis_id, diagnostics_json=json.dumps(source.diagnostics))

        roi, roi_source, warnings, extracted, review = review_capture(source, metadata)
        comparison = review_comparison(metadata, extracted, review)
        metrics = SimpleNamespace(**review["metrics"])
        display, times = review["waveform"], review["timestamps_ms"]
        reasons = review["diagnostic"]["vt_reasons"] + review["diagnostic"]["vc_reasons"]
        cautions = review["diagnostic"]["vt_warnings"] + review["diagnostic"]["vc_warnings"]
        warnings.extend(sorted(set(reasons + cautions)))
        if comparison:
            warnings.extend(comparison.warnings)
        if source.width < metadata.frame_width or source.height < metadata.frame_height:
            warnings.append("Decoded dimensions are smaller than capture dimensions; inspect camera and recording settings.")
        if min(source.width, source.height) < 720:
            warnings.append("Source is below 720p. A small chest edge may be poorly resolved.")
        if source.fps < 10:
            warnings.append("Low effective frame rate. Close other apps and improve lighting.")
        volume_metrics_valid = review["quality_status"] != "review_required"
        confidence = None  # Quality checks are not a calibrated probability.
        volume_signal_score = None
        quality = QualityDetails(
            snr=metrics.snr,
            periodicity=metrics.periodicity,
            roi_confidence=None,
            valid_frame_ratio=extracted.valid_frame_ratio,
            selected_row_fraction=len(extracted.selected_rows) / max(1, roi.height),
            texture_coverage=extracted.texture_coverage,
            temporal_coherence=extracted.temporal_coherence,
            saturation_ratio=extracted.saturation_ratio,
            noise_estimate=review["diagnostic"]["noise_px"],
            status=review["quality_status"],
            diagnostic=review["diagnostic"],
            volume_signal_score=volume_signal_score,
            volume_metrics_valid=volume_metrics_valid,
            warnings=warnings,
        )
        requests = analysis_evidence_requests(metadata, review["diagnostic"]["landmarks"])
        evidence = extract_evidence(analysis_store, analysis_id, source, metadata, requests, extracted.analysis_roi)
        response = AnalysisResponse(
            analysis_id=analysis_id,
            rr_hz=metrics.rr_hz,
            rr_bpm=metrics.rr_bpm,
            vt_px=metrics.vt_px,
            vc_px=metrics.vc_px,
            ratio=metrics.ratio,
            waveform=[float(value) for value in display],
            timestamps_ms=[float(value) for value in times],
            raw_waveform=review["raw"].tolist(),
            raw_timestamps_ms=extracted.timestamps_ms.tolist(),
            source_waveform=extracted.raw.tolist(),
            diagnostic=review["diagnostic"],
            diagnostics={**source.diagnostics, "capture_width": metadata.frame_width, "capture_height": metadata.frame_height,
                         "search_roi": roi.model_dump(), "analysis_roi": extracted.analysis_roi.model_dump(),
                         "roi_width": extracted.analysis_roi.width, "roi_height": extracted.analysis_roi.height, "reference_threshold": extracted.reference_threshold,
                         "subject_polarity": "dark" if extracted.dark_subject else "light", "signal_method": extracted.signal_method,
                         "highlight_saturation_ratio": extracted.highlight_saturation_ratio},
            confidence=confidence,
            confidence_interval=None,
            roi=extracted.analysis_roi,
            roi_source=roi_source,
            selected_rows=[int(value) for value in extracted.selected_rows],
            quality=quality,
            comparison=comparison,
            evidence=evidence,
            algorithm_version=VERSION,
        )
        analysis_store.update(analysis_id, status="complete", result_json=json.dumps(response.model_dump()))
        return response
    finally:
        source.close()


def _raise_analysis_error(analysis_id: str, exc: Exception) -> None:
    if isinstance(exc, VideoDecodeError):
        code = exc.code
        diagnostics = exc.diagnostics
    elif "Position quality" in str(exc) or "ROI" in str(exc):
        code = "position_invalid"
        diagnostics = None
    else:
        code = "analysis_invalid"
        diagnostics = None
    analysis_store.update(
        analysis_id,
        status="failed",
        diagnostics_json=json.dumps(diagnostics) if diagnostics else None,
        error_code=code,
        error_message=str(exc),
    )
    detail: dict[str, Any] = {"code": code, "message": str(exc), "analysis_id": analysis_id}
    if diagnostics:
        detail["diagnostics"] = diagnostics
    raise HTTPException(status_code=422, detail=detail) from exc


def _raise_unexpected_error(analysis_id: str, exc: Exception) -> None:
    analysis_store.update(analysis_id, status="failed", error_code="analysis_failed", error_message="offline analysis failed")
    raise HTTPException(
        status_code=500,
        detail={"code": "analysis_failed", "message": "offline analysis failed", "analysis_id": analysis_id},
    ) from exc


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_video(
    video: UploadFile = File(...),
    capture_roi: str = Form(...),
    frontend_record_id: str | None = Form(default=None),
    declared_duration_ms: float | None = Form(default=None),
):
    metadata = _parse_metadata(capture_roi)
    suffix = Path(video.filename or "capture.webm").suffix or ".webm"
    analysis_id, video_path = analysis_store.allocate_video(suffix)
    total = 0
    try:
        with video_path.open("wb") as handle:
            while chunk := await video.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_VIDEO_BYTES:
                    raise HTTPException(status_code=413, detail={"code": "video_too_large", "message": "Video exceeds 250 MB"})
                handle.write(chunk)
        if total == 0:
            raise HTTPException(status_code=422, detail={"code": "video_empty", "message": "The uploaded video is empty"})
        analysis_store.create(
            analysis_id=analysis_id,
            frontend_record_id=frontend_record_id,
            filename=video.filename or f"capture{suffix}",
            mime_type=video.content_type or "application/octet-stream",
            byte_size=total,
            declared_duration_ms=declared_duration_ms,
            video_path=video_path,
            capture_metadata=metadata.model_dump(),
        )
        try:
            return _analyze_saved(analysis_id, video_path, metadata, declared_duration_ms)
        except ValueError as exc:
            _raise_analysis_error(analysis_id, exc)
        except Exception as exc:
            _raise_unexpected_error(analysis_id, exc)
    except HTTPException:
        if not analysis_store.get(analysis_id):
            video_path.unlink(missing_ok=True)
        raise


@router.post("/analyses/{analysis_id}/reanalyze", response_model=AnalysisResponse)
def reanalyze_video(analysis_id: str):
    record = analysis_store.get(analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "analysis_not_found", "message": "Analysis record was not found"})
    try:
        metadata = CaptureMetadata.model_validate(record["capture_metadata"])
        return _analyze_saved(analysis_id, analysis_store.video_path(record), metadata, record.get("declared_duration_ms"))
    except ValueError as exc:
        _raise_analysis_error(analysis_id, exc)
    except Exception as exc:
        _raise_unexpected_error(analysis_id, exc)


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    record = analysis_store.get(analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "analysis_not_found", "message": "Analysis record was not found"})
    return JSONResponse(_stored_view(record))


def _portable_result(record: dict[str, Any]) -> dict[str, Any]:
    result = dict(record.get("result") or {})
    result["analysis_id"] = record["id"]
    result["capture_metadata"] = record.get("capture_metadata") or {}
    return result


@router.get("/analyses/{analysis_id}/export")
def export_analysis(analysis_id: str):
    record = analysis_store.get(analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "analysis_not_found", "message": "Analysis record was not found"})
    if record.get("status") != "complete" or not record.get("result"):
        raise HTTPException(status_code=409, detail={"code": "analysis_not_complete", "message": "Analysis is not complete"})
    return Response(
        export_zip(_portable_result(record)),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="went-{analysis_id}-analysis.zip"'},
    )


@router.post("/exports/comparison")
def export_comparison(request: ComparisonExportRequest):
    records = []
    for analysis_id in request.analysis_ids:
        record = analysis_store.get(analysis_id)
        if not record:
            raise HTTPException(status_code=404, detail={"code": "analysis_not_found", "message": f"Analysis {analysis_id} was not found"})
        if record.get("status") != "complete" or not record.get("result"):
            raise HTTPException(status_code=409, detail={"code": "analysis_not_complete", "message": f"Analysis {analysis_id} is not complete"})
        records.append(_portable_result(record))
    return Response(
        export_comparison_zip(records),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="went-comparison-{len(records)}-runs.zip"'},
    )


@router.get("/analyses/{analysis_id}/video")
def get_analysis_video(analysis_id: str):
    record = analysis_store.get(analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "analysis_not_found", "message": "Analysis record was not found"})
    path = analysis_store.video_path(record)
    if not path.exists():
        raise HTTPException(status_code=404, detail={"code": "video_not_found", "message": "Stored video was not found"})
    return FileResponse(path, media_type=record.get("mime_type") or "application/octet-stream", filename=record.get("original_filename") or path.name)


@router.get("/analyses/{analysis_id}/evidence/{evidence_id}")
def get_evidence_image(analysis_id: str, evidence_id: str):
    item = analysis_store.get_evidence(analysis_id, evidence_id)
    if not item:
        raise HTTPException(status_code=404, detail={"code": "evidence_not_found", "message": "Evidence frame was not found"})
    path = analysis_store.evidence_path(item)
    if not path.exists():
        raise HTTPException(status_code=404, detail={"code": "evidence_file_not_found", "message": "Evidence image file was not found"})
    return FileResponse(path, media_type="image/webp")


@router.delete("/analyses/{analysis_id}")
def delete_analysis(analysis_id: str):
    with analysis_store.analysis_lock(analysis_id):
        if not analysis_store.delete(analysis_id):
            raise HTTPException(status_code=404, detail={"code": "analysis_not_found", "message": "Analysis record was not found"})
    return {"deleted": True, "analysis_id": analysis_id}

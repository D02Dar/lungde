from __future__ import annotations

import logging
import os
from pathlib import Path

import cv2

from .roi import clip_pixel_roi, normalized_to_pixels
from .video import DecodedFrame, VideoData
from ..schemas import CaptureMetadata, EvidenceFrame, EvidenceRequest, PixelRoi
from ..storage import AnalysisStore

logger = logging.getLogger(__name__)


def extract_evidence(
    store: AnalysisStore,
    analysis_id: str,
    video: VideoData,
    metadata: CaptureMetadata,
    requests: list[EvidenceRequest],
    offline_roi: PixelRoi,
) -> list[EvidenceFrame]:
    if not requests:
        return []
    selected = _nearest_frames(video, requests)
    output: list[EvidenceFrame] = []
    for request in requests:
        decoded = selected.get(request.key)
        if decoded is None:
            logger.error("No decodable evidence frame for %s at %.1f ms", request.key, request.elapsed_ms)
            continue
        frame = decoded.frame
        height, width = frame.shape[:2]
        evidence_id, path = store.allocate_evidence(analysis_id, request.key, ".webp")
        temporary = path.with_suffix(path.suffix + ".tmp.webp")
        try:
            if not cv2.imwrite(str(temporary), frame, [cv2.IMWRITE_WEBP_QUALITY, 95]):
                logger.error("Failed to write evidence frame to %s", temporary)
                continue
            os.replace(temporary, path)
            roi = evidence_roi(request.roi_kind, metadata, offline_roi, width, height)
            item = EvidenceFrame(
                id=evidence_id,
                key=request.key,
                label=request.label,
                elapsed_ms=request.elapsed_ms,
                actual_elapsed_ms=decoded.timestamp_ms,
                timestamp_error_ms=decoded.timestamp_ms - request.elapsed_ms,
                phase=request.phase,
                area_px=request.area_px,
                threshold=request.threshold,
                roi_kind=request.roi_kind,
                roi=roi,
                frame_width=width,
                frame_height=height,
                image_url=f"/api/analyses/{analysis_id}/evidence/{evidence_id}",
            )
            try:
                store.add_evidence(analysis_id, item.model_dump(), path)
            except Exception:
                path.unlink(missing_ok=True)
                raise
            output.append(item)
        except Exception:
            logger.exception("Failed to persist evidence %s for analysis %s", request.key, analysis_id)
        finally:
            temporary.unlink(missing_ok=True)
    return output


def _nearest_frames(video: VideoData, requests: list[EvidenceRequest]) -> dict[str, DecodedFrame]:
    targets = sorted(requests, key=lambda item: item.elapsed_ms)
    selected: dict[str, DecodedFrame] = {}
    best_errors = {item.key: float("inf") for item in targets}
    pending = set(best_errors)
    max_target_ms = max(item.elapsed_ms for item in targets)
    margin_ms = max(250.0, 2000.0 / video.fps)
    for decoded in video.iter_frames():
        for request in targets:
            if request.key not in pending:
                continue
            error = abs(decoded.timestamp_ms - request.elapsed_ms)
            if error < best_errors[request.key]:
                selected[request.key] = DecodedFrame(frame=decoded.frame.copy(), index=decoded.index, timestamp_ms=decoded.timestamp_ms)
                best_errors[request.key] = error
            elif decoded.timestamp_ms > request.elapsed_ms and request.key in selected:
                pending.discard(request.key)
        if not pending and decoded.timestamp_ms > max_target_ms + margin_ms:
            break
    return selected


def evidence_roi(kind: str, metadata: CaptureMetadata, offline_roi: PixelRoi, width: int, height: int) -> PixelRoi | None:
    if kind == "offline":
        return clip_pixel_roi(offline_roi, width, height)
    if kind == "operator" and metadata.operator_roi:
        return normalized_to_pixels(metadata.operator_roi, width, height)
    if kind == "realtime" and metadata.realtime_chest_roi:
        return normalized_to_pixels(metadata.realtime_chest_roi, width, height)
    if metadata.operator_roi:
        return normalized_to_pixels(metadata.operator_roi, width, height)
    return None

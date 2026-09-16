from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Iterator

import cv2
import numpy as np

MINIMUM_SECONDS = 3.0
MINIMUM_FRAMES = 12
MINIMUM_REASONABLE_FPS = 5.0
DEFAULT_FPS = 30.0
MAX_REASONABLE_FPS = 120.0

##decoder the video
class VideoDecodeError(ValueError):
    def __init__(self, message: str, *, code: str = "video_decode_incomplete", diagnostics: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.diagnostics = diagnostics or {}


@dataclass(frozen=True)
class DecodedFrame:
    frame: np.ndarray
    index: int
    timestamp_ms: float


@dataclass
class VideoData:
    path: Path
    fps: float
    width: int
    height: int
    frame_count: int
    duration_seconds: float
    diagnostics: dict[str, Any] = field(default_factory=dict)
    cleanup_dir: Path | None = None
    max_frames: int = 10800
    max_seconds: float = 180.0

    def iter_frames(self) -> Iterator[DecodedFrame]:
        capture = cv2.VideoCapture(str(self.path))
        if not capture.isOpened():
            raise VideoDecodeError("Video could not be reopened for analysis", diagnostics=self.diagnostics)
        previous_ms = -1.0
        fallback_step_ms = 1000.0 / self.fps
        try:
            for index in range(self.max_frames):
                ok, frame = capture.read()
                if not ok:
                    break
                timestamp_ms = float(capture.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
                fallback_ms = index * fallback_step_ms
                if not np.isfinite(timestamp_ms) or timestamp_ms < 0 or (index and timestamp_ms <= previous_ms):
                    timestamp_ms = fallback_ms
                if timestamp_ms / 1000.0 > self.max_seconds:
                    break
                previous_ms = timestamp_ms
                yield DecodedFrame(frame=frame, index=index, timestamp_ms=timestamp_ms)
        finally:
            capture.release()

    def close(self) -> None:
        if self.cleanup_dir:
            shutil.rmtree(self.cleanup_dir, ignore_errors=True)
            self.cleanup_dir = None

    def __enter__(self) -> VideoData:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


@dataclass(frozen=True)
class _Probe:
    fps: float
    width: int
    height: int
    frame_count: int
    duration_seconds: float
    diagnostics: dict[str, Any]


def _normalise_fps(value: float, declared_duration_seconds: float | None, frame_count: int) -> tuple[float, str]:
    if declared_duration_seconds and declared_duration_seconds >= MINIMUM_SECONDS and frame_count >= MINIMUM_FRAMES:
        estimated = frame_count / declared_duration_seconds
        if MINIMUM_REASONABLE_FPS <= estimated <= MAX_REASONABLE_FPS:
            if not np.isfinite(value) or value < 1.0 or value > MAX_REASONABLE_FPS or abs(value - estimated) / estimated > 0.5:
                return estimated, "declared_duration"
    if np.isfinite(value) and 1.0 <= value <= MAX_REASONABLE_FPS:
        return value, "container"
    return DEFAULT_FPS, "fallback"


def _probe(path: Path, *, max_frames: int, max_seconds: float, declared_duration_seconds: float | None) -> _Probe:
    capture = cv2.VideoCapture(str(path))
    backend = capture.getBackendName() if capture.isOpened() else "unavailable"
    if not capture.isOpened():
        raise VideoDecodeError(
            "Video could not be decoded",
            diagnostics={"path_suffix": path.suffix.lower(), "backend": backend},
        )

    reported_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    reported_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if reported_frames < 0 or reported_frames > max_frames * 100:
        reported_frames = 0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if width <= 0 or height <= 0:
        capture.release()
        raise VideoDecodeError(
            "Video has invalid dimensions",
            diagnostics={"width": width, "height": height, "backend": backend},
        )

    provisional_fps, _ = _normalise_fps(reported_fps, declared_duration_seconds, max(reported_frames, 1))
    timestamps: list[float] = []
    fallback_count = 0
    previous_ms = -1.0
    try:
        for index in range(max_frames):
            ok, _frame = capture.read()
            if not ok:
                break
            timestamp_ms = float(capture.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
            fallback_ms = index * 1000.0 / provisional_fps
            if not np.isfinite(timestamp_ms) or timestamp_ms < 0 or (index and timestamp_ms <= previous_ms):
                timestamp_ms = fallback_ms
                fallback_count += 1
            if timestamp_ms / 1000.0 > max_seconds:
                break
            timestamps.append(timestamp_ms)
            previous_ms = timestamp_ms
    finally:
        capture.release()

    frame_count = len(timestamps)
    fps, fps_source = _normalise_fps(reported_fps, declared_duration_seconds, frame_count)
    if frame_count > 1:
        positive_steps = np.diff(np.asarray(timestamps, dtype=np.float64))
        positive_steps = positive_steps[positive_steps > 0]
        step_ms = float(np.median(positive_steps)) if len(positive_steps) else 1000.0 / fps
        duration_seconds = (timestamps[-1] + step_ms) / 1000.0
    else:
        duration_seconds = frame_count / fps
    timestamp_source = "container" if fallback_count == 0 else ("mixed" if fallback_count < frame_count else "fps_fallback")
    diagnostics = {
        "backend": backend,
        "reported_fps": reported_fps,
        "reported_frame_count": reported_frames,
        "decoded_frame_count": frame_count,
        "decoded_duration_seconds": duration_seconds,
        "fps": fps,
        "fps_source": fps_source,
        "timestamp_source": timestamp_source,
        "timestamp_fallback_count": fallback_count,
        "width": width,
        "height": height,
        "streaming_decode": True,
    }
    return _Probe(
        fps=fps,
        width=width,
        height=height,
        frame_count=frame_count,
        duration_seconds=duration_seconds,
        diagnostics=diagnostics,
    )


def _video_data(path: Path, probe: _Probe, *, cleanup_dir: Path | None, max_frames: int, max_seconds: float) -> VideoData:
    return VideoData(
        path=path,
        fps=probe.fps,
        width=probe.width,
        height=probe.height,
        frame_count=probe.frame_count,
        duration_seconds=probe.duration_seconds,
        diagnostics=dict(probe.diagnostics),
        cleanup_dir=cleanup_dir,
        max_frames=max_frames,
        max_seconds=max_seconds,
    )


def _ffmpeg_executable() -> str:
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise VideoDecodeError(
            "The server cannot decode this browser video because the FFmpeg fallback is not installed",
            code="decoder_unavailable",
        ) from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def _transcode_for_analysis(source: Path, target: Path) -> None:
    command = [
        _ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source), "-an", "-map", "0:v:0", "-vsync", "0",
        "-c:v", "mjpeg", "-q:v", "3", str(target),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=240, check=False)
    if completed.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        detail = (completed.stderr or completed.stdout or "FFmpeg produced no output").strip()
        raise VideoDecodeError(
            "The browser video container could not be normalised for analysis",
            diagnostics={"ffmpeg_error": detail[-1000:]},
        )


def _is_long_enough(video: VideoData) -> bool:
    return video.frame_count >= MINIMUM_FRAMES and video.duration_seconds >= MINIMUM_SECONDS


def read_video(
    path: Path,
    *,
    max_frames: int = 10800,
    max_seconds: float = 180.0,
    declared_duration_ms: float | None = None,
) -> VideoData:
    declared_seconds = declared_duration_ms / 1000.0 if declared_duration_ms and declared_duration_ms > 0 else None
    direct_error: VideoDecodeError | None = None
    direct: VideoData | None = None
    try:
        direct_probe = _probe(
            path,
            max_frames=max_frames,
            max_seconds=max_seconds,
            declared_duration_seconds=declared_seconds,
        )
        direct = _video_data(path, direct_probe, cleanup_dir=None, max_frames=max_frames, max_seconds=max_seconds)
    except VideoDecodeError as exc:
        direct_error = exc

    if direct and _is_long_enough(direct):
        return direct

    temporary_dir = Path(tempfile.mkdtemp(prefix="went-video-"))
    recovered_path = temporary_dir / "normalised.avi"
    try:
        _transcode_for_analysis(path, recovered_path)
        recovered_probe = _probe(
            recovered_path,
            max_frames=max_frames,
            max_seconds=max_seconds,
            declared_duration_seconds=declared_seconds,
        )
    except Exception:
        shutil.rmtree(temporary_dir, ignore_errors=True)
        raise

    diagnostics = dict(recovered_probe.diagnostics)
    diagnostics["normalised_with_ffmpeg"] = True
    diagnostics["direct_decode"] = direct.diagnostics if direct else (direct_error.diagnostics if direct_error else {})
    recovered = _video_data(
        recovered_path,
        _Probe(
            fps=recovered_probe.fps,
            width=recovered_probe.width,
            height=recovered_probe.height,
            frame_count=recovered_probe.frame_count,
            duration_seconds=recovered_probe.duration_seconds,
            diagnostics=diagnostics,
        ),
        cleanup_dir=temporary_dir,
        max_frames=max_frames,
        max_seconds=max_seconds,
    )
    if not _is_long_enough(recovered):
        recovered.close()
        raise VideoDecodeError(
            "Video decoding produced less than 3 seconds of usable frames",
            diagnostics=recovered.diagnostics,
        )
    return recovered

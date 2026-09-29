from pathlib import Path
import subprocess

import cv2
import imageio_ffmpeg
import numpy as np
import pytest

from app.analysis.video import VideoDecodeError, _normalise_fps, read_video


def write_test_video(path: Path, *, fps: float = 15.0, seconds: float = 4.0) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (96, 64))
    assert writer.isOpened()
    for index in range(round(fps * seconds)):
        frame = np.full((64, 96, 3), 70, dtype=np.uint8)
        frame[:, : 30 + index % 20] = (80, 110, 140)
        writer.write(frame)
    writer.release()


def test_declared_duration_corrects_implausible_container_fps():
    # Synthetic 37-second protocol example; this does not record a camera video.
    fps, source = _normalise_fps(1000.0, 37.0, 1110)
    assert source == "declared_duration"
    assert fps == pytest.approx(30.0)


def test_read_video_accepts_more_than_three_seconds(tmp_path: Path):
    path = tmp_path / "complete.avi"
    write_test_video(path, seconds=4.0)
    video = read_video(path, declared_duration_ms=4000)
    try:
        assert video.duration_seconds >= 3.9
        first_pass = list(video.iter_frames())
        second_pass = list(video.iter_frames())
        assert len(first_pass) >= 60
        assert len(second_pass) == len(first_pass) == video.frame_count
        assert video.diagnostics["decoded_frame_count"] == video.frame_count
        assert not hasattr(video, "frames")
        assert all(right.timestamp_ms > left.timestamp_ms for left, right in zip(first_pass, first_pass[1:]))
    finally:
        video.close()


def test_read_video_accepts_browser_webm(tmp_path: Path):
    path = tmp_path / "browser.webm"
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=size=96x64:rate=15:duration=4",
        "-c:v", "libvpx", "-pix_fmt", "yuv420p", str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
    assert completed.returncode == 0, completed.stderr
    video = read_video(path, declared_duration_ms=4000)
    assert video.duration_seconds >= 3.9
    assert video.diagnostics["decoded_frame_count"] >= 60


def test_read_video_rejects_a_real_short_clip(tmp_path: Path):
    path = tmp_path / "short.avi"
    write_test_video(path, seconds=1.0)
    with pytest.raises(VideoDecodeError, match="less than 3 seconds"):
        read_video(path, declared_duration_ms=1000)

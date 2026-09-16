"use strict";

const CANDIDATE_TYPES = [
  "video/webm;codecs=vp8",
  "video/webm",
  "video/webm;codecs=vp9",
  "video/mp4;codecs=avc1.42E01E",
  "video/mp4",
];
const CHUNK_INTERVAL_MS = 1000;

export function isRecordingSupported() {
  return typeof window !== "undefined" && typeof window.MediaRecorder === "function";
}

export function pickMimeType() {
  if (!isRecordingSupported()) return "";
  return CANDIDATE_TYPES.find((type) => MediaRecorder.isTypeSupported?.(type)) || "";
}

export class VideoRecorder {
  constructor() {
    this.recorder = null;
    this.chunks = [];
    this.startedAt = 0;
    this.stoppedAt = 0;
    this.requestedMimeType = "";
    this.mimeType = "";
    this.error = null;
    this.stopPromise = null;
  }

  start(stream) {
    this.cancel();
    if (!isRecordingSupported() || !stream) return false;
    this.requestedMimeType = pickMimeType();
    this.chunks = [];
    this.error = null;
    try {
      // A quality hint, not a guarantee: browsers may choose a different bitrate.
      const settings = stream.getVideoTracks?.()[0]?.getSettings?.() || {};
      const bitrate = Math.max(4_000_000, Math.min(8_000_000, Math.round((settings.width || 1280) * (settings.height || 720) * 4.5)));
      const options = { videoBitsPerSecond: bitrate, ...(this.requestedMimeType ? { mimeType: this.requestedMimeType } : {}) };
      const recorder = new MediaRecorder(stream, options);
      this.recorder = recorder;
      this.mimeType = recorder.mimeType || this.requestedMimeType;
      this.videoBitsPerSecond = recorder.videoBitsPerSecond || bitrate;
      recorder.ondataavailable = (event) => {
        if (event.data?.size) this.chunks.push(event.data);
      };
      recorder.onerror = (event) => {
        this.error = event.error || new Error("Video recording failed");
      };
      recorder.start(CHUNK_INTERVAL_MS);
      this.startedAt = performance.now();
      return true;
    } catch (error) {
      this.error = error;
      this.recorder = null;
      return false;
    }
  }

  stop() {
    if (this.stopPromise) return this.stopPromise;
    const recorder = this.recorder;
    if (!recorder) return Promise.resolve(null);
    this.stopPromise = new Promise((resolve) => {
      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true;
        this.stoppedAt = performance.now();
        this.recorder = null;
        const result = this.buildResult();
        this.stopPromise = null;
        resolve(result);
      };
      recorder.addEventListener("stop", finish, { once: true });
      if (recorder.state === "inactive") {
        queueMicrotask(finish);
        return;
      }
      try {
        recorder.requestData?.();
        recorder.stop();
      } catch {
        finish();
      }
    });
    return this.stopPromise;
  }

  buildResult() {
    if (!this.chunks.length) return null;
    const type = this.mimeType || this.chunks[0]?.type || "video/webm";
    const blob = new Blob(this.chunks, { type });
    const result = {
      blob,
      mimeType: type,
      requestedMimeType: this.requestedMimeType,
      durationMs: this.startedAt ? Math.max(0, this.stoppedAt - this.startedAt) : 0,
      size: blob.size,
      chunkCount: this.chunks.length,
      videoBitsPerSecond: this.videoBitsPerSecond,
    };
    this.chunks = [];
    return result;
  }

  cancel() {
    const recorder = this.recorder;
    this.chunks = [];
    if (recorder && recorder.state !== "inactive") {
      try {
        recorder.stop();
      } catch {}
    }
    this.recorder = null;
    this.startedAt = 0;
    this.stoppedAt = 0;
    this.stopPromise = null;
  }
}

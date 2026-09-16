"use strict";

import { reactive } from "vue";
import { PositionStabilityLatch, evaluatePositionStability } from "./positionStabilityCheck.js";
import { buildRoiContract, CHEST_ROI_HEURISTIC_VERSION, DEFAULT_BOX, deriveChestRoi, deriveOfflineSearchRoi, pixelRoi } from "./calibrationBox.js";
import { evaluateSignalCalibration } from "./signalCalibrationCheck.js";
import { evaluatePositionSilhouette } from "./positionSilhouetteCheck.js";
import { measureArea } from "../realtime/areaSignal.js";

export const CAPTURE_PREVIEW_FPS = 15;
export const CAPTURE_PREVIEW_WINDOW = 20;
export const CAPTURE_CALIBRATION_DURATION_MS = 2000;

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export class CaptureManager {
  constructor({ onDirective, onCalibrationComplete, isPositionActive } = {}) {
    this.state = reactive({
      stream: null,
      ready: false,
      error: "",
      positionBox: { ...DEFAULT_BOX },
      lockedBox: null,
      chestRoi: null,
      offlineSearchRoi: null,
      positionQuality: null,
      boxLocked: false,
      confirming: false,
      positionChecking: false,
      calibrationRunning: false,
      calibrationResult: null,
      subjectPolarity: "dark",
      weakSignalWarning: false,
      lockProgress: 0,
      directive: "",
    });
    this.video = null;
    this.canvas = null;
    this.previewTimer = 0;
    this.previewSamples = [];
    this.session = 0;
    this.positionStabilityLatch = new PositionStabilityLatch({ holdMs: 2000, releaseMs: 1800, unknownReleaseMs: 2500 });
    this.onDirective = onDirective || (() => {});
    this.onCalibrationComplete = onCalibrationComplete || (() => {});
    this.isPositionActive = isPositionActive || (() => true);
  }

  bindElements(video, canvas) {
    this.video = video || null;
    this.canvas = canvas || null;
  }

  async start(video = this.video, canvas = this.canvas) {
    this.bindElements(video, canvas);
    this.stopStream();
    this.resetPosition();
    const session = this.session;
    if (!this.video) throw new Error("Camera video element is unavailable");
    if (!navigator.mediaDevices?.getUserMedia) {
      const error = new Error("This browser does not support camera capture");
      this.state.error = error.message;
      throw error;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          frameRate: { ideal: 30 },
          facingMode: "environment",
        },
        audio: false,
      });
      if (session !== this.session || !this.isPositionActive()) {
        stream.getTracks?.().forEach((track) => track.stop());
        return null;
      }
      this.video.srcObject = stream;
      await this.video.play();
      if (session !== this.session || !this.isPositionActive()) {
        stream.getTracks?.().forEach((track) => track.stop());
        if (this.video) this.video.srcObject = null;
        return null;
      }
      this.state.stream = stream;
      this.state.ready = true;
      this.state.error = "";
      this.setDirective(this.directiveFromReason("collecting"), "collecting");
      this.confirmPosition();
      return stream;
    } catch (error) {
      this.state.error = error?.message || "Unable to open camera";
      this.state.ready = false;
      throw error;
    }
  }

  stopStream() {
    this.session += 1;
    this.stopPositionPreview();
    this.state.confirming = false;
    this.state.calibrationRunning = false;
    this.state.stream?.getTracks?.().forEach((track) => track.stop());
    this.state.stream = null;
    this.state.ready = false;
    if (this.video) this.video.srcObject = null;
  }

  updatePositionBox(box) {
    this.state.positionBox = { ...box };
    if (!this.state.positionChecking || this.state.boxLocked) return;
    this.positionStabilityLatch.reset();
    this.previewSamples = [];
    this.state.lockProgress = 0;
    this.setDirective(this.directiveFromReason("collecting"), "collecting");
  }

  confirmPosition() {
    if (!this.state.ready || this.state.confirming || this.state.boxLocked) return false;
    this.state.confirming = true;
    this.state.positionChecking = true;
    this.state.weakSignalWarning = false;
    this.state.calibrationResult = null;
    this.positionStabilityLatch.reset();
    this.previewSamples = [];
    this.state.lockProgress = 0;
    this.setDirective(this.directiveFromReason("collecting"), "collecting");
    this.stopPositionPreview();
    this.state.positionChecking = true;
    this.previewTimer = globalThis.setInterval(() => this.samplePositionPreview(), 1000 / CAPTURE_PREVIEW_FPS);
    this.samplePositionPreview();
    return true;
  }

  captureArea(normalizedRoi, phase = "preview", threshold = null, polarity = this.state.subjectPolarity) {
    const captured = this.captureImage(normalizedRoi);
    if (!captured) return null;
    const { imageData, roi } = captured;
    return measureArea(imageData, {
      elapsedMs: 0,
      phase,
      roi,
      polarity,
      threshold,
    });
  }

  captureImage(normalizedRoi) {
    if (!normalizedRoi || !this.video?.videoWidth || !this.video?.videoHeight || !this.canvas) return null;
    const roi = pixelRoi(normalizedRoi, this.video.videoWidth, this.video.videoHeight);
    this.canvas.width = roi.width;
    this.canvas.height = roi.height;
    const context = this.canvas.getContext("2d", { willReadFrequently: true });
    context.drawImage(this.video, roi.x, roi.y, roi.width, roi.height, 0, 0, roi.width, roi.height);
    return { imageData: context.getImageData(0, 0, roi.width, roi.height), roi };
  }

  captureMeasurementSample(phase, elapsedMs) {
    const sample = this.captureArea(
      this.state.chestRoi,
      phase,
      this.state.calibrationResult?.referenceThreshold,
    );
    if (sample) sample.elapsedMs = elapsedMs;
    return sample;
  }

  samplePositionPreview() {
    if (!this.state.positionChecking || !this.isPositionActive() || !this.state.ready) return;
    const captured = this.captureImage(this.state.positionBox);
    if (!captured) return;
    const silhouette = evaluatePositionSilhouette(captured.imageData);
    if (silhouette.pass) this.state.subjectPolarity = silhouette.polarity;
    const sample = measureArea(captured.imageData, {
      phase: "position",
      roi: captured.roi,
      polarity: silhouette.polarity || this.state.subjectPolarity,
    });
    sample.silhouette = silhouette;
    this.previewSamples.push(sample);
    if (this.previewSamples.length > CAPTURE_PREVIEW_WINDOW) this.previewSamples.shift();
    const alignment = evaluatePositionStability(this.previewSamples);
    const reason = silhouette.pass ? alignment.reason : silhouette.reason;
    const status = silhouette.pass ? alignment.status : "fail";
    this.state.positionQuality = {
      status: status === "pass" ? "locked" : "unknown",
      occupancy: alignment.ratio,
      variation: alignment.variation,
      contrast: silhouette.contrast,
      subject_polarity: silhouette.polarity,
      edge_clearance: silhouette.edge,
      band_occupancy: Object.fromEntries((silhouette.bands || []).map((value, index) => [`band_${index + 1}`, value])),
      calibration_samples: 0,
    };
    const latch = this.positionStabilityLatch.update(status, performance.now());
    this.state.lockProgress = latch.progress;
    this.setDirective(this.directiveFromReason(reason, latch.progress), reason);
    if (latch.locked) void this.finalizePositionLock();
  }

  async finalizePositionLock() {
    if (this.state.boxLocked || this.state.calibrationRunning) return;
    this.stopPositionPreview();
    this.state.lockedBox = { ...this.state.positionBox };
    this.state.chestRoi = deriveChestRoi(this.state.lockedBox);
    this.state.offlineSearchRoi = deriveOfflineSearchRoi(this.state.lockedBox);
    this.state.boxLocked = true;
    this.state.lockProgress = 1;
    await this.runCalibrationBreath(this.session);
  }

  async runCalibrationBreath(session) {
    this.state.calibrationRunning = true;
    this.setDirective("Breathe normally and keep still", "calibrating");
    const calibrationSamples = [];
    const startedAt = performance.now();
    while (session === this.session && this.state.boxLocked && performance.now() - startedAt < CAPTURE_CALIBRATION_DURATION_MS) {
      const sample = this.captureArea(this.state.chestRoi, "calibration");
      if (sample) calibrationSamples.push(sample);
      await wait(1000 / CAPTURE_PREVIEW_FPS);
    }
    if (session !== this.session || !this.state.boxLocked) return;
    this.state.calibrationResult = evaluateSignalCalibration(calibrationSamples);
    if (!this.state.calibrationResult.valid) {
      this.state.calibrationRunning = false;
      this.state.confirming = false;
      this.state.boxLocked = false;
      this.state.lockedBox = null;
      this.state.chestRoi = null;
      this.state.offlineSearchRoi = null;
      this.state.positionQuality = null;
      this.positionStabilityLatch.reset();
      this.previewSamples = [];
      this.state.positionChecking = true;
      this.previewTimer = globalThis.setInterval(() => this.samplePositionPreview(), 1000 / CAPTURE_PREVIEW_FPS);
      this.setDirective(this.directiveFromReason(this.state.calibrationResult.reason), this.state.calibrationResult.reason);
      return;
    }
    this.state.positionQuality = {
      ...(this.state.positionQuality || {}),
      status: "locked",
      calibration_ratio: this.state.calibrationResult.ratio,
      calibration_samples: calibrationSamples.length,
    };
    this.state.weakSignalWarning = this.state.calibrationResult.valid && this.state.calibrationResult.weak;
    this.state.calibrationRunning = false;
    this.state.confirming = false;
    this.setDirective("");
    this.onCalibrationComplete({
      result: this.state.calibrationResult,
      weak: this.state.weakSignalWarning,
    });
  }

  stopPositionPreview() {
    globalThis.clearInterval(this.previewTimer);
    this.previewTimer = 0;
    this.state.positionChecking = false;
  }

  resetPosition() {
    this.session += 1;
    this.stopPositionPreview();
    this.positionStabilityLatch.reset();
    Object.assign(this.state, {
      positionBox: { ...DEFAULT_BOX },
      lockedBox: null,
      chestRoi: null,
      offlineSearchRoi: null,
      positionQuality: null,
      boxLocked: false,
      confirming: false,
      calibrationRunning: false,
      calibrationResult: null,
      subjectPolarity: "dark",
      weakSignalWarning: false,
      lockProgress: 0,
      directive: "",
    });
    this.previewSamples = [];
    this.onDirective("", "");
  }

  buildRoiContract(phaseWindows = {}, evidenceRequests = []) {
    if (!this.state.lockedBox || !this.video?.videoWidth || !this.video?.videoHeight) return null;
    return {
      ...buildRoiContract(this.state.lockedBox, this.video.videoWidth, this.video.videoHeight, this.state.positionQuality || {}),
      phase_windows: phaseWindows,
      evidence_requests: evidenceRequests,
    };
  }

  setDirective(text, key = text) {
    if (this.state.directive === text) return;
    this.state.directive = text;
    this.onDirective(text, key);
  }

  directiveFromReason(reason, progress = 0) {
    if (this.state.calibrationRunning) return "Breathe normally and keep still";
    if (reason === "too_far") return "Move a little closer";
    if (reason === "too_close") return "Move a little farther away";
    if (reason === "moving") return "Relax shoulders and hold still";
    if (reason === "low_contrast" || reason === "no_signal") return "Improve lighting and background contrast";
    if (reason === "incomplete_silhouette") return "Keep your head, chest, and waist in frame";
    if (reason === "box_too_tight") return "Enlarge the frame so the silhouette has background clearance";
    if (reason === "head_cropped") return "Lower or enlarge the frame so the top of your head is visible";
    if (reason === "waist_cropped") return "Raise or enlarge the frame so your waist stays visible";
    if (reason === "front_cropped") return "Move slightly so the chest stays in frame";
    if (reason === "ok" && progress > 0) return "Hold still while the position locks";
    return "Stand side-on with your back inside the green band";
  }

  dispose() {
    this.session += 1;
    this.stopPositionPreview();
    this.stopStream();
  }
}

export { CHEST_ROI_HEURISTIC_VERSION };

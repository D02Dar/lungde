"use strict";
//fixed the bounding box and area calculation for alignment evaluation, and added a latch to hold the pass state for a short time after passing
export const POSITION_STABILITY_DEFAULTS = Object.freeze({
  minimumSamples: 10,
  minimumOccupancy: 0.25,
  maximumOccupancy: 0.75,
  maximumVariation: 0.03,
});

export function evaluatePositionStability(recentSamples, options = {}) {
  const settings = { ...POSITION_STABILITY_DEFAULTS, ...options };
  if (!Array.isArray(recentSamples) || recentSamples.length < settings.minimumSamples) {
    return { status: "unknown", pass: false, reason: "collecting", ratio: null, variation: null };
  }
  const valid = recentSamples.filter((sample) => Number.isFinite(sample?.areaPx) && sample?.roi?.width > 0 && sample?.roi?.height > 0);
  if (valid.length < settings.minimumSamples) {
    return { status: "unknown", pass: false, reason: "collecting", ratio: null, variation: null };
  }
  const areas = valid.map((sample) => sample.areaPx);
  const mean = areas.reduce((sum, value) => sum + value, 0) / areas.length;
  if (!Number.isFinite(mean) || mean <= 0) {
    return { status: "unknown", pass: false, reason: "no_signal", ratio: null, variation: null };
  }
  const variance = areas.reduce((sum, value) => sum + (value - mean) ** 2, 0) / areas.length;
  const variation = Math.sqrt(variance) / mean;
  const firstRoi = valid[0].roi;
  const ratio = mean / (firstRoi.width * firstRoi.height);
  if (!Number.isFinite(ratio)) {
    return { status: "unknown", pass: false, reason: "no_signal", ratio: null, variation };
  }
  if (ratio < settings.minimumOccupancy) return { status: "fail", pass: false, reason: "too_far", ratio, variation };
  if (ratio > settings.maximumOccupancy) return { status: "fail", pass: false, reason: "too_close", ratio, variation };
  if (variation > settings.maximumVariation) return { status: "fail", pass: false, reason: "moving", ratio, variation };
  return { status: "pass", pass: true, reason: "ok", ratio, variation };
}

export class PositionStabilityLatch {
  constructor({ holdMs = 900, releaseMs = 1800, unknownReleaseMs = 2500 } = {}) {
    this.holdMs = holdMs; this.releaseMs = releaseMs; this.unknownReleaseMs = unknownReleaseMs; this.reset();
  }
  update(status, now = performance.now()) {
    if (status === "pass") {
      this._unknownSince = 0; this._failSince = 0;
      if (!this.locked) {
        if (!this._passSince) this._passSince = now;
        if (now - this._passSince >= this.holdMs) this.locked = true;
      }
    } else if (status === "fail") {
      this._passSince = 0; this._unknownSince = 0;
      if (this.locked) {
        if (!this._failSince) this._failSince = now;
        if (now - this._failSince >= this.releaseMs) this.locked = false;
      }
    } else {
      this._passSince = 0; this._failSince = 0;
      if (!this._unknownSince) this._unknownSince = now;
      if (this.locked && now - this._unknownSince >= this.unknownReleaseMs) this.locked = false;
    }
    const since = this.locked ? this.holdMs : (this._passSince ? now - this._passSince : 0);
    return { locked: this.locked, progress: Math.min(1, since / this.holdMs) };
  }
  reset() { this.locked = false; this._passSince = 0; this._failSince = 0; this._unknownSince = 0; }
}

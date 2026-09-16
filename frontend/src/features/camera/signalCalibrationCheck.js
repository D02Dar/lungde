"use strict";

export const SIGNAL_CALIBRATION_MINIMUM_SAMPLES = 10;
export const WEAK_SIGNAL_THRESHOLD = 0.02;//threshold for signal strength that indicates a weak signal
export const LIGHT_SATURATION_CAUTION = 0.08;//threshold for highlight saturation ratio that indicates potential overexposure for light subjects

export function evaluateSignalCalibration(samples, { minimumSamples = SIGNAL_CALIBRATION_MINIMUM_SAMPLES, weakSignalThreshold = WEAK_SIGNAL_THRESHOLD } = {}) {
  const areas = Array.isArray(samples) ? samples.map((sample) => Number(sample?.areaPx)).filter(Number.isFinite) : [];
  if (areas.length < minimumSamples) return { valid: false, weak: false, reason: "insufficient_samples", ratio: null, mean: null, range: null };
  const mean = areas.reduce((sum, value) => sum + value, 0) / areas.length;
  if (!Number.isFinite(mean) || mean <= 0) return { valid: false, weak: false, reason: "no_signal", ratio: null, mean, range: null };
  const range = Math.max(...areas) - Math.min(...areas);
  const ratio = range / mean;
  const thresholds = samples.map((sample) => Number(sample?.threshold)).filter(Number.isFinite).sort((a, b) => a - b);
  const referenceThreshold = thresholds.length ? median(thresholds) : null;
  const polarities = samples.map((sample) => sample?.polarity).filter((value) => value === "dark" || value === "light");
  const polarity = polarities.length
    ? ["dark", "light"].sort((a, b) => polarities.filter((value) => value === b).length - polarities.filter((value) => value === a).length)[0]
    : null;
  const saturationRatios = samples.map((sample) => Number(sample?.highlightSaturationRatio)).filter(Number.isFinite).sort((a, b) => a - b);
  const saturationRatio = saturationRatios.length ? median(saturationRatios) : null;
  const lightOverexposed = polarity === "light" && saturationRatio >= LIGHT_SATURATION_CAUTION;
  const weak = ratio < weakSignalThreshold || lightOverexposed;
  const reason = lightOverexposed ? "light_subject_saturation" : ratio < weakSignalThreshold ? "weak_signal" : "ok";
  return { valid: true, weak, reason, ratio, mean, range, referenceThreshold, polarity, saturationRatio, lightOverexposed };
}

function median(values) {
  const middle = Math.floor(values.length / 2);
  return values.length % 2 ? values[middle] : (values[middle - 1] + values[middle]) / 2;
}

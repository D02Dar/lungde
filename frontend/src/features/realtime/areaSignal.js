"use strict";
//提取胸廓面积通过灰度图和otsu阈值分割
import { toGrayscale } from "./grayscale.js";
import { measureSubjectSignal, otsuThreshold } from "./otsu.js";

export function measureArea(imageData, { polarity = "dark", elapsedMs = 0, phase = "idle", roi = null, threshold: fixedThreshold = null } = {}) {
  const grayscale = toGrayscale(imageData);
  const otsu = otsuThreshold(grayscale);
  const threshold = Number.isFinite(fixedThreshold) ? Math.max(0, Math.min(255, Math.round(fixedThreshold))) : otsu;
  const signal = measureSubjectSignal(grayscale, threshold, polarity, imageData.width, imageData.height);
  let saturated = 0, highlightSaturated = 0;
  for (const value of grayscale) {
    if (value <= 8 || value >= 247) saturated += 1;
    if (value >= 247) highlightSaturated += 1;
  }
  return {
    timestamp: new Date().toISOString(), elapsedMs, phase, roi,
    polarity,
    threshold, otsuThreshold: otsu, thresholdSource: Number.isFinite(fixedThreshold) ? "calibrated" : "otsu",
    signalMethod: signal.method,
    saturationRatio: grayscale.length ? saturated / grayscale.length : 0,
    highlightSaturationRatio: grayscale.length ? highlightSaturated / grayscale.length : 0,
    areaPx: signal.value, areaRatio: grayscale.length ? signal.value / grayscale.length : 0,
  };
}

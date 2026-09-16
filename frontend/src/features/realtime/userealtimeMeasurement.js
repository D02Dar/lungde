"use strict";

import { measureArea } from "./areaSignal.js";
import { computerealtimeMetrics } from "./metrics.js";

export function createrealtimeMeasurement({ fps = 30, polarity = "dark", roi = null } = {}) {
  const samples = [];
  return {
    samples,
    sample(imageData, elapsedMs, phase = "tidal") {
      const sample = measureArea(imageData, { polarity, elapsedMs, phase, roi });
      samples.push({ ...sample, value: sample.areaPx });
      return sample;
    },
    results() { return computerealtimeMetrics(samples, fps); },
    reset() { samples.length = 0; },
  };
}

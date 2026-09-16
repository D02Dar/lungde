"use strict";

export function resampleAndFilter(samples, targetFps = 30) {
  if (!samples?.length) return { values: [], rawValues: [], timestampsMs: [], fps: targetFps };
  const ordered = [...samples]
    .filter((sample) => Number.isFinite(sample?.elapsedMs) && Number.isFinite(sample?.areaPx))
    .sort((a, b) => a.elapsedMs - b.elapsedMs);
  if (!ordered.length) return { values: [], rawValues: [], timestampsMs: [], fps: targetFps };

  const start = ordered[0].elapsedMs;
  const end = ordered.at(-1).elapsedMs;
  const step = 1000 / targetFps;
  const timestampsMs = [];
  const rawValues = [];
  let cursor = 0;
  for (let time = start; time <= end; time += step) {
    while (cursor < ordered.length - 2 && ordered[cursor + 1].elapsedMs < time) cursor += 1;
    const left = ordered[cursor];
    const right = ordered[Math.min(cursor + 1, ordered.length - 1)];
    const span = Math.max(1, right.elapsedMs - left.elapsedMs);
    const mix = Math.max(0, Math.min(1, (time - left.elapsedMs) / span));
    rawValues.push(left.areaPx + (right.areaPx - left.areaPx) * mix);
    timestampsMs.push(time);
  }

  const outlierRemoved = hampelFilter(rawValues, Math.max(3, Math.round(targetFps * 0.5)));
  // Vc/Vt must retain the slow inhale/exhale excursion and plateau levels.
  const values = movingAverage(outlierRemoved, Math.max(3, Math.round(targetFps * 0.3)));
  return { values, rawValues, timestampsMs, fps: targetFps };
}

function hampelFilter(values, windowSize) {
  const output = [...values];
  const radius = Math.floor(windowSize / 2);
  for (let i = 0; i < values.length; i += 1) {
    const left = Math.max(0, i - radius);
    const right = Math.min(values.length, i + radius + 1);
    const window = values.slice(left, right);
    const median = computeMedian(window);
    const deviations = window.map(v => Math.abs(v - median));
    const mad = computeMedian(deviations) * 1.4826;
    if (mad > 1e-9 && Math.abs(values[i] - median) > 3.5 * mad) {
      output[i] = median;
    }
  }
  return output;
}

function computeMedian(values) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function removeMovingBaseline(values, window) {
  const baseline = movingAverage(values, window);
  return values.map((value, index) => value - baseline[index]);
}

export function movingAverage(values, window) {
  if (!values.length) return [];
  const radius = Math.max(1, Math.floor(window / 2));
  const prefix = new Float64Array(values.length + 1);
  for (let index = 0; index < values.length; index += 1) prefix[index + 1] = prefix[index] + values[index];
  return values.map((_, index) => {
    const left = Math.max(0, index - radius);
    const right = Math.min(values.length - 1, index + radius);
    return (prefix[right + 1] - prefix[left]) / (right - left + 1);
  });
}

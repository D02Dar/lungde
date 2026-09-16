"use strict";

export function detectPeaksAndTroughs(values, { minDistance = 12, prominence = 0 } = {}) {
  const candidates = [];
  const radius = Math.max(2, minDistance);
  // Find all peaks and troughs within the given radius
  for (let index = 1; index < values.length - 1; index += 1) {
    const current = values[index];
    const isPeak = current >= values[index - 1] && current > values[index + 1];
    const isTrough = current <= values[index - 1] && current < values[index + 1];
    if (!isPeak && !isTrough) continue;
    const left = values.slice(Math.max(0, index - radius), index);
    const right = values.slice(index + 1, Math.min(values.length, index + radius + 1));
    const localProminence = isPeak
      ? current - Math.max(Math.min(...left), Math.min(...right))
      : Math.min(Math.max(...left), Math.max(...right)) - current;
    if (localProminence >= prominence) candidates.push({ index, type: isPeak ? "peak" : "trough", value: current, prominence: localProminence });
  }
//   Sort candidates by index to ensure they are in order
  const accepted = [];
  for (const candidate of candidates) {
    const previous = accepted.at(-1);
    if (!previous || candidate.index - previous.index >= minDistance) {
      accepted.push(candidate);
    } else if (candidate.type === previous.type && candidate.prominence > previous.prominence) {
      accepted[accepted.length - 1] = candidate;
    }
  }
  return accepted;
}

export function findSmoothedExtremum(values, direction, { radius = 2 } = {}) {
  if (!Array.isArray(values) || !values.length) return null;
  const smooth = centeredMovingAverage(values, radius);
  const wantedType = direction === "low" ? "trough" : "peak";
  const pool = smooth.map((value, index) => ({ index, type: wantedType, value, prominence: 0 }));
  return pool.reduce((best, point) => {
    if (!best) return point;
    return direction === "low"
      ? (point.value < best.value ? point : best)
      : (point.value > best.value ? point : best);
  }, null);
}

function centeredMovingAverage(values, radius) {
  const width = Math.max(0, Math.round(radius));
  return values.map((_, index) => {
    let total = 0;
    let count = 0;
    for (let offset = -width; offset <= width; offset += 1) {
      const sampleIndex = Math.max(0, Math.min(values.length - 1, index + offset));
      const value = Number(values[sampleIndex]);
      if (!Number.isFinite(value)) continue;
      total += value;
      count += 1;
    }
    return count ? total / count : Number(values[index]);
  });
}

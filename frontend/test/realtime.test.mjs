import assert from 'node:assert/strict';
import { otsuThreshold, countSubjectPixels, measureSubjectSignal } from '../src/features/realtime/otsu.js';
import { computeRealtimeMetrics } from '../src/features/realtime/metrics.js';
import { movingAverage, resampleAndFilter } from '../src/features/realtime/filter.js';
import { measureArea } from '../src/features/realtime/areaSignal.js';
import { LEGACY_REALTIME_REVIEW_VERSION, REALTIME_REVIEW_VERSION, reviewStoredRealtime } from '../src/features/realtime/reviewStored.js';

const pixels = new Uint8Array([...Array(50).fill(20), ...Array(50).fill(220)]);
const threshold = otsuThreshold(pixels);
assert.ok(threshold >= 20 && threshold < 220);
assert.equal(countSubjectPixels(pixels, threshold, 'dark'), 50);
assert.equal(countSubjectPixels(pixels, threshold, 'light'), 50);

assert.deepEqual(movingAverage([10, 10, 10, 10, 10], 3), [10, 10, 10, 10, 10], 'moving average must preserve a constant signal');
const boundedInput = Array.from({ length: 90 }, (_, index) => 2000 + 100 * Math.sin(index / 5));
const boundedAverage = movingAverage(boundedInput, 11);
assert.ok(Math.max(...boundedAverage) <= Math.max(...boundedInput));
assert.ok(Math.min(...boundedAverage) >= Math.min(...boundedInput));

const resampled = resampleAndFilter([
  { areaPx: 3000, elapsedMs: 0 },
  { areaPx: 3200, elapsedMs: 1000 },
  { areaPx: 2800, elapsedMs: 2000 },
], 10);
assert.ok(resampled.rawValues.length > 0);
assert.ok(Math.max(...resampled.rawValues) <= 3200);
assert.ok(Math.min(...resampled.rawValues) >= 2800);
assert.equal(resampled.values.length, resampled.rawValues.length);

const imageData = { data: new Uint8ClampedArray([
  20, 20, 20, 255,
  80, 80, 80, 255,
  180, 180, 180, 255,
  230, 230, 230, 255,
]) };
const automaticArea = measureArea(imageData);
const calibratedArea = measureArea(imageData, { threshold: 100 });
assert.equal(calibratedArea.threshold, 100);
assert.equal(calibratedArea.thresholdSource, 'calibrated');
assert.equal(calibratedArea.otsuThreshold, automaticArea.threshold);
assert.equal(calibratedArea.areaPx, 2);
assert.equal(measureArea(imageData, { threshold: 100, polarity: 'light' }).areaPx, 2);
assert.equal(measureArea(imageData, { threshold: 100, polarity: 'light' }).polarity, 'light');

const lightWidth = 30, lightHeight = 20;
const lightTorso = new Uint8Array(lightWidth * lightHeight).fill(10);
for (let y = 0; y < lightHeight; y += 1) for (let x = 8; x < 18; x += 1) lightTorso[y * lightWidth + x] = 240;
const lightWithRearArm = lightTorso.slice();
for (let y = 5; y < 15; y += 1) for (let x = 18; x < 26; x += 1) lightWithRearArm[y * lightWidth + x] = 240;
const torsoSignal = measureSubjectSignal(lightTorso, 100, 'light', lightWidth, lightHeight);
const armSignal = measureSubjectSignal(lightWithRearArm, 100, 'light', lightWidth, lightHeight);
assert.equal(torsoSignal.method, 'light_front_contour');
assert.equal(armSignal.value, torsoSignal.value, 'a rear arm connection must not move the light-shirt front contour');
assert.ok(countSubjectPixels(lightWithRearArm, 100, 'light', lightWidth, lightHeight) > countSubjectPixels(lightTorso, 100, 'light', lightWidth, lightHeight));

const fps = 10;
const samples = [];
for (let index = 0; index < 260; index += 1) {
  const seconds = index / fps;
  let phase = seconds < 3 ? 'countdown' : seconds < 15 ? 'tidal' : seconds < 20 ? 'maxInhale' : 'maxExhale';
  let value = 100 + 10 * Math.sin(2 * Math.PI * 0.25 * seconds);
  if (phase === 'maxInhale') value += 35;
  if (phase === 'maxExhale') value -= 35;
  samples.push({ value, elapsedMs: seconds * 1000, phase });
}
const result = computeRealtimeMetrics(samples, fps, { rawSamples: samples, roiPixels: 1000 });
assert.equal(result.valid, true);
assert.ok(Math.abs(result.rrHz - 0.25) < 0.05);
assert.ok(result.vcPx > result.vtPx);
assert.equal(result.ratio, result.vcPx / result.vtPx);
assert.equal(result.rrValid, true);
assert.equal(result.vtValid, true);
assert.equal(result.vcValid, true);
assert.equal(result.ratioValid, true);
const storedReview = reviewStoredRealtime({ samples: samples.map(sample => ({ areaPx: sample.value, elapsedMs: sample.elapsedMs, phase: sample.phase, roi: { width: 50, height: 50 } })), captureRoi: { phase_windows: { tidal: [3,15], maxInhale: [15,20], maxExhale: [20,26] } } }, fps);
assert.equal(REALTIME_REVIEW_VERSION, 'polarity-contour-amplitude-v4');
assert.equal(storedReview.algorithmVersion, LEGACY_REALTIME_REVIEW_VERSION);
assert.ok(storedReview.vcPx > storedReview.vtPx);
const contourStoredReview = reviewStoredRealtime({ samples: samples.map(sample => ({ areaPx: sample.value, elapsedMs: sample.elapsedMs, phase: sample.phase, signalMethod: 'light_front_contour', roi: { width: 50, height: 50 } })), captureRoi: { phase_windows: { tidal: [3,15], maxInhale: [15,20], maxExhale: [20,26] } } }, fps);
assert.equal(contourStoredReview.algorithmVersion, REALTIME_REVIEW_VERSION);

// A lower observed mobile-camera sample rate is complete when timestamps cover
// every phase without long gaps; it must not be compared to the resample rate.
const phaseWindows = { tidal: [3, 15], maxInhale: [15, 20], maxExhale: [20, 26] };
const lowerObservedRate = computeRealtimeMetrics(samples, 15, { rawSamples: samples, sourceSamples: samples, roiPixels: 1000, phaseWindows });
assert.ok(!lowerObservedRate.invalidReasons.includes('incomplete_tidal'));
assert.ok(!lowerObservedRate.invalidReasons.includes('incomplete_maxInhale'));
assert.ok(!lowerObservedRate.invalidReasons.includes('incomplete_maxExhale'));

// Volume metrics remain usable when the tidal section does not contain enough
// cycles for a reliable respiratory-rate estimate.
const shortTidalResult = computeRealtimeMetrics(samples, fps, { rawSamples: samples, roiPixels: 1000, minimumTidalCycles: 99 });
assert.equal(shortTidalResult.valid, true);
assert.equal(shortTidalResult.rrValid, false);
assert.equal(shortTidalResult.vtValid, true);
assert.equal(shortTidalResult.vcValid, true);
assert.equal(shortTidalResult.ratioValid, true);
assert.equal(shortTidalResult.rrBpm, null);
assert.ok(Number.isFinite(shortTidalResult.vtPx));
assert.ok(Number.isFinite(shortTidalResult.vcPx));
assert.equal(shortTidalResult.ratio, shortTidalResult.vcPx / shortTidalResult.vtPx);

const monotonic = Array.from({ length: 260 }, (_, index) => {
  const seconds = index / fps;
  const phase = seconds < 3 ? 'countdown' : seconds < 15 ? 'tidal' : seconds < 20 ? 'maxInhale' : 'maxExhale';
  return { value: 400 - index, areaPx: 400 - index, elapsedMs: seconds * 1000, phase, roi: { width: 30, height: 20 } };
});
const invalid = computeRealtimeMetrics(monotonic, fps, { rawSamples: monotonic, roiPixels: 600 });
assert.equal(invalid.valid, false);
assert.equal(invalid.rrBpm, null);
assert.equal(invalid.vtPx, null);
assert.equal(invalid.diagnostic.tidalCycles, 0);
assert.ok(invalid.rrInvalidReasons.includes('insufficient_tidal_cycles'));
assert.ok(!invalid.invalidReasons.includes('insufficient_tidal_cycles'));

const weakVital = samples.map((sample) => {
  const offset = sample.phase === 'maxInhale' ? 4 : sample.phase === 'maxExhale' ? -4 : 0;
  return { ...sample, value: offset ? 100+offset : sample.value };
});
const weakVitalResult = computeRealtimeMetrics(weakVital, fps, { rawSamples: weakVital, roiPixels: 1000 });
assert.equal(weakVitalResult.valid, false);
assert.ok(weakVitalResult.invalidReasons.includes('vital_not_greater_than_tidal'));
assert.ok(Number.isFinite(weakVitalResult.diagnostic.vtPx));
assert.ok(Number.isFinite(weakVitalResult.diagnostic.vcPx));
assert.ok(Number.isFinite(weakVitalResult.diagnostic.ratio));

const impossibleRaw = samples.map((sample) => ({ ...sample, areaPx: sample.value * 100 }));
const impossible = computeRealtimeMetrics(samples, fps, { rawSamples: impossibleRaw, roiPixels: 500 });
assert.equal(impossible.valid, false);
assert.ok(impossible.invalidReasons.includes('area_exceeds_roi'));
console.log('realtime tests passed');

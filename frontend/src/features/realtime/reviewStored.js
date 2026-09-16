"use strict";
import { resampleAndFilter } from './filter.js';
import { computeRealtimeMetrics } from './metrics.js';

export const REALTIME_REVIEW_VERSION = 'polarity-contour-amplitude-v4';
export const LEGACY_REALTIME_REVIEW_VERSION = 'area-amplitude-v3';

export function realtimeReviewVersion(record) {
  return record?.samples?.some(sample => typeof sample?.signalMethod === 'string')
    ? REALTIME_REVIEW_VERSION
    : LEGACY_REALTIME_REVIEW_VERSION;
}

export function reviewStoredRealtime(record, targetFps = 15) {
  const source = (record?.samples || []).filter(sample => Number.isFinite(sample?.elapsedMs) && Number.isFinite(sample?.areaPx));
  if (!source.length) return null;
  const windows = record?.captureRoi?.phase_windows || {};
  const phaseAt = timeMs => Object.entries(windows).find(([, range]) => timeMs >= range[0]*1000 && timeMs < range[1]*1000)?.[0] || '';
  const filtered = resampleAndFilter(source, targetFps);
  const samples = filtered.values.map((value, index) => ({ value, elapsedMs: filtered.timestampsMs[index], phase: phaseAt(filtered.timestampsMs[index]) }));
  const rawSamples = filtered.rawValues.map((areaPx, index) => ({ areaPx, elapsedMs: filtered.timestampsMs[index], phase: phaseAt(filtered.timestampsMs[index]), roi: source[0]?.roi || null }));
  const roiPixels = source[0]?.roi ? source[0].roi.width*source[0].roi.height : null;
  const result = computeRealtimeMetrics(samples, filtered.fps, { rawSamples, sourceSamples: source, phaseWindows: windows, roiPixels });
  return result ? { ...result, algorithmVersion: realtimeReviewVersion(record) } : null;
}

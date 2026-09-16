"use strict";

import { findSmoothedExtremum } from "../realtime/peaks.js";

export function selectEvidence(samples = [], results = {}) {
  if (!samples.length) return [];
  const sorted = [...samples].filter((sample) => Number.isFinite(sample?.elapsedMs)).sort((a, b) => a.elapsedMs - b.elapsedMs);
  if (!sorted.length) return [];

  // The inhale turning point may land in the following preparation window due
  // to the user's reaction time. Keep that transition available for finding
  // the peak without including it in the volume metric itself.
  const inhaleSamples = sorted.filter((sample) => ["maxInhale", "exhalePrep"].includes(sample.phase) && Number.isFinite(sample.areaPx));
  const exhaleSamples = sorted.filter((sample) => sample.phase === "maxExhale" && Number.isFinite(sample.areaPx));
  const output = [];
  const nearest = (values, ms) => Number.isFinite(ms) && values.length ? values.reduce((a,b)=>Math.abs(b.elapsedMs-ms)<Math.abs(a.elapsedMs-ms)?b:a) : null;
  const inhale = nearest(inhaleSamples, results.diagnostic?.inhaleMs) || phaseExtremum(inhaleSamples, "high");
  const exhale = nearest(exhaleSamples, results.diagnostic?.exhaleMs) || phaseExtremum(exhaleSamples, "low");
  if (inhale) output.push(frame("maxInhale", "Maximum inhale peak", inhale));
  if (exhale) output.push(frame("maxExhale", "Maximum exhale trough", exhale));

  const qualitySamples = sorted.filter((sample) => Number.isFinite(sample.quality));
  if (qualitySamples.length) output.push(frame("bestSignal", "Highest-quality Realtime frame", [...qualitySamples].sort((a, b) => b.quality - a.quality)[0]));

  const persisted = Array.isArray(results.evidence) ? results.evidence : [];
  for (const item of persisted) {
    if (!item?.key || !Number.isFinite(item.elapsed_ms)) continue;
    output.push({
      key: item.key,
      label: item.label,
      elapsedMs: item.elapsed_ms,
      actualElapsedMs: item.actual_elapsed_ms,
      timestampErrorMs: item.timestamp_error_ms,
      phase: item.phase || "",
      roi: item.roi || null,
      roiKind: item.roi_kind,
      areaPx: item.area_px,
      threshold: item.threshold,
      imageUrl: item.image_url,
      source: "backend",
      summary: item.label,
    });
  }
  return deduplicate(output);
}

function phaseExtremum(samples, direction) {
  if (!samples.length) return null;
  const point = findSmoothedExtremum(samples.map((sample) => sample.areaPx), direction, {
    radius: 2,
  });
  return point ? samples[point.index] : null;
}

function deduplicate(items) {
  const merged = new Map();
  for (const item of items) merged.set(item.key, { ...(merged.get(item.key) || {}), ...item });
  return [...merged.values()].sort((a, b) => Number(a.elapsedMs || 0) - Number(b.elapsedMs || 0));
}

function frame(key, label, sample) {
  return {
    key,
    label,
    elapsedMs: sample.elapsedMs,
    phase: sample.phase || "",
    roi: sample.roi || null,
    threshold: Number.isFinite(sample.threshold) ? sample.threshold : null,
    areaPx: Number.isFinite(sample.areaPx) ? sample.areaPx : null,
    summary: `Area ${Math.round(sample.areaPx || 0)} px`,
  };
}

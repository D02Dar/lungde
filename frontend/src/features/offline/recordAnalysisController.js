"use strict";

import { analyzeVideo, reanalyzeVideo } from "./api.js";
import { selectEvidence } from "../records/evidence.js";

export async function analyzeStoredRecord(record, { signal, updateRecording }) {
  if (!record?.videoBlob && !record?.backendAnalysisId) throw new Error("This record has no video to analyze");
  if (!record.backendAnalysisId && (record.durationMs || 0) < 3000) throw new Error("offline analysis requires at least 3 seconds of video");
  try {
    const result = await requestAnalysis(record, signal);
    return updateRecording(record.id, {
      offline: result,
      evidence: mergeEvidence(record, result.evidence || []),
      backendAnalysisId: result.analysis_id || record.backendAnalysisId || null,
      backendStatus: result.status,
      backendError: null,
    });
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    await updateRecording(record.id, {
      backendAnalysisId: error.analysisId || record.backendAnalysisId || null,
      backendStatus: "failed",
      backendError: {
        code: error.code || "analysis_failed",
        message: error.message || "offline analysis failed",
        diagnostics: error.diagnostics || null,
      },
    });
    throw error;
  }
}

async function requestAnalysis(record, signal) {
  if (record.backendAnalysisId) {
    try { return await reanalyzeVideo(record.backendAnalysisId, signal); }
    catch (error) {
      if (error.status !== 404 || !record.videoBlob) throw error;
    }
  }
  return analyzeVideo(record.videoBlob, record.captureRoi, {
    signal,
    frontendRecordId: record.id,
    durationMs: record.durationMs,
    filename: `went-${record.id}.webm`,
  });
}

export function mergeEvidence(record, backendItems = []) {
  const recoveredLocal = selectEvidence(record?.samples || [], {});
  const existing = Array.isArray(record?.evidence) ? record.evidence : [];
  const backend = backendItems.map(fromBackendEvidence);
  const merged = new Map();
  for (const item of [...recoveredLocal, ...existing, ...backend]) {
    if (!item?.key) continue;
    const previous = merged.get(item.key) || {};
    merged.set(item.key, { ...previous, ...item });
  }
  return [...merged.values()].sort((a, b) => Number(a.elapsedMs || 0) - Number(b.elapsedMs || 0));
}

export function fromBackendEvidence(item) {
  return {
    key: item.key,
    label: item.label,
    elapsedMs: item.elapsed_ms,
    ...(Number.isFinite(item.actual_elapsed_ms) ? { actualElapsedMs: item.actual_elapsed_ms } : {}),
    ...(Number.isFinite(item.timestamp_error_ms) ? { timestampErrorMs: item.timestamp_error_ms } : {}),
    phase: item.phase || "",
    areaPx: item.area_px,
    threshold: item.threshold,
    roi: item.roi || null,
    roiKind: item.roi_kind,
    frameWidth: item.frame_width,
    frameHeight: item.frame_height,
    imageUrl: item.image_url,
    source: "backend",
  };
}

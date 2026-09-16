"use strict";

const API_BASE_URL = String(import.meta.env?.VITE_API_BASE_URL || "").replace(/\/+$/, "");
export const apiUrl = path => `${API_BASE_URL}${path}`;

export class AnalysisApiError extends Error {
  constructor(message, detail = {}, status = 0) {
    super(message);
    this.name = "AnalysisApiError";
    this.code = detail?.code || "analysis_failed";
    this.analysisId = detail?.analysis_id || null;
    this.diagnostics = detail?.diagnostics || null;
    this.status = status;
  }
}

async function payloadOrEmpty(response) {
  return response.json().catch(() => ({}));
}

function throwResponseError(response, payload) {
  const detail = payload.detail || payload || {};
  const message = detail.message || (typeof detail === "string" ? detail : `Analysis failed with HTTP ${response.status}`);
  throw new AnalysisApiError(message, detail, response.status);
}

export async function analyzeVideo(videoBlob, captureMetadata, options = {}) {
  const {
    signal,
    frontendRecordId = null,
    durationMs = null,
    filename = "respiratory-capture.webm",
  } = options;
  const form = new FormData();
  form.append("video", videoBlob, filename);
  form.append("capture_roi", JSON.stringify(captureMetadata));
  if (frontendRecordId != null) form.append("frontend_record_id", String(frontendRecordId));
  if (Number.isFinite(durationMs)) form.append("declared_duration_ms", String(durationMs));
  const response = await fetch(apiUrl("/api/analyze"), { method: "POST", body: form, signal });
  const payload = await payloadOrEmpty(response);
  if (!response.ok) throwResponseError(response, payload);
  return payload;
}

export async function reanalyzeVideo(analysisId, signal) {
  const response = await fetch(apiUrl(`/api/analyses/${encodeURIComponent(analysisId)}/reanalyze`), {
    method: "POST",
    signal,
  });
  const payload = await payloadOrEmpty(response);
  if (!response.ok) throwResponseError(response, payload);
  return payload;
}

export async function getAnalysis(analysisId, signal) {
  const response = await fetch(apiUrl(`/api/analyses/${encodeURIComponent(analysisId)}`), { signal });
  const payload = await payloadOrEmpty(response);
  if (!response.ok) throwResponseError(response, payload);
  return payload;
}

export async function deleteAnalysis(analysisId, signal) {
  if (!analysisId) return false;
  const response = await fetch(apiUrl(`/api/analyses/${encodeURIComponent(analysisId)}`), { method: "DELETE", signal });
  if (response.status === 404) return false;
  const payload = await payloadOrEmpty(response);
  if (!response.ok) throwResponseError(response, payload);
  return Boolean(payload.deleted);
}

async function exportBlob(response) {
  if (!response.ok) throwResponseError(response, await payloadOrEmpty(response));
  return response.blob();
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

export async function downloadBackendAnalysisExport(analysisId, signal) {
  if (!analysisId) throw new Error("Run offline analysis before requesting a backend archive");
  const response = await fetch(apiUrl(`/api/analyses/${encodeURIComponent(analysisId)}/export`), { signal });
  const blob = await exportBlob(response);
  saveBlob(blob, `went-${analysisId}-analysis.zip`);
}

export async function downloadBackendComparisonExport(records, signal) {
  const selected = Array.from(records || []);
  const analysisIds = selected.map(record => record?.backendAnalysisId).filter(Boolean);
  if (analysisIds.length < 2 || analysisIds.length !== selected.length) {
    throw new Error("Every checked record must complete offline analysis before backend ZIP export");
  }
  const response = await fetch(apiUrl("/api/exports/comparison"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ analysis_ids: analysisIds }),
    signal,
  });
  const blob = await exportBlob(response);
  saveBlob(blob, `went-comparison-${analysisIds.length}-runs.zip`);
}

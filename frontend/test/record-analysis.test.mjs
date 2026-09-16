import assert from 'node:assert/strict';
import { analyzeStoredRecord, fromBackendEvidence, mergeEvidence } from '../src/features/offline/recordAnalysisController.js';
import { apiUrl } from '../src/features/offline/api.js';

const originalFetch = globalThis.fetch;
assert.equal(apiUrl('/api/health'), '/api/health');

function response(status, payload) {
  return new Response(JSON.stringify(payload), { status, headers: { 'content-type': 'application/json' } });
}

function updater(seed, calls) {
  let current = { ...seed };
  return async (id, patch) => {
    assert.equal(id, seed.id);
    calls.push(patch);
    current = { ...current, ...patch };
    return current;
  };
}

const evidence = {
  key: 'offlinePeak', label: 'offline waveform peak', elapsed_ms: 1500,
  phase: '', area_px: null, threshold: null, roi: { x: 1, y: 2, width: 3, height: 4 },
  roi_kind: 'offline', frame_width: 1280, frame_height: 720,
  image_url: '/api/analyses/new-id/evidence/frame-id',
};
assert.deepEqual(fromBackendEvidence(evidence), {
  key: 'offlinePeak', label: 'offline waveform peak', elapsedMs: 1500,
  phase: '', areaPx: null, threshold: null, roi: { x: 1, y: 2, width: 3, height: 4 },
  roiKind: 'offline', frameWidth: 1280, frameHeight: 720,
  imageUrl: '/api/analyses/new-id/evidence/frame-id', source: 'backend',
});

try {
  const base = {
    id: 'record-1', durationMs: 5000, videoBlob: new Blob(['video'], { type: 'video/webm' }),
    captureRoi: { roi: { x: .2, y: .1, width: .5, height: .8 }, frame_width: 1280, frame_height: 720 },
    samples: [
      { elapsedMs: 3500, phase: 'maxInhale', areaPx: 1400, roi: { x: 100, y: 120, width: 400, height: 300 } },
      { elapsedMs: 4500, phase: 'maxExhale', areaPx: 600, roi: { x: 100, y: 120, width: 400, height: 300 } },
    ],
    evidence: [{ key: 'local', elapsedMs: 1000 }],
  };
  const mergedEvidence = mergeEvidence(base, [evidence]);
  assert.ok(mergedEvidence.some((item) => item.key === 'maxInhale'));
  assert.ok(mergedEvidence.some((item) => item.key === 'maxExhale'));
  assert.ok(mergedEvidence.some((item) => item.key === 'offlinePeak'));

  let requests = [];
  globalThis.fetch = async (url, options) => {
    requests.push({ url: String(url), method: options?.method });
    return response(200, { status: 'complete', analysis_id: 'new-id', evidence: [evidence] });
  };
  let calls = [];
  const uploaded = await analyzeStoredRecord(base, { updateRecording: updater(base, calls) });
  assert.deepEqual(requests, [{ url: '/api/analyze', method: 'POST' }]);
  assert.equal(uploaded.backendAnalysisId, 'new-id');
  assert.equal(uploaded.backendStatus, 'complete');
  assert.equal(uploaded.evidence.find((item) => item.key === 'offlinePeak')?.source, 'backend');
  assert.ok(uploaded.evidence.some((item) => item.key === 'maxInhale'));
  assert.ok(uploaded.evidence.some((item) => item.key === 'maxExhale'));
  assert.equal(calls.length, 1);

  requests = [];
  calls = [];
  const retryRecord = { ...base, backendAnalysisId: 'existing-id' };
  globalThis.fetch = async (url, options) => {
    requests.push({ url: String(url), method: options?.method });
    return response(200, { status: 'complete', analysis_id: 'existing-id', evidence: [] });
  };
  const retried = await analyzeStoredRecord(retryRecord, { updateRecording: updater(retryRecord, calls) });
  assert.deepEqual(requests, [{ url: '/api/analyses/existing-id/reanalyze', method: 'POST' }]);
  assert.equal(retried.backendAnalysisId, 'existing-id');
  assert.ok(retried.evidence.some((item) => item.key === 'local'));
  assert.ok(retried.evidence.some((item) => item.key === 'maxInhale'));
  assert.ok(retried.evidence.some((item) => item.key === 'maxExhale'));

  requests = [];
  calls = [];
  globalThis.fetch = async (url, options) => {
    requests.push({ url: String(url), method: options?.method });
    if (requests.length === 1) return response(404, { detail: { code: 'analysis_not_found', message: 'Missing analysis' } });
    return response(200, { status: 'complete', analysis_id: 'replacement-id', evidence: [] });
  };
  const rebuilt = await analyzeStoredRecord(retryRecord, { updateRecording: updater(retryRecord, calls) });
  assert.deepEqual(requests, [
    { url: '/api/analyses/existing-id/reanalyze', method: 'POST' },
    { url: '/api/analyze', method: 'POST' },
  ]);
  assert.equal(rebuilt.backendAnalysisId, 'replacement-id');

  requests = [];
  calls = [];
  globalThis.fetch = async () => response(422, { detail: { code: 'position_invalid', message: 'Position quality was not locked', analysis_id: 'failed-id' } });
  await assert.rejects(() => analyzeStoredRecord(base, { updateRecording: updater(base, calls) }), /Position quality was not locked/);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].backendStatus, 'failed');
  assert.equal(calls[0].backendAnalysisId, 'failed-id');
  assert.equal(calls[0].backendError.code, 'position_invalid');
} finally {
  globalThis.fetch = originalFetch;
}

console.log('record analysis controller tests passed');

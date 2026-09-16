import assert from 'node:assert/strict';
import { selectEvidence } from '../src/features/records/evidence.js';

const samples = [
  { elapsedMs: 100, phase: 'tidal', areaPx: 10 },
  { elapsedMs: 200, phase: 'maxInhale', areaPx: 30, roi: { x: 1, y: 2, width: 3, height: 4 }, threshold: 80 },
  { elapsedMs: 250, phase: 'maxInhale', areaPx: 90, roi: { x: 1, y: 2, width: 3, height: 4 }, threshold: 81 },
  { elapsedMs: 300, phase: 'maxInhale', areaPx: 45, roi: { x: 1, y: 2, width: 3, height: 4 }, threshold: 82 },
  { elapsedMs: 350, phase: 'maxInhale', areaPx: 45.2, roi: { x: 1, y: 2, width: 3, height: 4 }, threshold: 83 },
  { elapsedMs: 400, phase: 'maxInhale', areaPx: 45.1, roi: { x: 1, y: 2, width: 3, height: 4 }, threshold: 84 },
  { elapsedMs: 425, phase: 'exhalePrep', areaPx: 48.0 },
  { elapsedMs: 450, phase: 'exhalePrep', areaPx: 60.0 },
  { elapsedMs: 475, phase: 'exhalePrep', areaPx: 57.0 },
  { elapsedMs: 500, phase: 'maxExhale', areaPx: 20 },
  { elapsedMs: 550, phase: 'maxExhale', areaPx: -30 },
  { elapsedMs: 600, phase: 'maxExhale', areaPx: 8.1 },
  { elapsedMs: 650, phase: 'maxExhale', areaPx: 8.0 },
  { elapsedMs: 700, phase: 'maxExhale', areaPx: 8.2 },
];

const realtimeOnly = selectEvidence(samples, {});
assert.equal(realtimeOnly.length, 2, 'only stable Realtime phase candidates should be generated locally');
assert.ok(realtimeOnly.find((item) => item.key === 'maxInhale').elapsedMs >= 400, 'inhale peak search must include the following preparation window');
assert.ok(realtimeOnly.find((item) => item.key === 'maxExhale').elapsedMs >= 600);
assert.ok(realtimeOnly.find((item) => item.key === 'maxInhale').areaPx < 60, 'transient inhale spike must be ignored');
assert.ok(realtimeOnly.find((item) => item.key === 'maxExhale').areaPx > 0, 'transient exhale spike must be ignored');

const legacyWaveform = selectEvidence(samples, { status: 'complete', waveform: [-1, 0, 2], timestamps_ms: [1000, 2000, 3000] });
assert.equal(legacyWaveform.length, 2, 'global offline extrema must not be generated in the frontend');

const persisted = selectEvidence(samples, { evidence: [
  { key: 'offlinePeak', label: 'offline waveform inhale turning point', elapsed_ms: 1200, actual_elapsed_ms: 1230, timestamp_error_ms: 30, roi_kind: 'offline', image_url: '/evidence/peak' },
  { key: 'offlineTrough', label: 'offline waveform exhale turning point', elapsed_ms: 2200, actual_elapsed_ms: 2180, timestamp_error_ms: -20, roi_kind: 'offline', image_url: '/evidence/trough' },
] });
assert.equal(persisted.length, 4);
assert.equal(persisted.find((item) => item.key === 'offlinePeak').actualElapsedMs, 1230);
assert.equal(persisted.find((item) => item.key === 'offlineTrough').timestampErrorMs, -20);

const quality = selectEvidence([...samples, { elapsedMs: 180, phase: 'tidal', areaPx: 20, quality: .9 }], {});
assert.equal(quality.find((item) => item.key === 'bestSignal').elapsedMs, 180);
assert.equal(quality.find((item) => item.key === 'bestSignal').label, 'Highest-quality Realtime frame');
console.log('evidence tests passed');

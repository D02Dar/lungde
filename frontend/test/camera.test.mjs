import assert from 'node:assert/strict';
import { PositionStabilityLatch, evaluatePositionStability } from '../src/features/camera/positionStabilityCheck.js';
import { buildRoiContract, clampBox, deriveChestRoi, deriveOfflineSearchRoi, resizeBoxFromCorner } from '../src/features/camera/calibrationBox.js';
import { evaluatePositionSilhouette } from '../src/features/camera/positionSilhouetteCheck.js';
import { evaluateSignalCalibration } from '../src/features/camera/signalCalibrationCheck.js';
import { CaptureManager } from '../src/features/camera/CaptureManager.js';
import { cloneForStorage, MAX_RECORDINGS } from '../src/features/records/recordingStore.js';

assert.equal(MAX_RECORDINGS, 30);

const latch = new PositionStabilityLatch({ holdMs: 500, releaseMs: 1500, unknownReleaseMs: 2200 });
let now = 1000;
for (let i = 0; i < 7; i += 1) { latch.update('pass', now); now += 100; }
assert.equal(latch.locked, true);
for (let i = 0; i < 4; i += 1) { latch.update('fail', now); now += 100; }
assert.equal(latch.locked, true, 'short failures must not unlock');
for (let i = 0; i < 16; i += 1) { latch.update('fail', now); now += 100; }
assert.equal(latch.locked, false, 'sustained failure must unlock');

const box = clampBox({ x: -.3, y: .9, width: .1, height: .1 });
assert.ok(box.x >= 0 && box.y + box.height <= 1);
assert.ok(box.width >= .34 && box.height >= .38);
const resized = resizeBoxFromCorner({ x: .2, y: .1, width: .5, height: .8 }, 'se', .15, -.2);
assert.ok(Math.abs(resized.width - .65) < 1e-9 && Math.abs(resized.height - .6) < 1e-9);
assert.equal(resized.x, .2);
assert.equal(resized.y, .1);
const minimumResize = resizeBoxFromCorner({ x: .2, y: .1, width: .5, height: .8 }, 'nw', .49, .79);
assert.ok(minimumResize.width >= .34 && minimumResize.height >= .38);
assert.ok(minimumResize.x >= 0 && minimumResize.y >= 0);

const chest = deriveChestRoi({ x: .2, y: .1, width: .5, height: .8 });
assert.ok(Math.abs(chest.x - .2) < 1e-9);
assert.ok(Math.abs(chest.y - .276) < 1e-9);
assert.ok(Math.abs(chest.width - .5) < 1e-9);
assert.ok(Math.abs(chest.height - .44) < 1e-9);
assert.ok(chest.x + chest.width <= 1 && chest.y + chest.height <= 1);
const edgeChest = deriveChestRoi({ x: .7, y: .8, width: .4, height: .5 });
assert.ok(edgeChest.x + edgeChest.width <= 1 && edgeChest.y + edgeChest.height <= 1);
const offline = deriveOfflineSearchRoi({ x: .2, y: .1, width: .5, height: .8 });
assert.ok(offline.x >= .2 && offline.x + offline.width <= .7);
assert.ok(offline.y >= .1 && offline.y + offline.height <= .9);
const contract = buildRoiContract({ x: .2, y: .1, width: .5, height: .8 }, 1280, 720, { contrast: 42, occupancy: .44 });
assert.equal(contract.roi_contract_version, 'went-roi-v2');
assert.equal(contract.roi_profile_id, 'standing-side-upper-body-v1');
assert.deepEqual(contract.operator_roi, contract.roi);
assert.equal(contract.frame_width, 1280);
assert.equal(contract.position_quality.status, 'locked');
assert.ok(contract.realtime_chest_roi.y >= contract.operator_roi.y);
assert.ok(contract.offline_search_roi.x + contract.offline_search_roi.width <= contract.operator_roi.x + contract.operator_roi.width);
assert.ok(contract.offline_search_roi.y + contract.offline_search_roi.height <= contract.operator_roi.y + contract.operator_roi.height);

function silhouetteImage({ width = 80, height = 120, value = 45, background = 220, top = 8, bottom = 112, left = 22, right = 70 } = {}) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const foreground = x >= left && x < right && y >= top && y < bottom;
      const gray = foreground ? value : background;
      const index = (y * width + x) * 4;
      data[index] = gray; data[index + 1] = gray; data[index + 2] = gray; data[index + 3] = 255;
    }
  }
  return { width, height, data };
}
const completeSilhouette = evaluatePositionSilhouette(silhouetteImage());
assert.equal(completeSilhouette.pass, true);
assert.equal(completeSilhouette.polarity, 'dark');
assert.equal(completeSilhouette.bands.length, 4);
assert.ok(completeSilhouette.contrast > 100);
assert.equal(evaluatePositionSilhouette(silhouetteImage({ value: 110, background: 125 })).reason, 'low_contrast');
assert.equal(evaluatePositionSilhouette(silhouetteImage({ top: 0 })).reason, 'head_cropped');
const inverseSilhouette = evaluatePositionSilhouette(silhouetteImage({ value: 225, background: 20 }));
assert.equal(inverseSilhouette.pass, true);
assert.equal(inverseSilhouette.polarity, 'light');
assert.ok(inverseSilhouette.contrast > 100);

const positionBox = { x: .2, y: .1, width: .5, height: .8 };
const lockedBox = { ...positionBox };
const lockedChest = deriveChestRoi(lockedBox);
positionBox.x = .4;
assert.equal(lockedBox.x, .2);
assert.equal(lockedChest.x, .2);

function alignmentSamples(areaValues, roi = { width: 100, height: 100 }) {
  return areaValues.map((areaPx) => ({ areaPx, roi }));
}
assert.equal(evaluatePositionStability(alignmentSamples(Array(9).fill(4000))).reason, 'collecting');
assert.equal(evaluatePositionStability(alignmentSamples(Array(10).fill(0))).reason, 'no_signal');
assert.equal(evaluatePositionStability(alignmentSamples(Array(10).fill(2000))).reason, 'too_far');
assert.equal(evaluatePositionStability(alignmentSamples(Array(10).fill(8000))).reason, 'too_close');
assert.equal(evaluatePositionStability(alignmentSamples([4000, 4600, 3400, 4600, 3400, 4600, 3400, 4600, 3400, 4000])).reason, 'moving');
const stable = evaluatePositionStability(alignmentSamples([4000, 4010, 3990, 4005, 3995, 4008, 3992, 4004, 3996, 4000]));
assert.equal(stable.status, 'pass');
assert.equal(stable.reason, 'ok');
assert.equal(evaluatePositionStability(Array(10).fill({ areaPx: 4000, roi: null })).status, 'unknown');

assert.equal(evaluateSignalCalibration(Array(9).fill({ areaPx: 1000 })).reason, 'insufficient_samples');
assert.equal(evaluateSignalCalibration(Array(10).fill({ areaPx: 0 })).reason, 'no_signal');
const weakCalibration = evaluateSignalCalibration(Array.from({ length: 10 }, (_, index) => ({ areaPx: 1000 + (index % 2) * 10, threshold: 70 + index, polarity: 'light' })));
assert.equal(weakCalibration.weak, true);
assert.equal(weakCalibration.referenceThreshold, 74.5);
assert.equal(weakCalibration.polarity, 'light');
const overexposedLight = evaluateSignalCalibration(Array.from({ length: 10 }, (_, index) => ({ areaPx: 1000 + index * 30, threshold: 160, polarity: 'light', highlightSaturationRatio: .2 })));
assert.equal(overexposedLight.weak, true);
assert.equal(overexposedLight.reason, 'light_subject_saturation');
assert.equal(overexposedLight.lightOverexposed, true);
const saturatedDark = evaluateSignalCalibration(Array.from({ length: 10 }, (_, index) => ({ areaPx: 1000 + index * 30, threshold: 90, polarity: 'dark', highlightSaturationRatio: .2 })));
assert.equal(saturatedDark.weak, false, 'light-shirt saturation policy must not change the dark-clothing path');
assert.equal(evaluateSignalCalibration(Array.from({ length: 10 }, (_, index) => ({ areaPx: 1000 + (index % 2) * 30 }))).weak, false);

const blob = new Blob(['video'], { type: 'video/webm' });
const source = { title: 'Morning run', note: 'dark shirt', box: { x: .2 }, samples: [{ areaPx: 30 }], videoBlob: blob, typed: new Uint8Array([1, 2, 3]) };
const stored = cloneForStorage(source);
assert.notEqual(stored, source);
assert.notEqual(stored.box, source.box);
assert.notEqual(stored.samples, source.samples);
assert.equal(stored.videoBlob, blob, 'Blob should be preserved for IndexedDB');
assert.equal(stored.title, 'Morning run');
assert.equal(stored.note, 'dark shirt');
assert.deepEqual([...stored.typed], [1, 2, 3]);

let stoppedTracks = 0;
const manager = new CaptureManager();
manager.video = { srcObject: { active: true } };
manager.state.stream = { getTracks: () => [{ stop: () => { stoppedTracks += 1; } }, { stop: () => { stoppedTracks += 1; } }] };
manager.state.ready = true;
manager.previewTimer = 123;
manager.state.positionChecking = true;
manager.state.confirming = true;
manager.state.calibrationRunning = true;
manager.stopStream();
assert.equal(stoppedTracks, 2, 'all camera tracks must be stopped');
assert.equal(manager.state.stream, null);
assert.equal(manager.state.ready, false);
assert.equal(manager.video.srcObject, null);
assert.equal(manager.previewTimer, 0, 'camera shutdown must also stop Position sampling');
assert.equal(manager.state.positionChecking, false);
assert.equal(manager.state.confirming, false);
assert.equal(manager.state.calibrationRunning, false);

const savedNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
let resolveCameraRequest;
let cancelledTrackStops = 0;
Object.defineProperty(globalThis, 'navigator', {
  configurable: true,
  value: { mediaDevices: { getUserMedia: () => new Promise((resolve) => { resolveCameraRequest = resolve; }) } },
});
const cancelledManager = new CaptureManager();
const cancelledVideo = { srcObject: null, play: async () => {} };
const pendingStart = cancelledManager.start(cancelledVideo, null);
cancelledManager.stopStream();
resolveCameraRequest({ getTracks: () => [{ stop: () => { cancelledTrackStops += 1; } }] });
assert.equal(await pendingStart, null, 'a camera request resolved after leaving Position must be discarded');
assert.equal(cancelledTrackStops, 1, 'a late media stream must be released immediately');
assert.equal(cancelledVideo.srcObject, null);
if (savedNavigator) Object.defineProperty(globalThis, 'navigator', savedNavigator);
else delete globalThis.navigator;
console.log('camera and storage tests passed');

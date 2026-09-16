<template>
  <main class="app-shell">
    <StageBar :stage="stage" :stages="stages" :mark-locked="boxLocked" :camera-status="cameraStatus" :measurement-status="measurementStatus" :record-count="recordCount" @go="goToStage"/>
    <section v-if="stage === 'guide'" class="guide-layout"><GuidePanel :protocol="protocol" @advance="goToStage('mark')" @open-stage="goToStage" @open-tutorial="measurementTutorialVisible = true"/></section>
    <RecordPage v-else-if="stage === 'record'" :refresh-token="recordsRefreshToken" @open-stage="goToStage" @count="recordCount=$event"/>
    <section v-else :class="stage === 'mark' ? 'mark-layout' : 'measure-layout'">
      <div class="stack">
        <section class="panel camera-panel">
          <div class="panel-head">
            <div>
              <h2>{{ stage === 'mark' ? 'Adjust the frame to fit your upper body' : 'Live measurement view' }}</h2>
              <p>{{ stage === 'mark' ? 'Move the frame and resize it from the corners so your head, chest, and waist fit inside. Keep your back in the green band, then hold still.' : 'The chest measurement area is frozen. Follow the screen and spoken breathing sequence.' }}</p>
            </div>
            <button v-if="stage === 'mark' && camera.ready.value" class="btn btn-quiet" type="button" @click="startCamera">Restart camera</button>
          </div>
          <div class="panel-body camera-panel-body">
            <section class="camera-shell" :class="{ 'camera-shell-empty': !camera.ready.value }">
              <CameraStage
                ref="cameraStage"
                :box="positionBox"
                :camera-ready="camera.ready.value"
                :locked="stage === 'measure' || boxLocked"
                :editable="stage === 'mark' && !boxLocked"
                :phase="stage"
                :chest-roi="chestRoi"
                :directive="stage === 'mark' ? currentDirective : ''"
                :calibrating="calibrationRunning"
                @update:box="updatePositionBox"
                @open-camera="openCameraFromStage"
              />
              <div v-if="stage === 'measure'" class="stage-instruction" :class="`phase-${currentPhase || 'ready'}`">
                <div class="stage-instruction-head">
                  <span class="prompt-chip"><i aria-hidden="true"></i>{{ phaseLabel(currentPhase) }}</span>
                  <b class="phase-timer tnum">{{ running ? `${Math.ceil(phaseRemainingMs / 1000)} s` : 'READY' }}</b>
                </div>
                <strong>{{ activeProtocolStep?.action || 'Ready to measure' }}</strong>
                <p>{{ activeProtocolStep?.detail || 'Review the sequence, then start when you are ready.' }}</p>
                <div v-if="currentPhase === 'tidal' || nextActionPreview" class="stage-instruction-meta">
                  <b v-if="currentPhase === 'tidal'">{{ tidalCycleCount }} stable {{ tidalCycleCount === 1 ? 'cycle' : 'cycles' }}</b>
                  <small v-if="nextActionPreview">Next · {{ nextActionPreview }}</small>
                </div>
              </div>
              <div v-if="running && currentPhase === 'countdown'" class="countdown-veil"><span>Ready</span><b>{{ Math.max(1, Math.ceil(phaseRemainingMs / 1000)) }}</b></div>
            </section>
          </div>
        </section>
        <p v-if="camera.error.value" class="status-banner error">Camera unavailable: {{ camera.error.value }}</p>
        <MetricGrid v-if="stage === 'measure'" :current-signal="latestArea" :elapsed-ms="elapsedMs" :sample-count="samples.length" :phase-text="phaseLabel(currentPhase)"/>
      </div>
      <div class="stack">
        <section v-if="stage === 'mark'" class="panel position-actions">
          <div class="panel-head">
            <div><h2>Find a frame that fits you</h2><p>Stand side-on. Drag inside to move, drag a corner to resize, then stay still until it confirms.</p></div>
            <button class="btn btn-quiet" @click="positionGuideVisible=true"><PhQuestion :size="18"/>View example</button>
          </div>
          <div class="panel-body">
            <div class="control-row">
              <template v-if="camera.ready.value">
                <strong v-if="positionChecking && !boxLocked" class="position-progress">Checking automatically · {{ Math.round(lockProgress * 100) }}%</strong>
                <strong v-else-if="calibrationRunning" class="position-progress">Checking breathing outline…</strong>
                <strong v-else-if="boxLocked" class="position-progress ready">Position ready</strong>
                <button class="btn btn-quiet" @click="resetPosition(); confirmBox()">Reset frame</button>
                <button class="btn btn-primary" :disabled="!boxLocked || calibrationRunning" @click="goToStage('measure')">Continue to Measure</button>
              </template>
            </div>
            <p class="panel-note">The outer frame adapts to your body size. The green chest area follows it at a fixed, versioned proportion so repeated measurements use the same definition.</p>
            <p v-if="weakSignalWarning" class="position-warning">{{ calibrationResult?.reason === 'light_subject_saturation' ? 'The light shirt is overexposed. Reduce direct light or use a mid-tone fitted shirt before measuring.' : 'Breathing outline is weak. Check clothing fit, lighting, and background contrast. You may still continue.' }}</p>
          </div>
        </section>
        <CaptureInspector v-if="captureInspectorAvailable && stage === 'mark'" :manager="captureManager" :camera-ready="camera.ready.value" />
        <template v-if="stage !== 'mark'">
          <RunPanel :protocol="protocol" :phase="currentPhase" :prompt="currentPrompt" :remaining-ms="phaseRemainingMs" :running="running" :camera-ready="camera.ready.value" :completed="completedPhases" :voice-enabled="voiceEnabled" :saving="savingRecord" :save-message="saveMessage" :save-tone="saveTone" @start="startMeasurement" @stop="stopMeasurement({complete:false})" @open-records="goToStage('record')" @update:voice-enabled="setVoiceEnabled"/>
          <ResultsPanel
            :realtime="realtimeResult"
            :waveform="liveWaveform"
            :timestamps="liveTimestamps"
            :phase-windows="livePhaseWindows"
            :record="lastSavedRecord"
          />
        </template>
      </div>
    </section>
    <PositionVisualGuide :visible="positionGuideVisible" @close="positionGuideVisible=false"/>
    <MeasurementTutorial :visible="measurementTutorialVisible" @close="measurementTutorialVisible=false"/>
    <canvas ref="processingCanvas" class="processing-canvas"/>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, toRefs } from 'vue';
import { PhQuestion } from '@phosphor-icons/vue';
import StageBar from './components/StageBar.vue';
import GuidePanel from './components/GuidePanel.vue';
import PositionVisualGuide from './components/PositionVisualGuide.vue';
import MeasurementTutorial from './components/MeasurementTutorial.vue';
import RunPanel from './components/RunPanel.vue';
import MetricGrid from './components/MetricGrid.vue';
import ResultsPanel from './components/ResultsPanel.vue';
import CaptureInspector from './components/CaptureInspector.vue';
import RecordPage from './components/RecordPage.vue';
import CameraStage from './features/camera/CameraStage.vue';
import { CaptureManager, CAPTURE_PREVIEW_FPS } from './features/camera/CaptureManager.js';
import { computeRealtimeMetrics } from './features/realtime/metrics.js';
import { resampleAndFilter } from './features/realtime/filter.js';
import { detectPeaksAndTroughs } from './features/realtime/peaks.js';
import { selectEvidence } from './features/records/evidence.js';
import { cloneForStorage, isStoreSupported, probeRecordStore, putRecording } from './features/records/recordingStore.js';
import { VideoRecorder } from './features/records/videoRecorder.js';
import { AudioGuide } from './features/audio/audioGuide.js';
import { protocol, stages, phaseLabel } from './features/protocol/config.js';

const stage = ref('guide');
const captureInspectorAvailable = import.meta.env.DEV;
const cameraStage = ref(null);
const processingCanvas = ref(null);
const captureManager = new CaptureManager({
  isPositionActive: () => stage.value === 'mark',
  onDirective: (text, key) => {
    if (text && stage.value === 'mark') audio.speak(text, { key: `position-${key}`, minIntervalMs: 3000 });
  },
  onCalibrationComplete: ({ weak }) => {
    saveMessage.value = weak
      ? 'Position locked. Breathing outline is weak, but you may continue.'
      : 'Frame confirmed. You can proceed to Measure.';
    saveTone.value = weak ? 'note' : 'good';
  },
});
const {
  stream,
  ready,
  error: cameraError,
  positionBox,
  lockedBox,
  chestRoi,
  boxLocked,
  confirming,
  positionChecking,
  calibrationRunning,
  calibrationResult,
  weakSignalWarning,
  lockProgress,
  directive: currentDirective,
} = toRefs(captureManager.state);
const camera = { stream, ready, error: cameraError };
const positionGuideVisible = ref(false);
const measurementTutorialVisible = ref(false);
const running = ref(false);
const savingRecord = ref(false);
const saveMessage = ref('');
const saveTone = ref('note');
const currentPhase = ref('');
const currentPrompt = ref('');
const phaseRemainingMs = ref(0);
const completedPhases = ref([]);
const elapsedMs = ref(0);
const samples = ref([]);
const liveWaveform = ref([]);
const liveTimestamps = ref([]);
const livePhaseWindows = ref({});
const realtimeResult = ref(null);
const latestArea = ref(0);
const recordsRefreshToken = ref(0);
const recordCount = ref(0);
const voiceEnabled = ref(readVoiceSetting());

const cameraStatus = computed(() => camera.ready.value
  ? { kind: 'good', text: boxLocked.value ? 'Frame confirmed' : 'Camera ready' }
  : { kind: camera.error.value ? 'critical' : 'muted', text: camera.error.value ? 'Camera unavailable' : 'Waiting for camera' });
const measurementStatus = computed(() => savingRecord.value
  ? { kind: 'warning', text: 'Saving local record' }
  : saveMessage.value
    ? { kind: saveTone.value === 'error' ? 'critical' : 'good', text: saveMessage.value }
    : running.value
      ? { kind: 'good', text: `${phaseLabel(currentPhase.value)} · ${Math.ceil(phaseRemainingMs.value / 1000)} s` }
      : { kind: 'muted', text: stage.value === 'measure' ? 'Ready to measure' : 'Not started' });
const activeProtocolStep = computed(() => protocol.find((step) => step.key === currentPhase.value) || null);
const activeProtocolIndex = computed(() => protocol.findIndex((step) => step.key === currentPhase.value));
const nextActionPreview = computed(() => {
  if (!running.value || phaseRemainingMs.value > 3000 || activeProtocolIndex.value < 0) return '';
  return protocol[activeProtocolIndex.value + 1]?.action || '';
});
const tidalCycleCount = computed(() => {
  if (currentPhase.value !== 'tidal') return 0;
  const tidalSamples = samples.value.filter((sample) => sample.phase === 'tidal');
  if (tidalSamples.length < CAPTURE_PREVIEW_FPS * 2) return 0;
  const filtered = resampleAndFilter(tidalSamples, CAPTURE_PREVIEW_FPS).values;
  if (filtered.length < 3) return 0;
  const spread = Math.max(...filtered) - Math.min(...filtered);
  if (!Number.isFinite(spread) || spread <= 0) return 0;
  const extrema = detectPeaksAndTroughs(filtered, { minDistance: Math.max(2, Math.round(CAPTURE_PREVIEW_FPS * .6)), prominence: spread * .08 });
  return Math.min(extrema.filter((point) => point.type === 'peak').length, extrema.filter((point) => point.type === 'trough').length);
});

const audio = new AudioGuide({ voiceEnabled: () => voiceEnabled.value });
let sampleTimer = 0;
let elapsedTimer = 0;
let stopInFlight = null;
let recorder = new VideoRecorder();
let measurementStartedAt = 0;
let actualPhaseWindows = {};
const lastSavedRecord = ref(null);

function readVoiceSetting() { try { return localStorage.getItem('went-voice-enabled') !== 'false'; } catch { return true; } }
function setVoiceEnabled(value) { voiceEnabled.value = Boolean(value); try { localStorage.setItem('went-voice-enabled', String(voiceEnabled.value)); } catch {} }
function wait(ms) { return new Promise((resolve) => window.setTimeout(resolve, ms)); }
function clearMeasurementTimers() { clearInterval(sampleTimer); clearInterval(elapsedTimer); sampleTimer = 0; elapsedTimer = 0; }

async function goToStage(next) {
  if (next === 'measure' && (!boxLocked.value || !lockedBox.value || !chestRoi.value || calibrationRunning.value)) {
    saveMessage.value = calibrationRunning.value ? 'Wait for the breathing outline check to finish' : 'Confirm the frame on the Position page first';
    saveTone.value = 'error'; stage.value = 'mark'; return;
  }
  if (running.value && next !== 'measure') await stopMeasurement({ complete: false });
  if (next !== 'mark') {
    captureManager.stopPositionPreview();
    captureManager.setDirective('');
  }
  if (next !== 'mark' && next !== 'measure') captureManager.stopStream();
  stage.value = next;
  if (next === 'record') recordsRefreshToken.value += 1;
}

async function startCamera() {
  await nextTick();
  audio.initialise();
  try {
    await captureManager.start(cameraStage.value?.video, processingCanvas.value);
  } catch {}
}

async function openCameraFromStage() {
  if (stage.value === 'measure') await goToStage('mark');
  await startCamera();
}

function updatePositionBox(box) {
  captureManager.updatePositionBox(box);
}

function confirmBox() {
  audio.initialise();
  captureManager.confirmPosition();
}

function resetPosition() {
  captureManager.resetPosition();
  saveMessage.value = '';
}

async function startMeasurement() {
  if (!camera.ready.value || !lockedBox.value || !chestRoi.value || running.value || savingRecord.value) return;
  if (!isStoreSupported()) { saveMessage.value = 'This browser does not support local records'; saveTone.value = 'error'; return; }
  try { await probeRecordStore(); } catch (error) { saveMessage.value = `Cannot write to the local record store: ${error.message}`; saveTone.value = 'error'; return; }
  audio.initialise(); audio.cancel(); samples.value = []; liveWaveform.value = []; liveTimestamps.value = []; livePhaseWindows.value = {}; realtimeResult.value = null; latestArea.value = 0; completedPhases.value = [];
  currentPhase.value = ''; currentPrompt.value = ''; phaseRemainingMs.value = 0; elapsedMs.value = 0;
  actualPhaseWindows = {};
  lastSavedRecord.value = null;
  recorder = new VideoRecorder(); recorder.start(camera.stream.value); measurementStartedAt = performance.now(); running.value = true; saveMessage.value = '';
  clearMeasurementTimers(); sampleTimer = window.setInterval(sampleFrame, 1000 / CAPTURE_PREVIEW_FPS); elapsedTimer = window.setInterval(() => { elapsedMs.value = performance.now() - measurementStartedAt; }, 80);
  await runProtocol();
}

async function runProtocol() {
  for (const step of protocol) {
    if (!running.value) return;
    await enterPhase(step);
  }
  if (running.value) {
    audio.speak('Measurement complete. Breathe normally.', { key: 'complete', minIntervalMs: 1000 });
    await stopMeasurement({ complete: true });
  }
}
async function enterPhase(step) {
  const phaseStartMs = performance.now() - measurementStartedAt;
  actualPhaseWindows[step.key] = [phaseStartMs / 1000, phaseStartMs / 1000];
  livePhaseWindows.value = { ...actualPhaseWindows };
  currentPhase.value = step.key; currentPrompt.value = step.prompt; phaseRemainingMs.value = step.seconds * 1000;
  if (step.beep !== false) audio.beep(step.key === 'countdown' ? 880 : 1046, 180);
  if (step.voice) audio.speak(step.voice, { key: `phase-${step.key}`, minIntervalMs: 1000 });
  const startedAt = performance.now();
  const endsAt = startedAt + step.seconds * 1000;
  const followupCues = Array.isArray(step.followupCues) ? step.followupCues : [];
  let followupIndex = 0;
  while (running.value && performance.now() < endsAt) {
    const elapsedSeconds = (performance.now() - startedAt) / 1000;
    const cue = followupCues[followupIndex];
    if (cue && elapsedSeconds >= cue.atSeconds) {
      audio.speak(cue.voice, { key: `phase-${step.key}-followup-${followupIndex}`, minIntervalMs: 600 });
      followupIndex += 1;
    }
    phaseRemainingMs.value = Math.max(0, endsAt - performance.now());
    actualPhaseWindows[step.key][1] = (performance.now() - measurementStartedAt) / 1000;
    livePhaseWindows.value = { ...actualPhaseWindows };
    await wait(100);
  }
  actualPhaseWindows[step.key][1] = (performance.now() - measurementStartedAt) / 1000;
  livePhaseWindows.value = { ...actualPhaseWindows };
  phaseRemainingMs.value = 0; if (running.value) completedPhases.value.push(step.key);
}

function sampleFrame() {
  const sample = captureManager.captureMeasurementSample(currentPhase.value, performance.now() - measurementStartedAt);
  if (!sample) return;
  samples.value.push(sample); latestArea.value = sample.areaPx;
  const filtered = resampleAndFilter(samples.value, CAPTURE_PREVIEW_FPS);
  liveWaveform.value = filtered.values;
  liveTimestamps.value = filtered.timestampsMs;
}

async function stopMeasurement({ complete }) { if (stopInFlight) return stopInFlight; if (!running.value) return; stopInFlight = finishMeasurement({ complete }); try { await stopInFlight; } finally { stopInFlight = null; } }
async function finishMeasurement(options) {
  try { return await finalizeMeasurementRecord(options); }
  finally { captureManager.stopStream(); }
}
async function finalizeMeasurementRecord({ complete }) {
  if (actualPhaseWindows[currentPhase.value]) actualPhaseWindows[currentPhase.value][1] = (performance.now() - measurementStartedAt) / 1000;
  running.value = false; clearMeasurementTimers(); audio.cancel(); currentPhase.value = ''; currentPrompt.value = '';
  const capture = await recorder.stop();
  const filtered = resampleAndFilter(samples.value, CAPTURE_PREVIEW_FPS);
  liveWaveform.value = filtered.values;
  liveTimestamps.value = filtered.timestampsMs;
  livePhaseWindows.value = { ...actualPhaseWindows };
  const tidalMetricSamples = filtered.values.map((value, index) => ({ value, elapsedMs: filtered.timestampsMs[index], phase: phaseAt(filtered.timestampsMs[index]) }));
  const rawMetricSamples = filtered.rawValues.map((areaPx, index) => ({ areaPx, elapsedMs: filtered.timestampsMs[index], phase: phaseAt(filtered.timestampsMs[index]), roi: samples.value[0]?.roi || null }));
  realtimeResult.value = computeRealtimeMetrics(tidalMetricSamples, filtered.fps, { rawSamples: rawMetricSamples, sourceSamples: samples.value, phaseWindows: actualPhaseWindows, roiPixels: samples.value[0]?.roi ? samples.value[0].roi.width * samples.value[0].roi.height : null });
  if (!samples.value.length) { saveMessage.value = 'Not enough samples were collected, so no record was created'; saveTone.value = 'error'; return; }
  savingRecord.value = true; saveMessage.value = 'Saving to local records…'; saveTone.value = 'note';
  try {
    const frameWidth = cameraStage.value?.video?.videoWidth || 0;
    const frameHeight = cameraStage.value?.video?.videoHeight || 0;
    const localEvidence = selectEvidence(cloneForStorage(samples.value), realtimeResult.value || {}).map((item) => ({
      ...item,
      frameWidth,
      frameHeight,
      roiKind: 'realtime',
    }));

    // Build the ROI contract for the recording, including phase windows and evidence frames
    const metadata = captureManager.buildRoiContract(
      { ...actualPhaseWindows },
      localEvidence.map((frame) => ({
        key: frame.key,
        label: frame.label,
        elapsed_ms: frame.elapsedMs,
        phase: frame.phase || '',
        area_px: frame.areaPx,
        threshold: frame.threshold,
        roi_kind: 'realtime',
      })),
    );
    if (!metadata) throw new Error('The locked Position ROI contract is unavailable');
    metadata.calibration = cloneForStorage(calibrationResult.value);
    metadata.camera_settings = camera.stream.value?.getVideoTracks?.()[0]?.getSettings?.() || {};
    metadata.realtime_samples = samples.value
      .filter((sample) => Number.isFinite(sample?.elapsedMs) && Number.isFinite(sample?.areaPx))
      .map((sample) => ({
        elapsed_ms: sample.elapsedMs,
        value: sample.areaPx,
        quality: Number.isFinite(sample.quality) ? sample.quality : null,
        phase: sample.phase || phaseAt(sample.elapsedMs),
        signal_method: sample.signalMethod || null,
        saturation_ratio: Number.isFinite(sample.saturationRatio) ? sample.saturationRatio : null,
        highlight_saturation_ratio: Number.isFinite(sample.highlightSaturationRatio) ? sample.highlightSaturationRatio : null,
      }));
      // Save the recording to the local store, including video, metadata, samples, and evidence
    const record = await putRecording({ videoBlob: capture?.blob || null, videoMimeType: capture?.mimeType || '',
    videoRequestedMimeType: capture?.requestedMimeType || '',
    videoChunkCount: capture?.chunkCount || 0, videoSize: capture?.size ||
    0, videoBitsPerSecond: capture?.videoBitsPerSecond || null, durationMs: capture?.durationMs ||
   elapsedMs.value, captureRoi: metadata,
   samples: cloneForStorage(samples.value),

   realtime: cloneForStorage(realtimeResult.value), offline: null, evidence: localEvidence, cancelled: !complete, algorithmVersion: 'polarity-contour-amplitude-v4' });
    lastSavedRecord.value = record;
    recordsRefreshToken.value += 1; recordCount.value += 1;
    saveMessage.value = capture ? 'Measurement saved to local records' : 'Area record saved; video was unavailable in this browser'; saveTone.value = 'good';
  } catch (error) { saveMessage.value = `Could not save record: ${error.message}`; saveTone.value = 'error'; } finally { savingRecord.value = false; }
}

function phaseAt(timeMs) { return Object.entries(actualPhaseWindows).find(([, range]) => timeMs >= range[0] * 1000 && timeMs < range[1] * 1000)?.[0] || ''; }

onBeforeUnmount(() => { captureManager.dispose(); clearMeasurementTimers(); audio.cancel(); recorder.cancel(); });
</script>

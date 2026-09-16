<template>
  <section class="panel capture-inspector">
    <div class="panel-head">
      <div>
        <p class="eyebrow">DEVELOPMENT TOOL</p>
        <h2>Capture inspector</h2>
        <p>Inspect the exact chest crop used by the Realtime path. Nothing shown here is saved.</p>
      </div>
      <button class="btn btn-quiet" type="button" :disabled="!cameraReady" @click="open = !open">
        {{ open ? 'Close inspector' : 'Inspect capture' }}
      </button>
    </div>
    <div v-if="open" class="panel-body">
      <p v-if="!cameraReady" class="panel-note">Open the camera to inspect a frame.</p>
      <template v-else-if="snapshot">
        <div class="capture-inspector-grid">
          <figure><canvas ref="sourceCanvas"></canvas><figcaption>Chest ROI · RGB</figcaption></figure>
          <figure><canvas ref="grayCanvas"></canvas><figcaption>Grayscale</figcaption></figure>
          <figure><canvas ref="maskCanvas"></canvas><figcaption>Final subject mask</figcaption></figure>
        </div>
        <dl class="capture-inspector-metrics">
          <div><dt>ROI pixels</dt><dd>{{ snapshot.roi.width }} × {{ snapshot.roi.height }}</dd></div>
          <div><dt>Threshold</dt><dd>{{ snapshot.threshold }} · {{ snapshot.thresholdSource }}</dd></div>
          <div><dt>Polarity</dt><dd>{{ snapshot.polarity }}</dd></div>
          <div><dt>Signal method</dt><dd>{{ snapshot.signal.method }}</dd></div>
          <div><dt>Measured area</dt><dd>{{ snapshot.signal.value.toFixed(0) }} px²</dd></div>
          <div><dt>Position check</dt><dd>{{ manager.state.positionQuality?.status || 'collecting' }}</dd></div>
        </dl>
      </template>
      <p v-else class="panel-note">Waiting for a decodable camera frame…</p>
    </div>
  </section>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, shallowRef, watch } from 'vue';
import { deriveChestRoi } from '../features/camera/calibrationBox.js';
import { toGrayscale } from '../features/realtime/grayscale.js';
import { measureSubjectSignal, otsuThreshold, segmentSubjectMask } from '../features/realtime/otsu.js';

const props = defineProps({ manager: { type: Object, required: true }, cameraReady: Boolean });
const open = ref(false);
const snapshot = shallowRef(null);
const sourceCanvas = ref(null);
const grayCanvas = ref(null);
const maskCanvas = ref(null);
let timer = 0;

function takeSnapshot() {
  if (!open.value || !props.cameraReady) return;
  const normalizedRoi = props.manager.state.chestRoi || deriveChestRoi(props.manager.state.positionBox);
  const captured = props.manager.captureImage(normalizedRoi);
  if (!captured) return;
  const grayscale = toGrayscale(captured.imageData);
  const otsu = otsuThreshold(grayscale);
  const reference = props.manager.state.calibrationResult?.referenceThreshold;
  const threshold = Number.isFinite(reference) ? Math.round(reference) : otsu;
  const thresholdSource = Number.isFinite(reference) ? 'locked calibration' : 'current Otsu';
  const polarity = props.manager.state.subjectPolarity || 'dark';
  const mask = segmentSubjectMask(grayscale, threshold, polarity, captured.imageData.width, captured.imageData.height);
  const signal = measureSubjectSignal(grayscale, threshold, polarity, captured.imageData.width, captured.imageData.height);
  snapshot.value = { ...captured, grayscale, mask, threshold, thresholdSource, polarity, signal };
  void nextTick(renderSnapshot);
}

function renderSnapshot() {
  if (!snapshot.value) return;
  paintSource(sourceCanvas.value, snapshot.value.imageData);
  paintMono(grayCanvas.value, snapshot.value.grayscale, snapshot.value.imageData.width, snapshot.value.imageData.height);
  paintMono(maskCanvas.value, snapshot.value.mask, snapshot.value.imageData.width, snapshot.value.imageData.height);
}

function paintSource(canvas, imageData) {
  if (!canvas || !imageData) return;
  canvas.width = imageData.width;
  canvas.height = imageData.height;
  canvas.getContext('2d').putImageData(imageData, 0, 0);
}

function paintMono(canvas, values, width, height) {
  if (!canvas || !values?.length) return;
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d');
  const image = context.createImageData(width, height);
  for (let index = 0; index < values.length; index += 1) {
    const offset = index * 4;
    image.data[offset] = values[index];
    image.data[offset + 1] = values[index];
    image.data[offset + 2] = values[index];
    image.data[offset + 3] = 255;
  }
  context.putImageData(image, 0, 0);
}

function updatePolling() {
  globalThis.clearInterval(timer);
  timer = 0;
  if (!open.value || !props.cameraReady) {
    if (!props.cameraReady) snapshot.value = null;
    return;
  }
  takeSnapshot();
  timer = globalThis.setInterval(takeSnapshot, 500);
}

watch(() => [open.value, props.cameraReady], updatePolling);
onBeforeUnmount(() => globalThis.clearInterval(timer));
</script>

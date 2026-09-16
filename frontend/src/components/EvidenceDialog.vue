<template>
  <Teleport to="body">
    <div v-if="open" class="evidence-dialog-backdrop" @mousedown.self="close">
      <section ref="dialog" class="evidence-dialog" role="dialog" aria-modal="true" aria-labelledby="evidence-dialog-title" @keydown="onKeydown">
        <header class="panel-head">
          <div>
            <h2 id="evidence-dialog-title">Evidence frames</h2>
            <p>Realtime and offline evidence are shown together at their decoded video timestamps.</p>
          </div>
          <button ref="closeButton" class="guide-close" type="button" aria-label="Close evidence dialog" @click="close"><PhX :size="21" weight="bold" /></button>
        </header>
        <div class="panel-body evidence-dialog-body">
          <div class="evidence-toolbar">
            <div><b>{{ frames.length }} evidence frames</b><span>Click a frame to seek the saved video.</span></div>
            <label class="evidence-overlay-toggle"><input v-model="showRoi" type="checkbox" /> Show saved ROI boxes</label>
          </div>
          <div v-if="loading" class="empty-copy">Generating missing evidence previews from the saved video…</div>
          <div v-else-if="!frames.length" class="empty-copy">This record has no usable evidence frames.</div>
          <div v-else class="evidence-grid">
            <button v-for="frame in frames" :key="`${frame.key}-${frame.elapsedMs}`" class="evidence-frame" type="button" @click="select(frame)">
              <span class="evidence-visual">
                <img :src="frame.src" :alt="frame.label" />
                <span v-if="showRoi && roiStyle(frame)" :class="['evidence-roi-box', `roi-${frame.roiKind || 'realtime'}`]" :style="roiStyle(frame)">
                  <em>{{ roiLabel(frame) }}</em>
                </span>
              </span>
              <span class="evidence-frame-title"><b>{{ frame.label }}</b><em>{{ time(displayTime(frame)) }}</em></span>
              <small>{{ frame.source === 'backend' ? 'Persisted offline frame' : 'Realtime candidate frame' }}<template v-if="frame.phase"> · {{ phaseLabel(frame.phase) }}</template></small>
              <small v-if="Number.isFinite(frame.actualElapsedMs)">Requested {{ time(frame.elapsedMs) }} · decoded {{ time(frame.actualElapsedMs) }} · error {{ signedMs(frame.timestampErrorMs) }}</small>
              <small v-if="details(frame)">{{ details(frame) }}</small>
            </button>
          </div>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { PhX } from '@phosphor-icons/vue';

const props = defineProps({ open: Boolean, videoUrl: String, evidence: { type: Array, default: () => [] } });
const emit = defineEmits(['close', 'seek']);
const dialog = ref(null);
const closeButton = ref(null);
const loading = ref(false);
const frames = ref([]);
const showRoi = ref(true);
let generation = 0;
let previousFocus = null;
let objectUrls = [];

watch(() => [props.open, props.videoUrl, props.evidence], async ([open]) => {
  if (!open) { clearFrames(); previousFocus?.focus?.(); previousFocus = null; return; }
  previousFocus = document.activeElement;
  await nextTick();
  closeButton.value?.focus();
  await generate();
}, { deep: true });

onBeforeUnmount(clearFrames);

async function generate() {
  const token = ++generation;
  clearFrames(false);
  const output = [];
  const missing = [];
  for (const item of props.evidence || []) {
    if (item?.imageUrl) output.push({ ...item, src: item.imageUrl, source: 'backend' });
    else if (Number.isFinite(item?.elapsedMs)) missing.push(item);
  }
  frames.value = sortFrames(output);
  if (!missing.length || !props.videoUrl) return;

  loading.value = true;
  const video = document.createElement('video');
  video.preload = 'auto';
  video.muted = true;
  video.playsInline = true;
  video.src = props.videoUrl;
  try {
    await event(video, 'loadedmetadata');
    for (const item of missing) {
      if (token !== generation) return;
      video.currentTime = Math.max(0, Math.min(Number.isFinite(video.duration) ? video.duration : item.elapsedMs / 1000, item.elapsedMs / 1000));
      await event(video, 'seeked');
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext('2d').drawImage(video, 0, 0);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/webp', .9));
      if (!blob) continue;
      const src = URL.createObjectURL(blob);
      objectUrls.push(src);
      output.push({
        ...item,
        src,
        source: 'local',
        frameWidth: item.frameWidth || video.videoWidth,
        frameHeight: item.frameHeight || video.videoHeight,
        roiKind: item.roiKind || 'realtime',
      });
      if (token === generation) frames.value = sortFrames(output);
    }
  } finally {
    video.removeAttribute('src');
    video.load();
    if (token === generation) loading.value = false;
  }
}
function sortFrames(items) { return [...items].sort((a, b) => Number(a.elapsedMs || 0) - Number(b.elapsedMs || 0)); }
function clearFrames(increment = true) {
  if (increment) generation += 1;
  objectUrls.forEach((url) => URL.revokeObjectURL(url));
  objectUrls = [];
  frames.value = [];
  loading.value = false;
}
function roiStyle(frame) {
  const roi = frame?.roi;
  const width = Number(frame?.frameWidth);
  const height = Number(frame?.frameHeight);
  if (!roi || !width || !height || !Number.isFinite(Number(roi.x)) || !Number.isFinite(Number(roi.y))) return null;
  return {
    left: `${Math.max(0, Math.min(100, Number(roi.x) / width * 100))}%`,
    top: `${Math.max(0, Math.min(100, Number(roi.y) / height * 100))}%`,
    width: `${Math.max(0, Math.min(100, Number(roi.width) / width * 100))}%`,
    height: `${Math.max(0, Math.min(100, Number(roi.height) / height * 100))}%`,
  };
}
function roiLabel(frame) { return frame.roiKind === 'offline' ? 'offline ROI' : 'ONLINE ROI'; }
function displayTime(frame) { return Number.isFinite(frame.actualElapsedMs) ? frame.actualElapsedMs : frame.elapsedMs; }
function signedMs(value) {
  if (!Number.isFinite(value)) return '--';
  return `${value >= 0 ? '+' : ''}${Math.round(value)} ms`;
}
function event(target, name) { return new Promise((resolve, reject) => { target.addEventListener(name, resolve, { once: true }); target.addEventListener('error', reject, { once: true }); }); }
function close() { emit('close'); }
function select(frame) { emit('seek', frame.elapsedMs); close(); }
function details(frame) {
  const pieces = [];
  if (Number.isFinite(frame.areaPx)) pieces.push(`Area ${Math.round(frame.areaPx)} px`);
  if (Number.isFinite(frame.threshold)) pieces.push(`Threshold ${Math.round(frame.threshold)}`);
  return pieces.join(' · ');
}
function phaseLabel(phase) { return ({ tidal: 'Normal breathing', maxInhale: 'Maximum inhale', maxExhale: 'Maximum exhale', countdown: 'Ready' })[phase] || phase; }
function time(ms) {
  const seconds = Math.max(0, Number(ms || 0) / 1000);
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}.${Math.floor((seconds % 1) * 10)}`;
}
function onKeydown(event) {
  if (event.key === 'Escape') { event.preventDefault(); close(); return; }
  if (event.key !== 'Tab') return;
  const focusable = [...dialog.value.querySelectorAll('button:not(:disabled), [href], input:not(:disabled), [tabindex]:not([tabindex="-1"])')];
  if (!focusable.length) return;
  const first = focusable[0], last = focusable.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}
</script>

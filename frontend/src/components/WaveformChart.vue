<template>
  <div class="annotated-waveform">
    <canvas ref="canvas" class="waveform" :aria-label="label"></canvas>
    <div class="waveform-key" aria-hidden="true">
      <span v-if="hasVcWindows" class="key-peak">VC inhale</span>
      <span v-if="hasVcWindows" class="key-trough">VC exhale</span>
      <span v-if="interval" class="key-confidence">Legacy RR interval</span>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = defineProps({
  values: { type: Array, default: () => [] },
  timestamps: { type: Array, default: () => [] },
  interval: { type: Object, default: null },
  phaseWindows: { type: Object, default: () => ({}) },
  label: { type: String, default: 'Respiratory waveform' },
  accent: { type: String, default: '#2f7f63' },
  landmarks: { type: Object, default: () => ({}) },
});
const canvas = ref(null);
const hasVcWindows = computed(() => Array.isArray(props.phaseWindows?.maxInhale) && Array.isArray(props.phaseWindows?.maxExhale));
let observer;
const padding = { left: 46, right: 16, top: 28, bottom: 28 };

function timestamps() {
  if (props.timestamps.length === props.values.length) return props.timestamps;
  return props.values.map((_, index) => index * 1000);
}
function timeExtent(times) { return Math.max(1, Number(times.at(-1) || 0)); }
function xForMs(ms, width, duration) { return padding.left + Math.max(0, Math.min(1, ms / duration)) * (width - padding.left - padding.right); }
function yForValue(value, height, min, span) { return padding.top + (1 - (value - min) / span) * (height - padding.top - padding.bottom); }

function draw() {
  const el = canvas.value;
  if (!el) return;
  const rect = el.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  el.width = Math.max(1, Math.round(rect.width * dpr));
  el.height = Math.max(1, Math.round(rect.height * dpr));
  const ctx = el.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, rect.width, rect.height);
  const times = timestamps();
  const duration = timeExtent(times);
  const plotWidth = rect.width - padding.left - padding.right;
  const plotHeight = rect.height - padding.top - padding.bottom;

  drawPhaseBands(ctx, rect.width, plotHeight, duration);
  drawGrid(ctx, rect.width, rect.height, duration);
  drawConfidence(ctx, rect.width, plotHeight, duration, times);
  if (props.values.length < 2) return;

  const finite = props.values.filter(Number.isFinite);
  if (finite.length < 2) return;
  const min = Math.min(...finite), max = Math.max(...finite), span = max - min || 1;
  ctx.save();
  ctx.beginPath();
  ctx.rect(padding.left, padding.top, plotWidth, plotHeight);
  ctx.clip();
  ctx.strokeStyle = props.accent;
  ctx.lineWidth = 2.25;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.beginPath();
  props.values.forEach((value, index) => {
    if (!Number.isFinite(value)) return;
    const x = xForMs(times[index] || 0, rect.width, duration);
    const y = yForValue(value, rect.height, min, span);
    index ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
  ctx.restore();

  const peakIndex = nearestLandmarkIndex(times, props.landmarks?.maxInhale?.ms) ?? phaseExtremumIndex(times, ['maxInhale', 'exhalePrep'], 'high');
  const troughIndex = nearestLandmarkIndex(times, props.landmarks?.maxExhale?.ms) ?? phaseExtremumIndex(times, ['maxExhale'], 'low');
  if (peakIndex >= 0) drawMarker(ctx, 'VC inhale', peakIndex, props.values[peakIndex], '#c8322f', times, duration, rect.width, rect.height, min, span, -10);
  if (troughIndex >= 0) drawMarker(ctx, 'VC exhale', troughIndex, props.values[troughIndex], '#2878b8', times, duration, rect.width, rect.height, min, span, 16);

  ctx.fillStyle = '#66737d';
  ctx.font = '10px ui-monospace, monospace';
  ctx.textAlign = 'right';
  ctx.fillText(max.toFixed(2), padding.left - 6, padding.top + 4);
  ctx.fillText(min.toFixed(2), padding.left - 6, rect.height - padding.bottom);
}

function drawGrid(ctx, width, height, duration) {
  const plotBottom = height - padding.bottom;
  ctx.strokeStyle = 'rgba(103,120,126,.18)';
  ctx.lineWidth = 1;
  for (let row = 0; row <= 4; row += 1) {
    const y = padding.top + row * (plotBottom - padding.top) / 4;
    ctx.beginPath(); ctx.moveTo(padding.left, y); ctx.lineTo(width - padding.right, y); ctx.stroke();
  }
  const ticks = Math.max(2, Math.min(6, Math.round(duration / 5000)));
  ctx.fillStyle = '#66737d';
  ctx.font = '10px ui-monospace, monospace';
  ctx.textAlign = 'center';
  for (let tick = 0; tick <= ticks; tick += 1) {
    const ms = duration * tick / ticks;
    const x = xForMs(ms, width, duration);
    ctx.beginPath(); ctx.moveTo(x, padding.top); ctx.lineTo(x, plotBottom); ctx.stroke();
    ctx.fillText(`${(ms / 1000).toFixed(0)}s`, x, height - 8);
  }
}

function drawPhaseBands(ctx, width, plotHeight, duration) {
  const colors = { countdown: 'rgba(105,113,120,.06)', tidal: 'rgba(45,126,184,.08)', maxInhale: 'rgba(47,127,99,.10)', maxExhale: 'rgba(200,50,47,.08)' };
  const labels = { countdown: 'Ready', tidal: 'Normal breathing', maxInhale: 'Maximum inhale', maxExhale: 'Maximum exhale' };
  for (const [key, range] of Object.entries(props.phaseWindows || {})) {
    if (!Array.isArray(range) || range.length < 2) continue;
    const left = xForMs(range[0] * 1000, width, duration);
    const right = xForMs(range[1] * 1000, width, duration);
    ctx.fillStyle = colors[key] || 'rgba(80,90,100,.05)';
    ctx.fillRect(left, padding.top, Math.max(1, right - left), plotHeight);
    ctx.fillStyle = '#52616b';
    ctx.font = '600 10px system-ui, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(labels[key] || key, left + 5, 14);
  }
}

function drawConfidence(ctx, width, plotHeight, duration, times) {
  const interval = props.interval;
  if (!interval) return;
  const startMs = Number.isFinite(interval.start_ms) ? interval.start_ms : times[interval.start_index];
  const endMs = Number.isFinite(interval.end_ms) ? interval.end_ms : times[interval.end_index];
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) return;
  const left = xForMs(startMs, width, duration), right = xForMs(endMs, width, duration);
  ctx.fillStyle = 'rgba(28,122,82,.14)';
  ctx.fillRect(left, padding.top, Math.max(2, right - left), plotHeight);
  ctx.strokeStyle = '#16704a';
  ctx.lineWidth = 2;
  ctx.setLineDash([5, 3]);
  ctx.strokeRect(left, padding.top, Math.max(2, right - left), plotHeight);
  ctx.setLineDash([]);
  ctx.fillStyle = '#125b3d';
  ctx.font = '700 10px system-ui, sans-serif';
  ctx.textAlign = 'left';
  const cycles = Number.isFinite(interval.cycle_count) ? ` · ${interval.cycle_count} cycles` : '';
  ctx.fillText(`LEGACY RR INTERVAL${cycles}`, Math.min(left + 6, width - 150), padding.top + 14);
}

function nearestLandmarkIndex(times, ms) {
  if (!Number.isFinite(Number(ms)) || !times.length) return null;
  let best = 0;
  for (let i = 1; i < times.length; i += 1) if (Math.abs(times[i] - ms) < Math.abs(times[best] - ms)) best = i;
  return best;
}

function phaseExtremumIndex(times, phaseKeys, direction) {
  const ranges = phaseKeys.map((key) => props.phaseWindows?.[key]).filter((range) => Array.isArray(range) && range.length >= 2);
  if (!ranges.length) return -1;
  const candidates = props.values
    .map((value, index) => ({ value, index, ms: Number(times[index]) }))
    .filter((point) => Number.isFinite(point.value) && ranges.some((range) => point.ms >= range[0] * 1000 && point.ms < range[1] * 1000));
  if (!candidates.length) return -1;
  const smoothed = candidates.map((point, index) => {
    const left = Math.max(0, index - 2), right = Math.min(candidates.length, index + 3);
    const local = candidates.slice(left, right).map((item) => item.value);
    return { ...point, smooth: local.reduce((sum, value) => sum + value, 0) / local.length };
  });
  return smoothed.reduce((best, point) => (
    direction === 'high'
      ? (point.smooth > best.smooth ? point : best)
      : (point.smooth < best.smooth ? point : best)
  )).index;
}

function drawMarker(ctx, label, index, value, color, times, duration, width, height, min, span, offsetY) {
  if (index < 0) return;
  const x = xForMs(times[index] || 0, width, duration);
  const y = yForValue(value, height, min, span);
  ctx.fillStyle = color;
  ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
  ctx.font = '700 10px system-ui, sans-serif';
  ctx.textAlign = x > width - 70 ? 'right' : 'left';
  ctx.fillText(`${label} ${(times[index] / 1000).toFixed(1)}s`, x + (ctx.textAlign === 'right' ? -6 : 6), Math.max(20, Math.min(height - 8, y + offsetY)));
}

watch(() => [props.values, props.timestamps, props.interval, props.phaseWindows, props.landmarks], draw, { deep: true });
onMounted(() => { observer = new ResizeObserver(draw); observer.observe(canvas.value); draw(); });
onBeforeUnmount(() => observer?.disconnect());
</script>

<template>
  <section class="panel record-waveform-panel">
    <div class="panel-head">
      <div>
        <h2>Respiratory waveform review</h2>
        <p>Click to seek video.</p>
      </div>
      <span class="trace-badge">ALIGNED REVIEW</span>
    </div>
    <div class="panel-body">
      <div class="trace-display-control">
        <label>Trace display
          <select v-model="traceMode">
            <option value="processed">Processed and aligned</option>
            <option value="raw">Raw captured values</option>
          </select>
        </label>
        <p v-if="traceMode === 'raw'" :class="{ warning: !hasOfflineRaw }">{{ rawAvailabilityText }}</p>
      </div>
      <div ref="frame" class="record-waveform-frame" @click="seek" @mousemove="hover" @mouseleave="clearHover">
        <canvas ref="canvas" class="record-waveform-canvas" aria-label="Primary respiratory waveform with Realtime and offline comparison signals"></canvas>
        <div v-if="hoverInfo" class="record-waveform-tooltip" :style="tooltipStyle">
          <b>{{ timeLabel(hoverInfo.ms) }}</b>
          <span v-if="Number.isFinite(hoverInfo.primary)">Primary processed {{ signed(hoverInfo.primary) }}</span>
          <span v-if="Number.isFinite(hoverInfo.realtime)">Realtime {{ traceMode }} {{ signed(hoverInfo.realtime) }}</span>
          <span v-if="Number.isFinite(hoverInfo.offline)">Offline {{ traceMode }} {{ signed(hoverInfo.offline) }}</span>
        </div>
      </div>
      <div class="record-waveform-key" aria-hidden="true">
        <span v-if="hasPrimary" class="key-primary">Primary · processed</span>
        <span v-if="realtimeSeries().length" class="key-realtime">Realtime · {{ traceMode }}</span>
        <span v-if="offlineSeries().length" class="key-offline">Offline · {{ traceMode }}</span>
        <span v-if="offline?.confidence_interval" class="key-confidence">Legacy RR interval</span>
        <span class="key-inhale">Maximum inhale</span>
        <span class="key-exhale">Maximum exhale</span>
        <span class="key-playhead">Video playhead</span>
      </div>
      <p v-if="offline?.comparison && traceMode === 'processed'" class="waveform-agreement-note">
        Agreement {{ percent(offline.comparison.correlation) }} · delay {{ signedMs(offline.comparison.alignment_lag_ms) }} · uncalibrated agreement score {{ percent(offline.comparison.confidence) }}
      </p>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { resampleAndFilter } from '../features/realtime/filter.js';

const props = defineProps({
  samples: { type: Array, default: () => [] },
  offline: { type: Object, default: null },
  phaseWindows: { type: Object, default: () => ({}) },
  evidence: { type: Array, default: () => [] },
  playheadMs: { type: Number, default: 0 },
});
const emit = defineEmits(['seek']);
const frame = ref(null);
const canvas = ref(null);
const hoverInfo = ref(null);
const hoverX = ref(0);
const traceMode = ref('processed');
let observer;
const padding = { left: 58, right: 18, top: 34, bottom: 38 };
const colors = { primary: '#4058b8', realtime: '#c8322f', offline: '#00866a', grid: '#d9ddd9', ink: '#56636e' };
const hasRealtimeRaw = computed(() => props.samples.some((sample) => Number.isFinite(sample?.elapsedMs) && Number.isFinite(sample?.areaPx)));
const hasOfflineRaw = computed(() => Boolean(
  props.offline?.source_waveform?.length
  && props.offline?.raw_timestamps_ms?.length === props.offline.source_waveform.length,
));
const hasPrimary = computed(() => traceMode.value === 'processed' && Boolean(props.offline?.comparison?.primary_waveform?.length));
const rawAvailabilityText = computed(() => {
  const realtime = hasRealtimeRaw.value ? 'Realtime raw available.' : 'Realtime raw unavailable.';
  const offline = hasOfflineRaw.value ? 'Offline raw available.' : 'Offline raw unavailable for this legacy or incomplete analysis; no processed fallback is being shown.';
  return `${realtime} ${offline}`;
});
const tooltipStyle = computed(() => ({ left: `${Math.max(8, Math.min((frame.value?.clientWidth || 0) - 174, hoverX.value + 12))}px` }));

function realtimeSeries() {
  if (traceMode.value === 'raw') {
    return normalize(props.samples
      .filter((sample) => Number.isFinite(sample?.elapsedMs) && Number.isFinite(sample?.areaPx))
      .map((sample) => ({ ms: Number(sample.elapsedMs), value: Number(sample.areaPx) }))
      .sort((a, b) => a.ms - b.ms));
  }
  if (props.samples.length) {
    const clean = resampleAndFilter(props.samples, 15);
    return normalize(clean.timestampsMs.map((ms, i) => ({ ms, value: clean.values[i] })));
  }
  const comparison = props.offline?.comparison;
  if (comparison?.realtime_waveform?.length && comparison.timestamps_ms?.length === comparison.realtime_waveform.length) {
    return comparison.timestamps_ms.map((ms, index) => ({ ms: Number(ms), value: Number(comparison.realtime_waveform[index]) })).filter(validPoint);
  }
  const points = props.samples
    .filter((sample) => Number.isFinite(sample?.elapsedMs) && Number.isFinite(sample?.areaPx))
    .map((sample) => ({ ms: Number(sample.elapsedMs), value: Number(sample.areaPx) }))
    .sort((a, b) => a.ms - b.ms);
  return normalize(points);
}

function offlineSeries() {
  if (traceMode.value === 'raw') {
    if (!hasOfflineRaw.value) return [];
    return normalize(props.offline.raw_timestamps_ms.map((ms, index) => ({ ms, value: props.offline.source_waveform[index] })).filter(validPoint));
  }
  const comparison = props.offline?.comparison;
  if (comparison?.offline_waveform?.length && comparison.timestamps_ms?.length === comparison.offline_waveform.length) {
    return comparison.timestamps_ms.map((ms, index) => ({ ms: Number(ms), value: Number(comparison.offline_waveform[index]) })).filter(validPoint);
  }
  const values = props.offline?.waveform;
  const timestamps = props.offline?.timestamps_ms;
  if (!Array.isArray(values) || !Array.isArray(timestamps) || values.length !== timestamps.length) return [];
  return normalize(timestamps.map((ms, index) => ({ ms: Number(ms), value: Number(values[index]) })).filter(validPoint));
}

function primarySeries() {
  if (traceMode.value === 'raw') return [];
  const comparison = props.offline?.comparison;
  if (!comparison?.primary_waveform?.length || comparison.timestamps_ms?.length !== comparison.primary_waveform.length) return [];
  return comparison.timestamps_ms.map((ms, index) => ({ ms: Number(ms), value: Number(comparison.primary_waveform[index]) })).filter(validPoint);
}

function validPoint(point) { return Number.isFinite(point.ms) && Number.isFinite(point.value); }
function normalize(points) {
  if (!points.length) return [];
  const values = points.map((point) => point.value).sort((a, b) => a - b);
  const median = quantile(values, 0.5);
  const deviations = values.map((value) => Math.abs(value - median)).sort((a, b) => a - b);
  const scale = quantile(deviations, 0.5) * 1.4826 || standardDeviation(values) || 1;
  return points.map((point) => ({ ...point, value: (point.value - median) / scale }));
}
function quantile(values, ratio) {
  if (!values.length) return 0;
  const position = (values.length - 1) * ratio;
  const lower = Math.floor(position), upper = Math.ceil(position), mix = position - lower;
  return values[lower] * (1 - mix) + values[upper] * mix;
}
function standardDeviation(values) {
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  return Math.sqrt(values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length);
}

function durationMs() {
  const candidates = [Number(props.playheadMs || 0)];
  for (const series of [realtimeSeries(), offlineSeries(), primarySeries()]) if (series.length) candidates.push(series.at(-1).ms);
  for (const window of Object.values(props.phaseWindows || {})) if (Array.isArray(window)) candidates.push(Number(window[1]) * 1000);
  for (const item of props.evidence || []) candidates.push(Number(item.actualElapsedMs ?? item.elapsedMs ?? 0));
  return Math.max(1000, ...candidates.filter(Number.isFinite));
}

function draw() {
  const element = canvas.value, host = frame.value;
  if (!element || !host) return;
  const width = Math.max(320, host.clientWidth), height = 390, ratio = window.devicePixelRatio || 1;
  element.width = Math.round(width * ratio); element.height = Math.round(height * ratio);
  element.style.width = `${width}px`; element.style.height = `${height}px`;
  const ctx = element.getContext('2d'); ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  const duration = durationMs();
  const plot = { left: padding.left, right: width - padding.right, top: padding.top, bottom: height - padding.bottom };
  drawPhases(ctx, width, plot, duration);
  drawGrid(ctx, width, plot, duration);
  drawConfidence(ctx, width, plot, duration);
  const realtime = realtimeSeries(), offline = offlineSeries(), primary = primarySeries();
  const allValues = [...realtime, ...offline, ...primary].map((point) => point.value);
  const extent = Math.max(1.5, ...allValues.map(Math.abs)) * 1.05;
  if (!realtime.length && !offline.length) drawEmpty(ctx, plot);
  drawLine(ctx, realtime, plot, duration, extent, colors.realtime, 1.5, []);
  drawLine(ctx, offline, plot, duration, extent, colors.offline, 1.5, [7, 5]);
  drawLine(ctx, primary, plot, duration, extent, colors.primary, 2.75, []);
  drawEvidence(ctx, width, plot, duration, extent, { realtime, offline, primary });
  drawPlayhead(ctx, width, plot, duration);
  if (hoverInfo.value) drawCrosshair(ctx, width, plot, duration, hoverInfo.value.ms);
  drawAxisLabels(ctx, width, plot, duration, extent);
}

function drawPhases(ctx, width, plot, duration) {
  const fills = { countdown: 'rgba(96,108,118,.06)', tidal: 'rgba(40,120,184,.07)', maxInhale: 'rgba(22,112,74,.08)', maxExhale: 'rgba(200,50,47,.07)' };
  const labels = { countdown: 'Ready', tidal: 'Normal breathing', maxInhale: 'Maximum inhale', maxExhale: 'Maximum exhale' };
  for (const [phase, window] of Object.entries(props.phaseWindows || {})) {
    if (!Array.isArray(window)) continue;
    const left = xForMs(Number(window[0]) * 1000, width, duration), right = xForMs(Number(window[1]) * 1000, width, duration);
    ctx.fillStyle = fills[phase] || 'rgba(96,108,118,.05)'; ctx.fillRect(left, plot.top, Math.max(1, right - left), plot.bottom - plot.top);
    ctx.fillStyle = '#66737d'; ctx.font = '700 9px system-ui, sans-serif'; ctx.textAlign = 'left';
    ctx.fillText(labels[phase] || phase, left + 5, plot.top - 10);
  }
}

function drawGrid(ctx, width, plot, duration) {
  ctx.strokeStyle = colors.grid; ctx.lineWidth = 1; ctx.setLineDash([]);
  for (let row = 0; row <= 4; row += 1) {
    const y = plot.top + (plot.bottom - plot.top) * row / 4;
    ctx.beginPath(); ctx.moveTo(plot.left, y); ctx.lineTo(plot.right, y); ctx.stroke();
  }
  const step = duration > 60000 ? 10000 : duration > 30000 ? 5000 : 2500;
  for (let ms = 0; ms <= duration; ms += step) {
    const x = xForMs(ms, width, duration); ctx.beginPath(); ctx.moveTo(x, plot.top); ctx.lineTo(x, plot.bottom); ctx.stroke();
  }
}

function drawLine(ctx, series, plot, duration, extent, color, lineWidth, dash) {
  if (!series.length) return;
  ctx.save(); ctx.beginPath(); ctx.rect(plot.left, plot.top, plot.right - plot.left, plot.bottom - plot.top); ctx.clip();
  ctx.strokeStyle = color; ctx.lineWidth = lineWidth; ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.setLineDash(dash);
  ctx.beginPath();
  series.forEach((point, index) => {
    const x = xForMs(point.ms, plot.right + padding.right, duration), y = yForValue(point.value, plot, extent);
    index ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke(); ctx.restore(); ctx.setLineDash([]);
}

function drawConfidence(ctx, width, plot, duration) {
  const interval = props.offline?.confidence_interval;
  if (!interval || !Number.isFinite(Number(interval.start_ms)) || !Number.isFinite(Number(interval.end_ms))) return;
  const left = xForMs(Number(interval.start_ms), width, duration), right = xForMs(Number(interval.end_ms), width, duration);
  ctx.fillStyle = 'rgba(28,122,82,.10)'; ctx.fillRect(left, plot.top, Math.max(2, right - left), plot.bottom - plot.top);
  ctx.strokeStyle = '#16704a'; ctx.lineWidth = 1.25; ctx.setLineDash([6, 4]); ctx.strokeRect(left, plot.top, Math.max(2, right - left), plot.bottom - plot.top); ctx.setLineDash([]);
}

function drawEvidence(ctx, width, plot, duration, extent, series) {
  const colorsByKey = { maxInhale: '#16704a', maxExhale: '#c8322f', bestSignal: '#8a5a00', offlinePeak: '#6542a6', offlineTrough: '#2878b8' };
  const labels = { maxInhale: 'Maximum inhale peak', maxExhale: 'Maximum exhale trough', bestSignal: 'Best Realtime', offlinePeak: 'offline inhale peak', offlineTrough: 'offline exhale trough' };
  for (const item of props.evidence || []) {
    const ms = Number(item.actualElapsedMs ?? item.elapsedMs);
    if (!Number.isFinite(ms)) continue;
    const source = item.roiKind === 'offline' ? series.offline : (series.primary.length ? series.primary : series.realtime);
    if (!source.length) continue;
    const point = nearest(source, ms);
    const x = xForMs(ms, width, duration), y = point ? yForValue(point.value, plot, extent) : plot.top + 16;
    const color = colorsByKey[item.key] || '#596773';
    ctx.fillStyle = color; ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.fillStyle = '#34414c'; ctx.font = '700 9px system-ui, sans-serif'; ctx.textAlign = x > width - 105 ? 'right' : 'left';
    ctx.fillText(labels[item.key] || item.label || 'Evidence', x + (ctx.textAlign === 'right' ? -7 : 7), Math.max(plot.top + 12, y - 8));
  }
}

function drawPlayhead(ctx, width, plot, duration) {
  if (!Number.isFinite(props.playheadMs)) return;
  const x = xForMs(props.playheadMs, width, duration);
  ctx.strokeStyle = '#17212b'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x, plot.top); ctx.lineTo(x, plot.bottom); ctx.stroke();
}
function drawCrosshair(ctx, width, plot, duration, ms) {
  const x = xForMs(ms, width, duration);
  ctx.strokeStyle = 'rgba(23,33,43,.5)'; ctx.lineWidth = 1; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(x, plot.top); ctx.lineTo(x, plot.bottom); ctx.stroke(); ctx.setLineDash([]);
}
function drawAxisLabels(ctx, width, plot, duration, extent) {
  ctx.fillStyle = colors.ink; ctx.font = '9px ui-monospace, monospace';
  ctx.textAlign = 'right'; ctx.fillText(`+${extent.toFixed(1)} z*`, plot.left - 7, plot.top + 4); ctx.fillText('0', plot.left - 7, (plot.top + plot.bottom) / 2 + 3); ctx.fillText(`-${extent.toFixed(1)} z*`, plot.left - 7, plot.bottom);
  const step = duration > 60000 ? 10000 : duration > 30000 ? 5000 : 2500;
  ctx.textAlign = 'center';
  for (let ms = 0; ms <= duration; ms += step) ctx.fillText(timeLabel(ms), xForMs(ms, width, duration), plot.bottom + 18);
}
function drawEmpty(ctx, plot) { ctx.fillStyle = '#7b858d'; ctx.font = '11px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.fillText('No usable waveform is available', (plot.left + plot.right) / 2, (plot.top + plot.bottom) / 2); }

function hover(event) {
  const rect = frame.value.getBoundingClientRect(), width = rect.width, duration = durationMs();
  const x = Math.max(padding.left, Math.min(width - padding.right, event.clientX - rect.left));
  const ms = (x - padding.left) / Math.max(1, width - padding.left - padding.right) * duration;
  hoverX.value = x;
  hoverInfo.value = {
    ms,
    primary: nearest(primarySeries(), ms)?.value,
    realtime: nearest(realtimeSeries(), ms)?.value,
    offline: nearest(offlineSeries(), ms)?.value,
  };
  draw();
}
function clearHover() { hoverInfo.value = null; draw(); }
function seek(event) {
  const rect = frame.value.getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left - padding.left) / Math.max(1, rect.width - padding.left - padding.right)));
  emit('seek', ratio * durationMs());
}
function nearest(series, ms) {
  if (!series.length) return null;
  let best = series[0], error = Math.abs(best.ms - ms);
  for (const point of series) { const next = Math.abs(point.ms - ms); if (next < error) { best = point; error = next; } }
  return best;
}
function xForMs(ms, width, duration) { return padding.left + Math.max(0, Math.min(1, ms / duration)) * (width - padding.left - padding.right); }
function yForValue(value, plot, extent) { return plot.top + (1 - value / extent) * (plot.bottom - plot.top) / 2; }
function timeLabel(ms) { const seconds = Math.max(0, Number(ms || 0) / 1000); return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}.${Math.floor((seconds % 1) * 10)}`; }
function percent(value) { return Number.isFinite(value) ? `${Math.round(value * 100)}%` : '--'; }
function signed(value) { return `${value >= 0 ? '+' : ''}${Number(value).toFixed(2)} scaled`; }
function signedMs(value) { return Number.isFinite(value) ? `${value >= 0 ? '+' : ''}${Math.round(value)} ms` : '--'; }

watch(() => [props.samples, props.offline, props.phaseWindows, props.evidence, props.playheadMs, traceMode.value], draw, { deep: true });
onMounted(() => { observer = new ResizeObserver(draw); observer.observe(frame.value); draw(); });
onBeforeUnmount(() => observer?.disconnect());
</script>

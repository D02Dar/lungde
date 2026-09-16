<template>
  <section class="panel">
    <div class="panel-head"><div><h2>Record details</h2><p>Realtime capture, offline processing, and Primary status.</p></div></div>
    <div class="panel-body">
      <form class="record-annotation" @submit.prevent="saveMetadata">
        <label><span>Record name</span><input v-model="title" maxlength="60" placeholder="Optional name, for example Morning test 1" /></label>
        <label><span>Notes</span><textarea v-model="note" maxlength="500" rows="3" placeholder="Posture, clothing, breathing condition, or anything useful for comparison"></textarea></label>
        <div><small>{{ note.length }}/500 · saved only on this device</small><button class="btn btn-quiet" type="submit" :disabled="!metadataChanged">Save name &amp; notes</button></div>
      </form>
      <div class="result-rows">
        <div><span>Realtime VcA</span><b>{{ metric(liveValue('vcPx'),record?.realtime?.diagnostic?.vcPx,1,'px') }}</b></div>
        <div><span>Realtime VtA</span><b>{{ metric(liveValue('vtPx'),record?.realtime?.diagnostic?.vtPx,1,'px') }}</b></div>
        <div><span>Realtime VcA/VtA</span><b>{{ metric(liveValue('ratio'),record?.realtime?.diagnostic?.ratio,2) }}</b></div>
        <div><span>Realtime RR</span><b>{{ number(liveValue('rrBpm'),1) }} bpm</b></div>
        <div><span>offline Vc</span><b>{{ metric(record?.offline?.vc_px,record?.offline?.diagnostic?.vc_px,1,'px') }}</b></div>
        <div><span>offline Vt</span><b>{{ metric(record?.offline?.vt_px,record?.offline?.diagnostic?.vt_px,1,'px') }}</b></div>
        <div><span>offline Vc/Vt</span><b>{{ metric(record?.offline?.ratio,record?.offline?.diagnostic?.ratio,2) }}</b></div>
        <div><span>Offline quality checks</span><b>{{ qualityLabel }}</b></div>
        <div><span>offline RR</span><b>{{ number(record?.offline?.rr_bpm,1) }} bpm</b></div>
        <div><span>Legacy RR interval</span><b>{{ interval(record?.offline?.confidence_interval) }}</b></div>
        <div><span>offline storage</span><b>{{ backendLabel }}</b></div>
        <div><span>Recorded file</span><b>{{ fileLabel }}</b></div>
      </div>
      <p v-if="record?.realtime && !record.realtime.valid" class="panel-note">Some realtime quality checks failed. Invalid formal values are withheld; provisional estimates below are for debugging only.</p>
      <p v-else-if="record?.realtime?.qualityStatus === 'usable_with_caution'" class="panel-note">Realtime values are available, but one or more non-fatal variability checks need caution.</p>
      <details v-if="record?.realtime?.diagnostic || record?.offline?.diagnostic" class="diagnostic-estimate"><summary>Provisional estimates and quality reasons — not validated results</summary><pre>{{ diagnosticText }}</pre></details>
      <p v-if="record?.offline && !record.offline.quality?.status" class="panel-note">Legacy analysis: quality has not been checked by the new amplitude-preserving pipeline. Run offline analysis again to update it.</p>
      <p class="panel-note">Area and RGB amplitudes are image proxies, not liters and not a substitute for clinical pulmonary testing.</p>
      <div class="panel-actions">
        <button class="btn btn-quiet" :disabled="!record?.videoBlob" @click="$emit('download-video')">Download video</button>
        <button class="btn btn-danger" @click="$emit('delete')">Delete record</button>
      </div>
      <p v-if="record?.videoBlob && !longEnough" class="panel-note">offline analysis requires at least 3 seconds of video. This clip is {{ clipSeconds }} seconds.</p>
      <p v-if="decodeSummary" class="panel-note">{{ decodeSummary }}</p>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
const props = defineProps({ record: Object });
const emit = defineEmits(['delete', 'download-video', 'save-metadata']);
const title = ref('');
const note = ref('');
watch(() => [props.record?.id, props.record?.title, props.record?.note], () => {
  title.value = props.record?.title || '';
  note.value = props.record?.note || '';
}, { immediate: true });
const metadataChanged = computed(() => title.value.trim() !== (props.record?.title || '') || note.value.trim() !== (props.record?.note || ''));
const longEnough = computed(() => (props.record?.durationMs || 0) >= 3000);
const clipSeconds = computed(() => ((props.record?.durationMs || 0) / 1000).toFixed(1));
const qualityLabel = computed(() => ({checks_passed:'Checks passed · not an accuracy %',usable_with_caution:'Usable with caution',review_required:'Review required'}[props.record?.offline?.quality?.status] || (props.record?.offline ? 'Legacy · rerun analysis' : '--')));
const diagnosticText = computed(() => JSON.stringify({realtime:props.record?.realtime?.diagnostic,offline:props.record?.offline?.diagnostic},null,2));
const backendLabel = computed(() => {
  if (!props.record?.backendAnalysisId) return 'Not uploaded';
  const labels = { complete: 'Saved · complete', failed: 'Saved · failed', processing: 'Saved · processing' };
  return labels[props.record?.backendStatus] || 'Saved';
});
const fileLabel = computed(() => {
  const size = Number(props.record?.videoSize || props.record?.videoBlob?.size || 0);
  const mib = size ? `${(size / 1048576).toFixed(1)} MB` : 'size unknown';
  return `${clipSeconds.value} s · ${mib}`;
});
const decodeSummary = computed(() => {
  const diagnostic = props.record?.backendError?.diagnostics || props.record?.offline?.diagnostics;
  const direct = diagnostic?.direct || diagnostic;
  if (!direct || !Number.isFinite(direct.decoded_frame_count)) return '';
  const fps = Number.isFinite(direct.fps) ? `${direct.fps.toFixed(1)} fps` : 'unknown fps';
  const duration = Number.isFinite(direct.decoded_duration_seconds) ? `${direct.decoded_duration_seconds.toFixed(1)} s decoded` : 'duration unavailable';
  return `Offline decoded ${direct.width || '?'} × ${direct.height || '?'}: ${direct.decoded_frame_count} frames at ${fps} (${duration}). Capture: ${props.record?.captureRoi?.frame_width || '?'} × ${props.record?.captureRoi?.frame_height || '?'}.`;
});
function liveValue(key) {
  return props.record?.realtime?.[key];
}
function number(value, digits) { return Number.isFinite(value) ? value.toFixed(digits) : '--'; }
function metric(formal, diagnostic, digits, unit='') {
  if (Number.isFinite(formal)) return `${formal.toFixed(digits)}${unit ? ` ${unit}` : ''}`;
  if (Number.isFinite(diagnostic)) return `~${diagnostic.toFixed(digits)}${unit ? ` ${unit}` : ''} · estimate`;
  return 'Not reliable';
}
function percent(value) { return Number.isFinite(value) ? `${Math.round(value * 100)}%` : '--'; }
function interval(value) { return value ? `${(value.start_ms / 1000).toFixed(2)}–${(value.end_ms / 1000).toFixed(2)} s` : '--'; }
function saveMetadata() { if (metadataChanged.value) emit('save-metadata', { title: title.value.trim(), note: note.value.trim() }); }
</script>
<style scoped>
pre { white-space:pre-wrap; overflow-wrap:anywhere; max-height:340px; overflow:auto; font-size:12px; padding:12px; } summary { cursor:pointer; padding:12px 0; }
.record-annotation { display:grid; gap:10px; margin-bottom:16px; padding:14px; border:1px solid var(--rule); border-radius:var(--radius); background:var(--paper-raised); }
.record-annotation label { display:grid; gap:5px; color:var(--ink-soft); font-size:12px; font-weight:600; }
.record-annotation input,.record-annotation textarea { width:100%; padding:9px 10px; border:1px solid var(--rule-strong); border-radius:var(--radius); background:var(--panel); color:var(--ink); font:inherit; font-weight:400; resize:vertical; }
.record-annotation > div { display:flex; align-items:center; justify-content:space-between; gap:10px; }
.record-annotation small { color:var(--ink-faint); }
</style>

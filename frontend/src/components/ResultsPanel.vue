<template>
  <section class="panel results-panel">
    <div class="panel-head"><div><h2>Realtime analysis result</h2>
      <p>The Realtime area signal is calculated during capture. Run offline analysis later from the saved Record to generate a Primary waveform.</p></div></div>
    <div class="panel-body">
      <section class="result-section">
        <header><span class="trace-badge">ONLINE PATH</span><b>Realtime area analysis</b></header>
        <div v-if="realtime && !realtime.valid" class="invalid-measurement" role="status">
          <strong>Measurement invalid</strong>
          <p>{{ invalidMessage(realtime.invalidReasons) }}</p>
          <small>{{ invalidGuidance(realtime.invalidReasons) }}</small>
        </div>
        <div v-else-if="realtime?.qualityStatus === 'usable_with_caution'" class="invalid-measurement caution-measurement" role="status">
          <strong>Usable with caution</strong>
          <p>The Vc/Vt values are available, but normal-breathing amplitudes or baseline varied more than preferred.</p>
          <small>Keep the result for comparison and repeat once with steadier natural breathing.</small>
        </div>
        <div class="result-rows" :class="{ muted: realtime && !realtime.valid }">
          <div><span>Vital area VcA</span><b>{{ number(realtime?.vcPx, 1) }} px</b></div>
          <div><span>Tidal area VtA</span><b>{{ number(realtime?.vtPx, 1) }} px</b></div>
          <div><span>VcA / VtA</span><b>{{ number(realtime?.ratio, 2) }}</b></div>
          <div><span>Respiratory rate</span><b>{{ number(realtime?.rrBpm, 1) }} bpm</b></div>
        </div>
        <section v-if="realtime && !realtime.valid && realtime.diagnostic" class="diagnostic-estimate">
          <div class="diagnostic-heading"><div><span>Diagnostic estimate</span><b>Values before quality rejection</b></div><small>Not a valid measurement result</small></div>
          <div class="result-rows">
            <div><span>Max inhale–exhale VcA</span><b>{{ number(realtime.diagnostic.vcPx, 1) }} px</b></div>
            <div><span>Normal-breath VtA</span><b>{{ number(realtime.diagnostic.vtPx, 1) }} px</b></div>
            <div><span>Diagnostic VcA/VtA</span><b>{{ number(realtime.diagnostic.ratio, 2) }}</b></div>
            <div><span>Estimated RR</span><b>{{ number(diagnosticRrBpm, 1) }} bpm</b></div>
            <div><span>Tidal cycles found</span><b>{{ integer(realtime.diagnostic.tidalCycles) }}</b></div>
            <div><span>Inhale / exhale levels</span><b>{{ levelPair }}</b></div>
          </div>
        </section>
        <WaveformChart
          :values="waveform"
          :timestamps="timestamps"
          :phase-windows="phaseWindows"
          :landmarks="realtimeLandmarks"
          label="Realtime area waveform with measured phase timing"
        />
        <AnalysisExport v-if="record" :record="record" />
        <p class="panel-note">After the measurement is saved, open Records to run or retry offline analysis and review the Primary waveform with persisted evidence.</p>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';
import WaveformChart from './WaveformChart.vue';
import AnalysisExport from './AnalysisExport.vue';
const props = defineProps({
  realtime: Object,
  waveform: { type: Array, default: () => [] },
  timestamps: { type: Array, default: () => [] },
  phaseWindows: { type: Object, default: () => ({}) },
  record: Object,
});
const realtimeLandmarks = computed(() => ({
  maxInhale: Number.isFinite(props.realtime?.diagnostic?.inhaleMs) ? { ms: props.realtime.diagnostic.inhaleMs } : null,
  maxExhale: Number.isFinite(props.realtime?.diagnostic?.exhaleMs) ? { ms: props.realtime.diagnostic.exhaleMs } : null,
}));
const diagnosticRrBpm = computed(() => Number.isFinite(props.realtime?.diagnostic?.rrHz) ? props.realtime.diagnostic.rrHz * 60 : null);
const levelPair = computed(() => {
  const inhale = props.realtime?.diagnostic?.inhaleLevel;
  const exhale = props.realtime?.diagnostic?.exhaleLevel;
  return Number.isFinite(inhale) && Number.isFinite(exhale) ? `${inhale.toFixed(0)} / ${exhale.toFixed(0)} px` : '--';
});
function number(value, digits) { return Number.isFinite(value) ? value.toFixed(digits) : '--'; }
function integer(value) { return Number.isFinite(value) ? String(Math.round(value)) : '--'; }
function invalidMessage(reasons = []) {
  if (reasons.includes('area_exceeds_roi')) return 'The calculated area exceeded the physical ROI limit. The result was rejected.';
  if (reasons.includes('insufficient_tidal_cycles')) return 'Not enough stable normal-breathing cycles were detected.';
  if (reasons.includes('vital_not_greater_than_tidal')) return 'Maximum inhale and exhale were not clearly separated from normal breathing.';
  if (reasons.includes('severely_inconsistent_tidal_amplitudes')) return 'Normal-breathing amplitudes varied too much to form a reliable Vt baseline.';
  if (reasons.some(reason => reason.startsWith('incomplete_'))) return 'One or more required phases contain too few samples or a long frame gap.';
  if (reasons.includes('invalid_vital_area')) return 'A usable maximum inhale-to-exhale area change was not detected.';
  return 'The breathing signal did not meet the minimum quality checks.';
}
function invalidGuidance(reasons = []) {
  if (reasons.includes('vital_not_greater_than_tidal')) return 'Keep normal breathing natural. Follow the full inhale/exhale cues without leaning or moving your shoulders or hips; do not deliberately shrink normal breaths to increase the ratio.';
  if (reasons.includes('insufficient_tidal_cycles')) return 'Stay still during normal breathing and avoid deliberately deep breaths before the maximum phases.';
  if (reasons.includes('severely_inconsistent_tidal_amplitudes')) return 'Repeat with natural, unforced breaths while keeping your hips, shoulders and clothing edge still.';
  if (reasons.some(reason => reason.startsWith('incomplete_'))) return 'Improve lighting, close heavy apps, and keep this page active so the camera can maintain its frame rate.';
  if (reasons.includes('area_exceeds_roi')) return 'Return to Position and make sure the full chest and waist silhouette remains inside the upper-body box.';
  return 'Review the waveform and evidence, then repeat with a steady side-on posture and clear silhouette.';
}
</script>

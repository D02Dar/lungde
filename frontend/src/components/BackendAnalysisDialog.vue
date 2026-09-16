<template>
  <Teleport to="body">
    <div v-if="open" class="evidence-dialog-backdrop" @mousedown.self="close">
      <section ref="dialog" class="evidence-dialog backend-analysis-dialog" role="dialog" aria-modal="true" aria-labelledby="backend-dialog-title" @keydown="onKeydown">
        <header class="panel-head">
          <div><p class="eyebrow">offline PATH</p><h2 id="backend-dialog-title">offline analysis</h2><p>Analyze the saved video, align it with the Realtime signal, and review the Primary result without leaving Records.</p></div>
          <button ref="closeButton" class="guide-close" type="button" aria-label="Close offline analysis" @click="close"><PhX :size="21" weight="bold" /></button>
        </header>
        <div class="panel-body evidence-dialog-body">
          <div v-if="loading" class="analysis-loading"><span></span><p>Decoding full-resolution frames, extracting the silhouette, preserving amplitude, checking Vc/Vt, and saving evidence…</p></div>

          <template v-else>
            <section class="backend-dialog-status">
              <div><span>Server record</span><b>{{ shortId }}</b></div>
              <div><span>Status</span><b>{{ statusLabel }}</b></div>
              <div><span>ROI source</span><b>{{ result?.roi_source || roiContractLabel }}</b></div>
              <div><span>Algorithm</span><b>{{ result?.algorithm_version || '--' }}</b></div>
            </section>

            <div v-if="!result" class="backend-run-card">
              <strong>{{ error ? 'Analysis did not complete' : 'Ready for offline analysis' }}</strong>
              <p v-if="error">{{ error }}</p>
              <p v-else-if="isLegacy">This older record has no locked ROI v2 contract. offline analysis will run in compatibility mode and label the result accordingly.</p>
              <p v-else>offline analysis will use the Position-locked ROI, align texture motion with the saved Realtime samples, and persist key evidence frames.</p>
              <button class="btn btn-primary" type="button" :disabled="!canAnalyze" @click="$emit('analyze')">{{ retryLabel }}</button>
            </div>

            <template v-else>
              <section class="backend-dialog-section">
                <div class="backend-section-heading"><h3>Computed result</h3><button class="btn btn-quiet" type="button" :disabled="!canAnalyze" @click="$emit('analyze')">Retry analysis</button></div>
                <div class="result-rows">
                  <div><span>Vital proxy Vc</span><b>{{ number(result.vc_px, 2) }} px</b></div>
                  <div><span>Tidal proxy Vt</span><b>{{ number(result.vt_px, 2) }} px</b></div>
                  <div><span>Vc / Vt</span><b>{{ number(result.ratio, 2) }}</b></div>
                  <div><span>Quality checks</span><b>{{ qualityLabel }}</b></div>
                  <div><span>Respiratory rate</span><b>{{ number(result.rr_bpm, 1) }} bpm</b></div>
                  <div><span>Legacy RR interval</span><b>{{ interval(result.confidence_interval) }}</b></div>
                  <div><span>Saved evidence</span><b>{{ result.evidence?.length || record?.evidence?.filter(item => item.source === 'backend').length || 0 }}</b></div>
                  <div><span>ROI contract</span><b>{{ roiContractLabel }}</b></div>
                  <div><span>Search ROI</span><b>{{ roiText(result.diagnostic?.search_roi) }}</b></div>
                  <div><span>Measured ROI</span><b>{{ roiText(result.roi || result.diagnostic?.analysis_roi) }}</b></div>
                  <div><span>Spatial selection</span><b>{{ result.diagnostic?.row_selection_method || '--' }}</b></div>
                </div>
                <div v-if="result.comparison" class="result-rows primary-result-rows">
                  <div><span>Agreement score (uncalibrated)</span><b>{{ percent(result.comparison.confidence) }}</b></div>
                  <div><span>Realtime / offline agreement</span><b>{{ percent(result.comparison.correlation) }}</b></div>
                  <div><span>Alignment delay</span><b>{{ signedMs(result.comparison.alignment_lag_ms) }}</b></div>
                  <div><span>Signal direction</span><b>{{ result.comparison.alignment_sign === -1 ? 'offline inverted' : 'Aligned' }}</b></div>
                  <div><span>Realtime weight</span><b>{{ percent(result.comparison.realtime_weight) }}</b></div>
                  <div><span>offline weight</span><b>{{ percent(result.comparison.offline_weight) }}</b></div>
                </div>
                <WaveformChart
                  :values="result.comparison?.primary_waveform || result.waveform || []"
                  :timestamps="result.comparison?.timestamps_ms || result.timestamps_ms || []"
                  :interval="result.confidence_interval"
                  :phase-windows="record?.captureRoi?.phase_windows || {}"
                  :landmarks="result.diagnostic?.landmarks || {}"
                  label="Offline amplitude-preserving respiratory waveform"
                />
              </section>

              <section v-if="result.quality" class="backend-dialog-section">
                <h3>Signal quality</h3>
                <dl class="quality-list">
                  <div><dt>SNR</dt><dd>{{ number(result.quality.snr, 3) }}</dd></div>
                  <div><dt>Periodicity</dt><dd>{{ number(result.quality.periodicity, 3) }}</dd></div>
                  <div><dt>ROI source</dt><dd>{{ result.roi_source }}</dd></div>
                  <div><dt>Valid frames</dt><dd>{{ percent(result.quality.valid_frame_ratio) }}</dd></div>
                  <div><dt>Texture coverage</dt><dd>{{ percent(result.quality.texture_coverage) }}</dd></div>
                  <div><dt>Temporal coherence</dt><dd>{{ percent(result.quality.temporal_coherence) }}</dd></div>
                  <div><dt>Saturated pixels</dt><dd>{{ percent(result.quality.saturation_ratio) }}</dd></div>
                  <div><dt>Residual noise</dt><dd>{{ number(result.quality.noise_estimate, 2) }}</dd></div>
                  <div><dt>Vt/Vc signal</dt><dd>{{ percent(result.quality.volume_signal_score) }}</dd></div>
                </dl>
                <ul v-if="result.quality.warnings?.length" class="backend-warning-list"><li v-for="warning in result.quality.warnings" :key="warning">{{ reasonLabel(warning) }}</li></ul>
                <p class="panel-note">Checks passed means no configured engineering check failed. It is not a calibrated accuracy probability or a clinical validation.</p>
                <details v-if="result.diagnostic"><summary>Provisional estimates and quality reasons</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">{{ JSON.stringify(result.diagnostic,null,2) }}</pre></details>
              </section>
            </template>

            <section v-if="decoder" class="backend-dialog-section">
              <h3>Video decoder</h3>
              <dl class="quality-list">
                <div><dt>Decoded resolution</dt><dd>{{ decoder.width }} × {{ decoder.height }}</dd></div>
                <div><dt>Captured resolution</dt><dd>{{ record?.captureRoi?.frame_width }} × {{ record?.captureRoi?.frame_height }}</dd></div>
                <div><dt>Decoded frames</dt><dd>{{ integer(decoder.decoded_frame_count) }}</dd></div>
                <div><dt>Effective FPS</dt><dd>{{ number(decoder.fps, 1) }}</dd></div>
                <div><dt>Decoded duration</dt><dd>{{ seconds(decoder.decoded_duration_seconds) }}</dd></div>
                <div><dt>Decoder engine</dt><dd>{{ decoder.backend || '--' }}</dd></div>
              </dl>
            </section>

            <p v-if="error && result" class="error-banner">{{ error }}</p>
            <p v-if="record?.backendError?.message && !error" class="error-banner">{{ record.backendError.message }}</p>
          </template>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { PhX } from '@phosphor-icons/vue';
import WaveformChart from './WaveformChart.vue';

const props = defineProps({ open: Boolean, record: Object, loading: Boolean, error: String });
const emit = defineEmits(['close', 'analyze']);
const dialog = ref(null);
const closeButton = ref(null);
let previousFocus = null;
const result = computed(() => props.record?.offline?.status === 'complete' ? props.record.offline : null);
const qualityLabel = computed(() => ({checks_passed:'Checks passed',usable_with_caution:'Usable with caution',review_required:'Review required'}[result.value?.quality?.status] || 'Legacy · rerun analysis'));
const decoder = computed(() => {
  const diagnostics = props.record?.backendError?.diagnostics || result.value?.diagnostics;
  return diagnostics?.fallback || diagnostics?.direct || diagnostics || null;
});
const shortId = computed(() => props.record?.backendAnalysisId ? props.record.backendAnalysisId.slice(0, 8) : '--');
const isLegacy = computed(() => props.record?.captureRoi?.roi_contract_version !== 'went-roi-v2');
const roiContractLabel = computed(() => isLegacy.value ? 'Legacy compatibility' : 'Position locked v2');
const statusLabel = computed(() => props.loading ? 'Processing' : ({ complete: 'Complete', failed: 'Failed', processing: 'Processing' }[props.record?.backendStatus || result.value?.status] || 'Not started'));
const retryLabel = computed(() => props.record?.backendAnalysisId ? 'Retry offline analysis' : 'Run offline analysis');
const canAnalyze = computed(() => Boolean(props.record?.backendAnalysisId || props.record?.videoBlob) && !props.loading);
watch(() => props.open, async (open) => {
  if (open) { previousFocus = document.activeElement; await nextTick(); closeButton.value?.focus(); }
  else { previousFocus?.focus?.(); previousFocus = null; }
});
function close() { emit('close'); }
function onKeydown(event) {
  if (event.key === 'Escape') { event.preventDefault(); close(); return; }
  if (event.key !== 'Tab') return;
  const focusable = [...dialog.value.querySelectorAll('button:not(:disabled), [href], input:not(:disabled), [tabindex]:not([tabindex="-1"])')];
  if (!focusable.length) return;
  const first = focusable[0], last = focusable.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}
function number(value, digits) { return Number.isFinite(value) ? value.toFixed(digits) : '--'; }
function integer(value) { return Number.isFinite(value) ? String(Math.round(value)) : '--'; }
function percent(value) { return Number.isFinite(value) ? `${Math.round(value * 100)}%` : '--'; }
function seconds(value) { return Number.isFinite(value) ? `${value.toFixed(1)} s` : '--'; }
function interval(value) { return value ? `${(value.start_ms / 1000).toFixed(2)}–${(value.end_ms / 1000).toFixed(2)} s` : '--'; }
function roiText(value) { return value ? `${value.width}×${value.height} @ ${value.x},${value.y}` : '--'; }
function reasonLabel(value) {
  const labels = { insufficient_complete_tidal_cycles: 'Too few complete normal-breathing cycles.', severely_inconsistent_tidal_amplitudes: 'Normal-breathing amplitudes were too inconsistent for a formal value.', variable_tidal_amplitudes: 'Normal-breathing amplitudes varied; the value is usable with caution.', tidal_below_noise: 'Normal-breathing movement was too close to noise.', tidal_baseline_drift: 'The normal-breathing baseline drifted; the value is usable with caution.', vital_below_noise: 'Maximum inhale/exhale separation was too close to noise.', vital_not_greater_than_tidal: 'Maximum movement was not greater than normal breathing.', reversed_vital_levels: 'Inhale and exhale levels were reversed.', light_subject_saturation: 'The light shirt was overexposed; contour values are usable with caution.' };
  return labels[value] || (String(value).startsWith('incomplete_') ? `Missing or delayed frames in ${String(value).slice(11)}.` : value);
}
</script>

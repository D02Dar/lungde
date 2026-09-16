<template>
  <section class="record-layout">
    <div class="stack">
      <p v-if="statusText" :class="['status-banner',statusTone]">{{ statusText }}</p>
      <template v-if="selected">
        <RecordPlayer ref="player" :video-url="videoUrl" :recorded-duration-ms="selected.durationMs || 0" @time="playheadMs=$event"/>
        <RecordTraceChart
          :samples="selected.samples || []"
          :offline="selected.offline"
          :phase-windows="selected.captureRoi?.phase_windows || {}"
          :evidence="selected.evidence || []"
          :playhead-ms="playheadMs"
          @seek="seek"
        />
        <section class="panel evidence-launcher">
          <div class="panel-head"><div><h2>Review details</h2>
            <p>Analysis and evidence stay attached to the selected record.</p></div></div>
          <div class="panel-body record-review-actions">
            <button class="btn btn-primary" type="button" @click="backendOpen=true">{{ backendButtonLabel }}</button>
            <button class="btn btn-quiet" type="button" :disabled="!selected.evidence?.length" @click="evidenceOpen=true">Open evidence · {{ selected.evidence?.length || 0 }}</button>
          </div>
        </section>
        <RecordSummary :record="selected" @delete="remove" @download-video="downloadVideo" @save-metadata="saveMetadata"/>
      </template>
      <section v-else class="panel"><div class="panel-body"><div class="empty-state"><strong>Select a record</strong><p>Select a measurement from the record list.</p></div></div></section>
    </div>
    <div class="stack">
      <RecordList
        :records="records"
        :selected-id="selectedId"
        :max-recordings="maxRecordings"
        :usage-text="usageText"
        :selected-for-export="comparisonIds"
        :selection-limit="comparisonLimit"
        @select="select"
        @toggle-export="toggleComparison"
        @select-export="setComparison"
        @delete-export="removeSelected"
      />
      <ComparisonExport :current-record="selected" :records="comparisonRecords" :limit="comparisonLimit" />
      <section class="panel">
        <div class="panel-head"><div><h2>How to review records</h2>
          <p>Realtime, offline, and Primary analysis stay inside this Record page.</p></div></div>
        <div class="panel-body">
          <section class="flow-strip">
            <article class="flow-card compact"><span>1. Waveform</span>
              <b>Click a time point</b><p>Jump to the same point in the saved video.</p></article>
            <article class="flow-card compact"><span>2. offline</span><b>Run or retry here</b>
              <p>Video processing, alignment, errors, and the Primary result remain in the analysis dialog.</p></article>
            <article class="flow-card compact"><span>3. Evidence</span><b>Open saved frames</b>
              <p>offline analysis persists the selected source frames, decoded timestamps, and ROI metadata.</p></article>
          </section>
          <button class="btn btn-primary" @click="$emit('open-stage','mark')">New measurement</button>
        </div>
      </section>
    </div>
    <EvidenceDialog :open="evidenceOpen" :video-url="videoUrl" :evidence="selected?.evidence || []" @close="evidenceOpen=false" @seek="seek"/>
    <BackendAnalysisDialog :open="backendOpen" :record="selected" :loading="analysisLoading" :error="analysisError" @close="backendOpen=false" @analyze="runAnalysis"/>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import RecordList from './RecordList.vue';
import ComparisonExport from './ComparisonExport.vue';
import RecordPlayer from './RecordPlayer.vue';
import RecordTraceChart from './RecordTraceChart.vue';
import RecordSummary from './RecordSummary.vue';
import EvidenceDialog from './EvidenceDialog.vue';
import BackendAnalysisDialog from './BackendAnalysisDialog.vue';
import { MAX_RECORDINGS, deleteRecording, estimateUsage, listRecordings, updateRecording } from '../features/records/recordingStore.js';
import { deleteAnalysis } from '../features/offline/api.js';
import { analyzeStoredRecord } from '../features/offline/recordAnalysisController.js';
import { realtimeReviewVersion, reviewStoredRealtime } from '../features/realtime/reviewStored.js';

const props = defineProps({ refreshToken: Number });
const emit = defineEmits(['open-stage', 'count']);
const records = ref([]);
const selectedId = ref('');
const selected = ref(null);
const videoUrl = ref('');
const playheadMs = ref(0);
const statusText = ref('');
const statusTone = ref('note');
const usageText = ref('');
const player = ref(null);
const evidenceOpen = ref(false);
const backendOpen = ref(false);
const analysisLoading = ref(false);
const analysisError = ref('');
const comparisonIds = ref([]);
const maxRecordings = MAX_RECORDINGS;
const comparisonLimit = 8;
let analysisController = null;

const backendButtonLabel = computed(() => selected.value?.backendAnalysisId || selected.value?.offline ? 'View offline analysis' : 'Run offline analysis');
const comparisonRecords = computed(() => records.value.filter(record => comparisonIds.value.includes(record.id)).slice(0, comparisonLimit));

async function refresh({ preserveSelection = true } = {}) {
  const previous = preserveSelection ? selectedId.value : '';
  const loaded = await listRecordings();
  records.value = [];
  for (const record of loaded) {
    const targetReviewVersion = realtimeReviewVersion(record);
    if (record.realtime?.algorithmVersion === targetReviewVersion || !record.samples?.length) {
      records.value.push(record);
      continue;
    }
    try {
      const realtime = reviewStoredRealtime(record);
      const updated = realtime ? await updateRecording(record.id, { realtime, algorithmVersion: targetReviewVersion }) : record;
      records.value.push(updated || record);
    } catch {
      records.value.push(record);
    }
  }
  comparisonIds.value = comparisonIds.value.filter(id => records.value.some(record => record.id === id)).slice(0, comparisonLimit);
  emit('count', records.value.length);
  const usage = await estimateUsage();
  usageText.value = usage ? `${(usage.usage / 1048576).toFixed(1)} MB used of ${(usage.quota / 1073741824).toFixed(1)} GB browser storage` : '';
  const nextId = records.value.some((record) => record.id === previous) ? previous : (records.value[0]?.id || '');
  select(nextId);
}

function toggleComparison(id) {
  comparisonIds.value = comparisonIds.value.includes(id)
    ? comparisonIds.value.filter(value => value !== id)
    : [...comparisonIds.value, id].slice(0, comparisonLimit);
}
function setComparison(ids) {
  comparisonIds.value = Array.from(new Set(ids)).filter(id => records.value.some(record => record.id === id)).slice(0, comparisonLimit);
}

async function saveMetadata(metadata) {
  if (!selected.value) return;
  try {
    const updated = await updateRecording(selected.value.id, { title: metadata.title, note: metadata.note });
    replaceSelected(updated);
    statusText.value = metadata.title || metadata.note ? 'Record name and notes saved on this device.' : 'Record name and notes cleared.';
    statusTone.value = 'good';
  } catch (error) {
    statusText.value = `Could not save record name or notes: ${error.message}`;
    statusTone.value = 'error';
  }
}

async function removeSelected() {
  const targets = records.value.filter(record => comparisonIds.value.includes(record.id));
  if (!targets.length || !window.confirm(`Delete ${targets.length} selected records, their saved videos, and backend evidence? This cannot be undone.`)) return;
  if (analysisLoading.value && targets.some(record => record.id === selectedId.value)) {
    analysisController?.abort();
    analysisLoading.value = false;
  }
  statusText.value = `Deleting ${targets.length} selected records…`;
  statusTone.value = 'note';
  let localFailures = 0;
  let backendFailures = 0;
  for (const target of targets) {
    if (target.backendAnalysisId) {
      try { await deleteAnalysis(target.backendAnalysisId); }
      catch { backendFailures += 1; }
    }
    try { await deleteRecording(target.id); }
    catch { localFailures += 1; }
  }
  comparisonIds.value = [];
  await refresh({ preserveSelection: !targets.some(record => record.id === selectedId.value) });
  if (localFailures || backendFailures) {
    statusText.value = `Batch delete finished with ${localFailures} local and ${backendFailures} backend cleanup failures.`;
    statusTone.value = 'error';
  } else {
    statusText.value = `${targets.length} selected records, videos, and backend evidence deleted.`;
    statusTone.value = 'good';
  }
}

function replaceSelected(updated) {
  if (!updated) return;
  records.value = records.value.map((record) => record.id === updated.id ? updated : record);
  selected.value = updated;
  selectedId.value = updated.id;
}

function select(id) {
  if (analysisLoading.value && id !== selectedId.value) {
    analysisController?.abort();
    analysisLoading.value = false;
  }
  releaseVideo();
  evidenceOpen.value = false;
  backendOpen.value = false;
  analysisError.value = '';
  selectedId.value = id;
  selected.value = records.value.find((record) => record.id === id) || null;
  videoUrl.value = selected.value?.videoBlob ? URL.createObjectURL(selected.value.videoBlob) : '';
  playheadMs.value = 0;
}

async function runAnalysis() {
  if (!selected.value || analysisLoading.value) return;
  const targetId = selected.value.id;
  analysisController?.abort();
  analysisController = new AbortController();
  analysisLoading.value = true;
  analysisError.value = '';
  statusText.value = 'offline analysis is running for this record…';
  statusTone.value = 'note';
  try {
    const updated = await analyzeStoredRecord(selected.value, { signal: analysisController.signal, updateRecording });
    if (selectedId.value === targetId) replaceSelected(updated);
    statusText.value = 'offline analysis and the Primary result were saved with this record';
    statusTone.value = 'good';
  } catch (error) {
    if (error?.name === 'AbortError') return;
    analysisError.value = error?.message || 'offline analysis failed';
    const latest = records.value.find((record) => record.id === targetId);
    const patched = await updateRecording(targetId, {
      backendAnalysisId: error.analysisId || latest?.backendAnalysisId || selected.value?.backendAnalysisId || null,
      backendStatus: 'failed',
      backendError: { code: error.code || 'analysis_failed', message: analysisError.value, diagnostics: error.diagnostics || null },
    });
    if (selectedId.value === targetId) replaceSelected(patched);
    statusText.value = analysisError.value;
    statusTone.value = 'error';
  } finally {
    if (selectedId.value === targetId) analysisLoading.value = false;
  }
}

function releaseVideo() {
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value);
  videoUrl.value = '';
}
function seek(ms) { player.value?.seek(ms); }
async function remove() {
  if (!selected.value) return;
  const target = selected.value;
  if (analysisLoading.value) analysisController?.abort();
  try {
    if (target.backendAnalysisId) {
      try { await deleteAnalysis(target.backendAnalysisId); }
      catch (error) { statusText.value = `Local record deleted, but backend cleanup failed: ${error.message}`; statusTone.value = 'error'; }
    }
    await deleteRecording(target.id);
    if (statusTone.value !== 'error') { statusText.value = 'Record, offline video, and saved evidence deleted'; statusTone.value = 'good'; }
    await refresh({ preserveSelection: false });
  } catch (error) { statusText.value = `Could not delete record: ${error.message}`; statusTone.value = 'error'; }
}
function downloadVideo() {
  if (!selected.value?.videoBlob) return;
  const url = URL.createObjectURL(selected.value.videoBlob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `went-run-${String(selected.value.createdAt).replace(/[:.]/g, '-')}.webm`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

watch(() => props.refreshToken, () => refresh(), { immediate: true });
onBeforeUnmount(() => { analysisController?.abort(); releaseVideo(); });
defineExpose({ refresh });
</script>

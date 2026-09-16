<template>
  <section class="analysis-export" aria-label="Export measurement analysis">
    <h3>Export for review</h3>
    <p>CSV opens in Excel. JSON keeps results, quality reasons, timestamps, calibration and ROI metadata. SVG contains raw/processed charts. Video and evidence image payloads are not included.</p>
    <div class="export-controls">
      <label><span>Waveform</span><select v-model="source" :disabled="format === 'zip'"><option value="offline">Backend · offline (default)</option><option value="realtime">Frontend · realtime</option></select></label>
      <label><span>Format</span><select v-model="format"><option value="svg">SVG chart</option><option value="csv">CSV data</option><option value="json">JSON archive</option><option value="zip">Backend reproducible ZIP</option></select></label>
      <button type="button" class="btn btn-quiet" :disabled="busy || (format === 'zip' && !record.backendAnalysisId)" @click="save">{{ busy ? 'Preparing…' : 'Export current record' }}</button>
    </div>
    <p role="status">{{ message }}</p>
  </section>
</template>
<script setup>
import { ref } from 'vue';
import { downloadAnalysis } from '../features/records/exportAnalysis.js';
import { downloadBackendAnalysisExport } from '../features/offline/api.js';
const props=defineProps({record:{type:Object,required:true}}),message=ref(''),format=ref('svg'),source=ref('offline'),busy=ref(false);
async function save() { if(busy.value)return;busy.value=true;try { if(format.value==='zip')await downloadBackendAnalysisExport(props.record.backendAnalysisId);else downloadAnalysis(props.record,format.value,{source:source.value}); message.value=format.value==='zip'?'Backend ZIP requested.':`${format.value.toUpperCase()} requested with ${source.value === 'offline' ? 'backend' : 'frontend'} waveform. Export stays on this device.`; } catch(error) { message.value=`Export failed: ${error.message}`; } finally { busy.value=false; } }
</script>
<style scoped>
.analysis-export { margin-top:20px; border-top:1px solid var(--rule); padding-top:18px; } h3 { margin:0 0 8px; } p { font-size:13px; line-height:1.6; color:var(--ink-soft); }
.export-controls { display:flex; align-items:end; flex-wrap:wrap; gap:8px; }
.export-controls label { display:grid; gap:4px; min-width:150px; color:var(--ink-soft); font-size:12px; }
.export-controls select { min-height:38px; padding:7px 30px 7px 10px; border:1px solid var(--rule-strong); border-radius:var(--radius); background:var(--panel); color:var(--ink); }
</style>

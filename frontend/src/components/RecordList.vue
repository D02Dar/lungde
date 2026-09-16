<template>
  <aside class="panel">
    <div class="panel-head">
      <div><h2>Records</h2><p>Measurements saved on this device, newest first.</p></div>
      <span class="trace-badge">{{ records.length }}/{{ maxRecordings }}</span>
    </div>
    <div class="panel-body">
      <div v-if="!records.length" class="empty-state"><strong>No records yet</strong><p>Complete or stop a measurement on the Measure page and it will appear here.</p></div>
      <template v-else>
        <div class="compare-toolbar">
          <span><b>{{ selectedForExport.length }}</b> selected for comparison</span>
          <span>
            <button type="button" @click="$emit('select-export', records.slice(0, selectionLimit).map(record => record.id))">Select latest {{ Math.min(records.length, selectionLimit) }}</button>
            <button type="button" :disabled="!selectedForExport.length" @click="$emit('select-export', [])">Clear</button>
            <button type="button" class="delete-selected" :disabled="!selectedForExport.length" @click="$emit('delete-export')">Delete selected</button>
          </span>
        </div>
        <ul class="record-list">
          <li v-for="record in records" :key="record.id" class="record-choice">
            <label class="compare-choice" :title="isAtLimit(record.id) ? `Up to ${selectionLimit} runs` : 'Include in comparison export'">
              <input type="checkbox" :checked="selectedForExport.includes(record.id)" :disabled="isAtLimit(record.id)" @change="$emit('toggle-export', record.id)" />
              <span>Compare</span>
            </label>
            <button class="record-item" :class="{active:record.id===selectedId}" @click="$emit('select',record.id)">
              <span class="record-item-head"><b>{{ record.title || stamp(record.createdAt) }}</b><em>{{ record.videoBlob ? size(record.videoBlob.size) : 'No video' }}</em></span>
              <small v-if="record.title" class="record-item-date">{{ stamp(record.createdAt) }}</small>
              <span>{{ Math.round((record.durationMs||0)/1000) }} s · {{ record.samples?.length||0 }} samples</span>
              <span>VcA/VtA {{ number(record.realtime?.ratio,2) }} · {{ record.offline?.status==='complete'?'Both paths complete':'Live path only' }}</span>
              <span v-if="record.note" class="record-note">{{ record.note }}</span>
            </button>
          </li>
        </ul>
      </template>
    </div>
    <p v-if="usageText" class="panel-note">{{ usageText }}</p>
  </aside>
</template>

<script setup>
const props=defineProps({records:Array,selectedId:String,maxRecordings:Number,usageText:String,selectedForExport:{type:Array,default:()=>[]},selectionLimit:{type:Number,default:8}});
defineEmits(['select','toggle-export','select-export','delete-export']);
function isAtLimit(id){return props.selectedForExport.length>=props.selectionLimit&&!props.selectedForExport.includes(id);}
function stamp(value){return new Date(value).toLocaleString('en-US',{month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'});}
function size(bytes=0){return bytes>=1048576?`${(bytes/1048576).toFixed(1)} MB`:`${Math.round(bytes/1024)} KB`;}
function number(v,d){return Number.isFinite(v)?v.toFixed(d):'--';}
</script>

<template>
  <header class="topbar">
    <p class="topbar-mark">
  <strong>2d camera webapp for recording lateral chest wall movement</strong>
</p>
    <nav class="stage-nav" aria-label="Measurement stages">
      <button v-for="(item, index) in stages" :key="item.key" type="button" class="stage-step" :class="{ done: isDone(index) }" :aria-current="item.key === stage ? 'step' : undefined" :disabled="item.key === 'measure' && !markLocked" :title="item.key === 'measure' && !markLocked ? 'Confirm the upper-body box first' : undefined" @click="$emit('go', item.key)">
        <i>{{ index + 1 }}</i><b>{{ item.label }}</b></button>
      <button type="button" class="stage-step stage-step-aside" :aria-current="stage === 'record' ? 'page' : undefined" @click="$emit('go', 'record')"><PhFilmScript :size="18" />
        <b>Records</b><em>{{ recordCount }}</em></button>
    </nav>
    <div class="status-strip" aria-live="polite"><p :class="['status-read', cameraStatus.kind]"><s></s><b>{{ cameraStatus.text }}</b></p><p :class="['status-read', measurementStatus.kind]"><s></s>
      <b>{{ measurementStatus.text }}</b></p></div>
  </header>
</template>
<script setup>import{PhFilmScript}from'@phosphor-icons/vue';const props=defineProps({stage:String,stages:Array,markLocked:Boolean,cameraStatus:Object,measurementStatus:Object,recordCount:{type:Number,default:0}});defineEmits(['go']);function isDone(index){const current=props.stages.findIndex(item=>item.key===props.stage);return current>index;}</script>

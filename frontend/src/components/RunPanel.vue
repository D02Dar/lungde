<template>
  <aside class="panel run-panel">
    <div class="panel-head">
      <div>
        <h2>Measurement</h2>
        <p>When your position is steady, start the breathing sequence.</p>
      </div>
      <label class="voice-toggle">
        <input :checked="voiceEnabled" type="checkbox" @change="$emit('update:voiceEnabled',$event.target.checked)">
        <PhSpeakerHigh :size="18"/>
        Voice prompts
      </label>
    </div>
    <div class="panel-body">
      <section class="flow-strip">
        <article
          v-for="(item,index) in protocol"
          :key="item.key"
          :class="['flow-card','compact',{active:phase===item.key,done:completed.includes(item.key)}]"
        >
          <span>{{index+1}} · {{item.seconds}} s</span>
          <b>{{item.label}}</b>
          <p>{{item.prompt}}</p>
        </article>
      </section>
      <section class="phase-readout">
        <span>Current prompt</span>
        <strong>{{prompt||'Ready to begin'}}</strong>
        <b class="tnum">{{running?`${Math.ceil(remainingMs/1000)} s`:'—'}}</b>
      </section>
      <p v-if="saveMessage" :class="['save-message',saveTone]">{{saveMessage}}</p>
      <div class="control-row">
        <button
          v-if="!running"
          class="btn btn-primary"
          :disabled="!cameraReady||saving"
          @click="$emit('start')"
        >
          <PhPlay :size="18" weight="fill"/>
          Start measurement
        </button>
        <button
          v-else
          class="btn btn-danger"
          @click="$emit('stop')"
        >
          <PhStop :size="18" weight="fill"/>
          Stop early
        </button>
        <button class="btn btn-quiet" type="button" @click="$emit('open-records')">
          Open Records
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { PhPlay, PhSpeakerHigh, PhStop } from '@phosphor-icons/vue';

defineProps({
  protocol: Array,
  phase: String,
  prompt: String,
  remainingMs: Number,
  running: Boolean,
  cameraReady: Boolean,
  completed: { type: Array, default: () => [] },
  voiceEnabled: Boolean,
  saving: Boolean,
  saveMessage: String,
  saveTone: String
});

defineEmits(['start','stop','open-records','update:voiceEnabled']);
</script>

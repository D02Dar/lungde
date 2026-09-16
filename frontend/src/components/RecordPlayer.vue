<template>
  <section class="panel">
    <div class="panel-head">
      <div>
        <h2>Measurement video</h2>
        <p>Original camera footage saved during measurement.</p>
      </div>
      <span :class="['trace-badge', { live: playing }]">{{ playing ? 'Playing' : 'Paused' }}</span>
    </div>
    <div class="panel-body">
      <div v-if="!videoUrl" class="empty-state">
        <strong>This record has no video</strong>
        <p>Area samples are still saved when recording is unsupported or fails.</p>
      </div>
      <template v-else>
        <div class="record-video-frame">
          <video
            ref="video"
            :src="videoUrl"
            playsinline
            preload="metadata"
            @loadedmetadata="readDuration"
            @durationchange="readDuration"
            @play="playing = true"
            @pause="playing = false"
            @ended="playing = false"
            @timeupdate="emitTime"
          ></video>
        </div>
        <div class="record-controls">
          <button class="btn btn-primary" @click="toggle">
            <PhPause v-if="playing" :size="18" />
            <PhPlay v-else :size="18" weight="fill" />
            {{ playing ? 'Pause' : 'Play' }}
          </button>
          <span class="record-clock">{{ time(currentMs) }} / {{ time(displayDurationMs) }}</span>
        </div>

      </template>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue';
import { PhPause, PhPlay } from '@phosphor-icons/vue';

const props = defineProps({
  videoUrl: String,
  recordedDurationMs: { type: Number, default: 0 },
});
const emit = defineEmits(['time']);
const video = ref(null);
const playing = ref(false);
const currentMs = ref(0);
const metadataDurationMs = ref(0);
const containerDurationInvalid = ref(false);
const displayDurationMs = computed(() => metadataDurationMs.value || Math.max(0, props.recordedDurationMs || 0));

function readDuration() {
  const duration = video.value?.duration;
  if (Number.isFinite(duration) && duration > 0) {
    metadataDurationMs.value = duration * 1000;
    containerDurationInvalid.value = false;
  } else {
    metadataDurationMs.value = 0;
    containerDurationInvalid.value = Boolean(video.value && (duration === Infinity || Number.isNaN(duration)));
  }
}
function emitTime() {
  currentMs.value = (video.value?.currentTime || 0) * 1000;
  readDuration();
  emit('time', currentMs.value);
}
function toggle() {
  if (!video.value) return;
  video.value.paused ? video.value.play() : video.value.pause();
}
function seek(ms) {
  if (video.value) video.value.currentTime = Math.max(0, ms / 1000);
}
function time(ms) {
  const seconds = Math.max(0, Math.floor(Number.isFinite(ms) ? ms / 1000 : 0));
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}
defineExpose({ seek });
</script>

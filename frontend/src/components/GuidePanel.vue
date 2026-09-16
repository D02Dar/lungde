<template>
  <section class="panel guide-panel">
    <div class="panel-head guide-panel-head">
      <div>
        <p class="eyebrow">First measurement</p>
        <h2>Turn into the measurement position</h2>
        <p>Follow the six images from front view to a stable side view.</p>
      </div>
      <span class="guide-duration">about 30 seconds</span>
    </div>
    <div class="panel-body">
      <VisualGuideCarousel @complete="$emit('advance')" />
      <CaptureConditions />
      <p class="panel-note">{{ protocolSeconds }}-second sequence. You can listen to the exact cues in the Position standing example before recording.</p>
      <div class="guide-tutorial-link">
        <button class="btn btn-quiet" type="button" @click="$emit('open-tutorial')">
          <PhQuestion :size="18" weight="bold" />
          How the measurement works
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';
import { PhQuestion } from '@phosphor-icons/vue';
import VisualGuideCarousel from './VisualGuideCarousel.vue';
import CaptureConditions from './CaptureConditions.vue';

const props = defineProps({ protocol: { type: Array, required: true } });
defineEmits(['advance', 'open-stage', 'open-tutorial']);
const protocolSeconds = computed(() => props.protocol.reduce((total, step) => total + Number(step.seconds || 0), 0));
</script>

<style scoped>
.guide-tutorial-link {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.guide-tutorial-link .btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
</style>

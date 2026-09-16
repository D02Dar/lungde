<template>
  <section class="visual-guide" aria-labelledby="visual-guide-title" @keydown.left.prevent="previous" @keydown.right.prevent="next">
    <div class="visual-guide-copy">
      <p class="eyebrow">{{ active.kicker }}</p>
      <h2 id="visual-guide-title">{{ active.title }}</h2>
      <p>{{ active.body }}</p>
      <div class="visual-guide-progress" role="tablist" aria-label="Position guide steps">
        <button
          v-for="(item, stepIndex) in steps"
          :key="item.key"
          type="button"
          role="tab"
          :aria-selected="stepIndex === index"
          :aria-label="`Show step ${stepIndex + 1}: ${item.title}`"
          :class="{ active: stepIndex === index, complete: stepIndex < index }"
          @click="index = stepIndex"
        ><span>{{ stepIndex + 1 }}</span></button>
      </div>
    </div>

    <figure class="visual-guide-frame">
      <Transition name="guide-image" mode="out-in">
        <img :key="active.key" :src="active.image" :alt="active.alt" @error="imageFailed = true" />
      </Transition>
      <div v-if="imageFailed" class="visual-guide-fallback">
        <BodyPositionFigure :title="active.title" :caption="active.body" compact />
      </div>
      <figcaption><span>{{ String(index + 1).padStart(2, '0') }}</span> / {{ String(steps.length).padStart(2, '0') }}</figcaption>
    </figure>

    <div class="visual-guide-actions">
      <button class="btn btn-quiet" type="button" :disabled="index === 0" @click="previous">Previous</button>
      <button v-if="index < steps.length - 1" class="btn btn-primary" type="button" @click="next">Next step</button>
      <button v-else class="btn btn-primary" type="button" @click="$emit('complete')">Open Position</button>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import BodyPositionFigure from './BodyPositionFigure.vue';
import { visualGuideSteps } from './visualGuideSteps.js';

const props = defineProps({ initialStep: { type: Number, default: 0 } });
defineEmits(['complete']);
const steps = visualGuideSteps;
const index = ref(Math.max(0, Math.min(steps.length - 1, props.initialStep)));
const imageFailed = ref(false);
const active = computed(() => steps[index.value]);

watch(index, () => { imageFailed.value = false; });
function previous() { index.value = Math.max(0, index.value - 1); }
function next() { index.value = Math.min(steps.length - 1, index.value + 1); }
defineExpose({ reset: () => { index.value = 0; } });
</script>

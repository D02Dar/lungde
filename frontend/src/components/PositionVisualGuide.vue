<template>
  <Teleport to="body">
    <Transition name="guide-overlay">
      <div v-if="visible" class="position-guide-overlay" @click="$emit('close')">
        <section class="position-guide-card position-guide-card-wide" @click.stop>
          <button class="guide-close" type="button" aria-label="Close position guide" @click="$emit('close')">
            <PhX :size="22" weight="bold" />
          </button>
          <section class="standing-example" aria-labelledby="standing-example-title">
            <div class="standing-example-copy">
              <p class="eyebrow">Standing example</p>
              <h2 id="standing-example-title">Match this side-on posture</h2>
              <p>User can follow this video until they find the right position.</p>
            </div>

            <div v-if="mediaUrl" class="standing-example-media">
              <video v-if="mediaKind === 'video'" :src="mediaUrl" controls autoplay muted loop playsinline @error="handleDefaultError" />
              <img v-else :src="mediaUrl" alt="Uploaded standing posture example" />
            </div>
            <BodyPositionFigure v-else title="Stand side-on with your back in the green band" caption="Keep your head, shoulders, chest, and waist visible and stay still." />
            <VoicePractice />

            <div class="standing-example-actions">
              <label class="btn btn-quiet upload-button">
                Upload standing example
                <input ref="fileInput" type="file" accept="video/*,image/*" @change="handleFile" />
              </label>
              <button class="btn btn-primary" type="button" @click="$emit('close')">Open Position</button>
            </div>
          </section>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue';
import { PhX } from '@phosphor-icons/vue';
import BodyPositionFigure from './BodyPositionFigure.vue';
import VoicePractice from './VoicePractice.vue';

const props = defineProps({ visible: Boolean });
defineEmits(['close']);
const fileInput = ref(null);
const defaultMediaUrl = '/guide/standing-example.mp4';
const mediaUrl = ref(defaultMediaUrl);
const mediaKind = ref('video');
let objectUrl = '';

function handleFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  if (objectUrl) URL.revokeObjectURL(objectUrl);
  objectUrl = URL.createObjectURL(file);
  mediaUrl.value = objectUrl;
  mediaKind.value = file.type.startsWith('video/') ? 'video' : 'image';
}

function handleDefaultError() {
  if (mediaUrl.value === defaultMediaUrl) {
    mediaUrl.value = '';
    mediaKind.value = '';
  }
}

function clearMedia() {
  if (objectUrl) URL.revokeObjectURL(objectUrl);
  objectUrl = '';
  mediaUrl.value = '';
  mediaKind.value = '';
  if (fileInput.value) fileInput.value.value = '';
}

watch(() => props.visible, (visible) => {
  if (visible) {
    mediaUrl.value = defaultMediaUrl;
    mediaKind.value = 'video';
  } else {
    clearMedia();
  }
});
onBeforeUnmount(clearMedia);
</script>

<style scoped>
.standing-example { display: grid; gap: 22px; }
.standing-example-copy { display: grid; gap: 7px; }
.standing-example-copy h2, .standing-example-copy p { margin: 0; }
.standing-example-copy h2 { font-size: var(--step-2); line-height: 1.2; }
.standing-example-copy > p:last-child { color: var(--ink-soft); line-height: 1.5; }
.standing-example-media { overflow: hidden; border: 1px solid var(--rule); border-radius: var(--radius); background: var(--paper-sunken); }
.standing-example-media video, .standing-example-media img { display: block; width: 100%; max-height: 56vh; object-fit: contain; }
.standing-example-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 10px; }
.upload-button { cursor: pointer; }
.upload-button input { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
@media (max-width: 640px) {
  .standing-example-copy h2 { font-size: var(--step-1); }
  .standing-example-actions .btn { flex: 1 1 140px; }
}
</style>

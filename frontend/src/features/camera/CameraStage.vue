<template>
  <div class="camera-stage">
    <video ref="video" playsinline muted autoplay></video>
    <canvas ref="overlay" class="stage-overlay" @pointerdown="beginDrag" @pointermove="moveDrag" @pointerup="endDrag" @pointercancel="endDrag"></canvas>
    <div v-if="!cameraReady" class="stage-empty">
      <div class="position-preview" aria-hidden="true">
        <span class="preview-head"></span><span class="preview-body"></span><span class="preview-back">BACK<br>HERE</span>
      </div>
      <strong>{{ phase === 'measure' ? 'Camera closed' : 'Stand side-on' }}</strong>
      <span>{{ phase === 'measure' ? 'The camera was released after saving. Start again to return to Position and make a new measurement.' : 'Place your back in the green band, then adjust the frame around your upper body.' }}</span>
      <button class="btn btn-primary" type="button" @click="$emit('open-camera')"><PhVideoCamera :size="18"/>{{ phase === 'measure' ? 'Start another measurement' : 'Open camera' }}</button>
      <small>Video is processed locally.</small>
    </div>
    <div v-if="phase === 'mark' && directive" class="directive-pill" :class="{ calibrating }" aria-live="polite">{{ directive }}</div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { PhVideoCamera } from '@phosphor-icons/vue';
import { clampBox, deriveChestRoi, resizeBoxFromCorner } from './calibrationBox.js';

const props = defineProps({
  box: { type: Object, required: true },
  cameraReady: Boolean,
  locked: Boolean,
  editable: { type: Boolean, default: true },
  phase: { type: String, default: 'position' },
  chestRoi: { type: Object, default: null },
  directive: { type: String, default: '' },
  calibrating: Boolean,
});
const emit = defineEmits(['update:box', 'open-camera']);
const video = ref(null);
const overlay = ref(null);
let observer;
let drag = null;

function coverTransform(videoWidth, videoHeight, displayWidth, displayHeight) {
  if (!videoWidth || !videoHeight || !displayWidth || !displayHeight) return { scale: 1, offsetX: 0, offsetY: 0 };
  const scale = Math.max(displayWidth / videoWidth, displayHeight / videoHeight);
  return {
    scale,
    offsetX: (displayWidth - videoWidth * scale) / 2,
    offsetY: (displayHeight - videoHeight * scale) / 2,
  };
}

function displayedBox(box, width, height) {
  const sourceWidth = video.value?.videoWidth || width;
  const sourceHeight = video.value?.videoHeight || height;
  const transform = coverTransform(sourceWidth, sourceHeight, width, height);
  return {
    x: box.x * sourceWidth * transform.scale + transform.offsetX,
    y: box.y * sourceHeight * transform.scale + transform.offsetY,
    w: box.width * sourceWidth * transform.scale,
    h: box.height * sourceHeight * transform.scale,
  };
}

function drawCornerBrackets(ctx, box, color) {
  const { x, y, w, h } = box;
  const len = Math.min(20, w * 0.16, h * 0.1);
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.setLineDash([]);
  ctx.beginPath();
  ctx.moveTo(x, y + len); ctx.lineTo(x, y); ctx.lineTo(x + len, y);
  ctx.moveTo(x + w - len, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + len);
  ctx.moveTo(x, y + h - len); ctx.lineTo(x, y + h); ctx.lineTo(x + len, y + h);
  ctx.moveTo(x + w - len, y + h); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w, y + h - len);
  ctx.stroke();
}

function drawBackReferenceBand(ctx, box) {
  const width = Math.max(28, box.w * 0.12);
  const left = box.x + box.w - width;
  ctx.fillStyle = 'rgba(29,158,117,.2)';
  ctx.fillRect(left, box.y, width, box.h);
  ctx.strokeStyle = 'rgba(29,158,117,.9)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(left, box.y);
  ctx.lineTo(left, box.y + box.h);
  ctx.stroke();
  ctx.save();
  ctx.translate(left + width / 2, box.y + box.h / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillStyle = 'rgba(255,255,255,.95)';
  ctx.font = '600 12px system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('PLACE BACK HERE', 0, 4);
  ctx.restore();
}

function drawAnalysisRegion(ctx, roi, width, height, { fill, stroke, label }) {
  if (!roi) return;
  const region = displayedBox(roi, width, height);
  ctx.fillStyle = fill;
  ctx.fillRect(region.x, region.y, region.w, region.h);
  ctx.strokeStyle = stroke;
  ctx.lineWidth = 1.5;
  ctx.setLineDash([]);
  ctx.strokeRect(region.x, region.y, region.w, region.h);
  ctx.fillStyle = 'rgba(255,255,255,.96)';
  ctx.font = '600 10px system-ui, sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText(label, region.x + 5, region.y + 13);
}

function drawChestRegion(ctx, width, height) {
  drawAnalysisRegion(ctx, props.chestRoi || deriveChestRoi(props.box), width, height, {
    fill: 'rgba(29,158,117,.15)', stroke: 'rgba(29,158,117,.72)', label: 'CHEST MEASUREMENT AREA',
  });
}

function drawResizeHandles(ctx, box) {
  if (!props.editable) return;
  ctx.fillStyle = '#1d9e75';
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 2;
  for (const [x, y] of [[box.x, box.y], [box.x + box.w, box.y], [box.x, box.y + box.h], [box.x + box.w, box.y + box.h]]) {
    ctx.beginPath();
    ctx.arc(x, y, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
}

function drawFrameGuide(ctx, box) {
  const title = props.locked ? 'FRAME CONFIRMED' : 'ADJUST THIS FRAME';
  const detail = props.locked
    ? 'Your chest measurement area is ready'
    : 'Drag inside to move · drag corners to resize';
  const x = box.x + 8;
  const y = box.y + 8;
  ctx.font = '700 12px system-ui, sans-serif';
  const labelWidth = Math.min(box.w - 16, Math.max(ctx.measureText(title).width, ctx.measureText(detail).width) + 16);
  ctx.fillStyle = 'rgba(8,19,23,.74)';
  ctx.fillRect(x - 4, y - 4, labelWidth, 38);
  ctx.fillStyle = 'rgba(255,255,255,.98)';
  ctx.textAlign = 'left';
  ctx.fillText(title, x + 4, y + 10);
  ctx.font = '500 10px system-ui, sans-serif';
  ctx.fillStyle = 'rgba(232,244,240,.94)';
  ctx.fillText(detail, x + 4, y + 25);
}

function draw() {
  const canvas = overlay.value;
  const host = canvas?.parentElement;
  if (!canvas || !host) return;
  const ratio = window.devicePixelRatio || 1;
  const width = host.clientWidth;
  const height = host.clientHeight;
  canvas.width = Math.max(1, Math.round(width * ratio));
  canvas.height = Math.max(1, Math.round(height * ratio));
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  const ctx = canvas.getContext('2d');
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);

  if (props.phase === 'measure') {
    drawChestRegion(ctx, width, height);
    return;
  }

  const box = displayedBox(props.box, width, height);
  ctx.fillStyle = 'rgba(8,19,23,.38)';
  ctx.fillRect(0, 0, width, height);
  ctx.clearRect(box.x, box.y, box.w, box.h);
  drawBackReferenceBand(ctx, box);
  drawChestRegion(ctx, width, height);
  drawCornerBrackets(ctx, box, props.locked ? 'rgba(29,158,117,.95)' : 'rgba(29,158,117,.8)');
  drawResizeHandles(ctx, box);
  drawFrameGuide(ctx, box);
}

function point(event) {
  const rect = overlay.value.getBoundingClientRect();
  const sourceWidth = video.value?.videoWidth || rect.width;
  const sourceHeight = video.value?.videoHeight || rect.height;
  const transform = coverTransform(sourceWidth, sourceHeight, rect.width, rect.height);
  return {
    x: ((event.clientX - rect.left - transform.offsetX) / transform.scale) / sourceWidth,
    y: ((event.clientY - rect.top - transform.offsetY) / transform.scale) / sourceHeight,
  };
}
function dragTarget(event) {
  const rect = overlay.value.getBoundingClientRect();
  const cursor = { x: event.clientX - rect.left, y: event.clientY - rect.top };
  const box = displayedBox(props.box, rect.width, rect.height);
  const handles = {
    nw: [box.x, box.y], ne: [box.x + box.w, box.y],
    sw: [box.x, box.y + box.h], se: [box.x + box.w, box.y + box.h],
  };
  for (const [corner, [x, y]] of Object.entries(handles)) {
    if (Math.hypot(cursor.x - x, cursor.y - y) <= 20) return corner;
  }
  return cursor.x >= box.x && cursor.x <= box.x + box.w && cursor.y >= box.y && cursor.y <= box.y + box.h ? 'move' : '';
}
function cursorFor(target) {
  if (target === 'nw' || target === 'se') return 'nwse-resize';
  if (target === 'ne' || target === 'sw') return 'nesw-resize';
  return target === 'move' ? 'move' : 'default';
}
function beginDrag(event) {
  if (!props.editable) return;
  const target = dragTarget(event);
  if (!target) return;
  const p = point(event);
  drag = { target, p, box: { ...props.box } };
  overlay.value.setPointerCapture?.(event.pointerId);
}
function moveDrag(event) {
  if (!props.editable) return;
  if (!drag) {
    overlay.value.style.cursor = cursorFor(dragTarget(event));
    return;
  }
  const p = point(event);
  const deltaX = p.x - drag.p.x;
  const deltaY = p.y - drag.p.y;
  const next = drag.target === 'move'
    ? clampBox({ ...drag.box, x: drag.box.x + deltaX, y: drag.box.y + deltaY })
    : resizeBoxFromCorner(drag.box, drag.target, deltaX, deltaY);
  emit('update:box', next);
}
function endDrag(event) {
  if (drag) overlay.value?.releasePointerCapture?.(event.pointerId);
  drag = null;
  if (overlay.value) overlay.value.style.cursor = cursorFor(dragTarget(event));
}
function handleVideoGeometry() { draw(); }

watch(() => [props.box, props.locked, props.phase, props.chestRoi], draw, { deep: true });
onMounted(() => {
  observer = new ResizeObserver(draw);
  observer.observe(overlay.value.parentElement);
  video.value?.addEventListener('loadedmetadata', handleVideoGeometry);
  draw();
});
onBeforeUnmount(() => {
  observer?.disconnect();
  video.value?.removeEventListener('loadedmetadata', handleVideoGeometry);
});
defineExpose({ video });
</script>

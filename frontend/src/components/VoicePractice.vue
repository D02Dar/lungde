<template>
  <section class="voice-practice" aria-label="Measurement audio rehearsal">
    <h3>Preview each audio cue</h3>
    <p><b> For inhale and exhale, the preparation voice plays first and the start bell follows 3 seconds later, matching capture.
      </b>
      </p>
    <div class="cue-grid">
      <article v-for="cue in cues" :key="cue.key" :class="{ active: activeKey === cue.key }">
        <span>{{ cue.step }}</span>
        <b>{{ cue.title }}</b>
        <p>{{ cue.description }}</p>
        <button type="button" :class="['btn', activeKey === cue.key ? 'btn-primary' : 'btn-quiet']" @click="activeKey === cue.key ? stop() : play(cue)">
          {{ activeKey === cue.key ? 'Stop preview' : cue.button }}
        </button>
      </article>
    </div>
    <div class="cue-current" role="status" aria-live="polite"><b>{{ statusTitle }}</b><p>{{ message }}</p></div>
    <p v-if="!speechAvailable" class="panel-note">Speech is unavailable in this browser. Bells and on-screen instructions remain available; check system voice support and device volume.</p>
  </section>
</template>
<script setup>
import { onBeforeUnmount, ref } from 'vue';
import { AudioGuide } from '../features/audio/audioGuide.js';
import { protocol } from '../features/protocol/config.js';
const activeKey=ref(''), statusTitle=ref('Ready to preview'), message=ref('Choose one section. Nothing is recorded.');
const speechAvailable=typeof window !== 'undefined' && Boolean(window.speechSynthesis);
const audio=new AudioGuide();
const phase = key => protocol.find(step => step.key === key);
const cues = [
  { key:'tidal', step:'01', title:'Normal breathing cue', description:'Start bell and “Breathe normally.”', button:'normal audio cue', voice:phase('tidal')?.voice, delay:0 },
  { key:'inhale', step:'02', title:'Inhale preparation', description:'Preparation voice, then the inhale start bell after 3 seconds.', button:'Preview inhale cue', voice:phase('inhalePrep')?.voice, delay:(phase('inhalePrep')?.seconds || 3)*1000 },
  { key:'exhale', step:'03', title:'Exhale preparation', description:'Preparation voice, then the exhale start bell after 3 seconds.', button:'Preview exhale cue', voice:phase('exhalePrep')?.voice, delay:(phase('exhalePrep')?.seconds || 3)*1000 },
];
let timers=[];
function stop({ complete=false }={}) {
  timers.forEach(clearTimeout); timers=[]; audio.cancel();
  if(activeKey.value) message.value=complete ? 'This cue preview is complete.' : 'Preview stopped.';
  activeKey.value=''; statusTitle.value=complete ? 'Preview complete' : 'Ready to preview';
}
function play(cue) {
  stop(); audio.initialise(); activeKey.value=cue.key; statusTitle.value=cue.title;
  if(cue.delay) {
    message.value='Preparation voice playing. Wait for the bell before beginning.';
    audio.speak(cue.voice,{key:`preview-${cue.key}`,minIntervalMs:0});
    timers.push(window.setTimeout(()=>{ audio.beep(1046,220); message.value='Bell: begin the movement now.'; timers.push(window.setTimeout(()=>stop({complete:true}),900)); },cue.delay));
  } else {
    audio.beep(1046,220); audio.speak(cue.voice,{key:'preview-tidal',minIntervalMs:0}); message.value='Bell and normal-breathing voice cue.';
    timers.push(window.setTimeout(()=>stop({complete:true}),2200));
  }
}
onBeforeUnmount(()=>{ stop(); audio.context?.close?.(); });
</script>
<style scoped>
.voice-practice { padding:18px; background:var(--paper-sunken); border:1px solid var(--rule); border-radius:8px; }
h3 { margin:0 0 10px; } p { line-height:1.55; font-size:13px; color:var(--ink-soft); }
.cue-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:15px; }
.cue-grid article { display:flex; flex-direction:column; align-items:flex-start; gap:7px; padding:12px; border:1px solid var(--rule); border-radius:7px; background:var(--paper); }
.cue-grid article.active { border-color:#c8322f; box-shadow:inset 3px 0 #c8322f; }.cue-grid span { color:#c8322f; font:700 11px ui-monospace,monospace; }.cue-grid p { flex:1; margin:0; }.cue-grid .btn { width:100%; padding-inline:8px; }
.cue-current { padding-top:14px; min-height:58px; }.cue-current p { margin:5px 0 0; }
@media(max-width:720px) { .cue-grid { grid-template-columns:1fr; } }
</style>

<template>
  <section class="instrument-panel evidence-panel">
    <header class="panel-heading"><div><h2>Evidence frames</h2>
      <p>Generated from the saved source video at signal timestamps.</p></div>
      <span class="state-text idle">{{ frames.length }} frames</span></header>
    <div v-if="!evidence?.length" class="empty-copy">This record has no usable evidence timestamps.</div>
    <div v-else class="evidence-grid"><article v-for="frame in frames" :key="frame.key"><div class="evidence-image">
      <img v-if="frame.image" :src="frame.image" :alt="frame.label"><span v-else>{{ frame.summary }}</span></div>
      <strong>{{ frame.label }}</strong><small>{{ (frame.elapsedMs / 1000).toFixed(2) }} s</small></article></div>
  </section>
</template>
<script setup>

// This component displays a grid of evidence frames extracted from a video at specific timestamps.

import { ref, watch } from 'vue';
const props=defineProps({videoUrl:String,evidence:{type:Array,default:()=>[]}});

const frames=ref([]);watch(()=>[props.videoUrl,props.evidence],rebuild,{immediate:true,deep:true});

async function rebuild(){frames.value=(props.evidence||[]).map(item=>({...item,image:''}));
if(!props.videoUrl||!frames.value.length)return;

const video=document.createElement('video');
video.src=props.videoUrl;video.muted=true;video.preload='auto';try{await event(video,'loadedmetadata');}catch{return;}

const canvas=document.createElement('canvas');
canvas.width=480;canvas.height=Math.round(480*video.videoHeight/video.videoWidth);const ctx=canvas.getContext('2d');

for(const frame of frames.value){try{video.currentTime=Math.min(Math.max(0,frame.elapsedMs/1000),Math.max(0,video.duration-.05));
  await event(video,'seeked');
ctx.drawImage(video,0,0,canvas.width,canvas.height);frame.image=canvas.toDataURL('image/jpeg',.76);}
catch{frame.image='';}}}

function event(target,name)
{return new Promise((resolve,reject)=>{target.addEventListener(name,resolve,{once:true});
target.addEventListener('error',reject,{once:true});});
}
</script>

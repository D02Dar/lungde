"use strict";
import { detectPeaksAndTroughs } from "./peaks.js";

export function computeRealtimeMetrics(samples, fps = 30, { rawSamples = samples, roiPixels = null, minimumTidalCycles = 2, sourceSamples = rawSamples, phaseWindows = {} } = {}) {
  if (!samples?.length) return null;
  const clean = samples.filter(s => Number.isFinite(s.value ?? s.areaPx));
  const value = s => s.value ?? s.areaPx;
  const tidal = clean.filter(s => s.phase === "tidal");
  const tidalValues = tidal.map(value);
  const raw = rawSamples.map(s => s.areaPx ?? s.value).filter(Number.isFinite);
  const residuals = clean.map((s,i) => Math.abs(value(s) - (rawSamples[i]?.areaPx ?? rawSamples[i]?.value ?? value(s))));
  const noise = median(residuals) * 1.4826;
  const spread = tidalValues.length ? Math.max(...tidalValues)-Math.min(...tidalValues) : 0;

  const extrema = detectPeaksAndTroughs(tidalValues, {
    minDistance: Math.max(2, Math.round(fps * .6)), prominence: Math.max(spread*.08, noise*3, 1e-6),
  });
  const peaks = extrema.filter(p => p.type === "peak");
  const periods = peaks.slice(1).map((p,i) => (tidal[p.index].elapsedMs-tidal[peaks[i].index].elapsedMs)/1000).filter(p => p > 0);
  const amplitudes = [];
  for (let i=1; i<peaks.length; i++) {
    const a=peaks[i-1], b=peaks[i];
    const section=tidalValues.slice(a.index+1,b.index);
    if (section.length) amplitudes.push((a.value+b.value)/2-Math.min(...section));
  }

  const vtPx = amplitudes.length ? median(amplitudes) : null;
  const tidalCycles = amplitudes.length;
  const cv = vtPx ? Math.sqrt(amplitudes.reduce((n,v)=>n+(v-vtPx)**2,0)/amplitudes.length)/vtPx : null;
  const n=Math.max(1,Math.round(fps));
  const drift=tidalValues.length ? Math.abs(median(tidalValues.slice(-n))-median(tidalValues.slice(0,n))) : null;
  const inhale=clean.filter(s=>["maxInhale","exhalePrep"].includes(s.phase));
  const exhale=clean.filter(s=>s.phase==="maxExhale");
  const high=supportedLevel(inhale,value,"high");
  const low=supportedLevel(exhale,value,"low");
  const inhaleLevel=high?.level ?? null, exhaleLevel=low?.level ?? null;
  const vcPx=high&&low ? Math.abs(high.level-low.level) : null;
  const ratio=vtPx&&vcPx!==null ? vcPx/vtPx : null;
  const vtReasons=[], vcReasons=[], vtWarnings=[], vcWarnings=[];

  if(tidalCycles<2) vtReasons.push("insufficient_complete_tidal_cycles");
  if(!vtPx || vtPx<=Math.max(noise*4,1e-6)) vtReasons.push("invalid_tidal_area");
  if(cv>.5) vtReasons.push("severely_inconsistent_tidal_amplitudes");
  else if(cv>.3) vtWarnings.push("variable_tidal_amplitudes");
  if(vtPx && drift>vtPx*2) vtWarnings.push("tidal_baseline_drift");
  if(!vcPx || vcPx<=Math.max(noise*6,1e-6)) vcReasons.push("invalid_vital_area");
  if(high && low && high.level <= low.level) vcReasons.push("reversed_vital_levels");
  if(vcPx!==null && vtPx && vcPx<=vtPx) vcReasons.push("vital_not_greater_than_tidal");
  const physicalLimit=roiPixels || sourceSamples.find(s=>s.roi?.width)?.roi?.width * sourceSamples.find(s=>s.roi?.width)?.roi?.height || null;
  if(physicalLimit && raw.some(v=>v<0||v>physicalLimit)) { vtReasons.push("area_exceeds_roi"); vcReasons.push("area_exceeds_roi"); }
  const sorted=[...sourceSamples].sort((a,b)=>a.elapsedMs-b.elapsedMs);
  const gaps=sorted.slice(1).map((s,i)=>s.elapsedMs-sorted[i].elapsedMs);
  for(const phase of ["tidal","maxInhale","maxExhale"]) {
    const group=sorted.filter(s=>s.phase===phase);
    const window=phaseWindows[phase];
    const boundaries=window ? [window[0]*1000,...group.map(s=>s.elapsedMs),window[1]*1000] : group.map(s=>s.elapsedMs);
    // Timestamp coverage matters; assuming the resampling target is the camera
    // FPS falsely rejected otherwise complete 10–15 fps mobile recordings.
    const bad=group.length<3 || boundaries.some((ms,i)=>i>0&&ms-boundaries[i-1]>500);
    if(bad) (phase==="tidal"?vtReasons:vcReasons).push("incomplete_"+phase);
  }
  const rrHz=periods.length ? 1/median(periods) : null;
  const rrValid=tidalCycles>=minimumTidalCycles && rrHz!==null && !vtReasons.length;
  const vtValid=!vtReasons.length, vcValid=!vcReasons.length, ratioValid=vtValid&&vcValid;
  const invalidReasons=[...new Set([...vtReasons,...vcReasons])];
  const qualityWarnings=[...new Set([...vtWarnings,...vcWarnings])];
  return {
    algorithmVersion:"polarity-contour-amplitude-v4",valid:ratioValid,vtValid,vcValid,ratioValid,rrValid,
    vtPx:vtValid?vtPx:null,vcPx:vcValid?vcPx:null,ratio:ratioValid?ratio:null,
    rrHz:rrValid?rrHz:null,rrBpm:rrValid?rrHz*60:null,confidence:null,
    qualityStatus:!ratioValid?"review_required":qualityWarnings.length?"usable_with_caution":"checks_passed",invalidReasons,qualityWarnings,
    rrInvalidReasons:rrValid?[]:["insufficient_tidal_cycles"],extrema,
    diagnostic:{vtPx,vcPx,ratio,rrHz,tidalCycles,inhaleLevel,exhaleLevel,physicalLimit,
      tidalAmplitudes:amplitudes,tidalCv:cv,tidalDriftPx:drift,noisePx:noise,
      maxGapMs:gaps.length?Math.max(...gaps):null,vtReasons,vcReasons,vtWarnings,vcWarnings,
      inhaleMs:high?.ms ?? null,exhaleMs:low?.ms ?? null},
  };
}

function supportedLevel(samples,value,direction) {
  if(samples.length<3 || samples.at(-1).elapsedMs-samples[0].elapsedMs<400) return null;
  const candidates=samples.map(s=>{
    const local=samples.filter(p=>Math.abs(p.elapsedMs-s.elapsedMs)<=250);
    return {level:median(local.map(value)),ms:s.elapsedMs,span:local.at(-1).elapsedMs-local[0].elapsedMs};
  }).filter(p=>p.span>=400);
  if(!candidates.length) return null;
  return candidates.reduce((a,b)=>direction==="high"?(b.level>a.level?b:a):(b.level<a.level?b:a));
}
function median(values) {
  if(!values.length) return 0;
  const v=[...values].sort((a,b)=>a-b), m=Math.floor(v.length/2);
  return v.length%2?v[m]:(v[m-1]+v[m])/2;
}

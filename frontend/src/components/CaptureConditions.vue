<template>
  <section class="capture-conditions" aria-labelledby="conditions-title">
    <h3 id="conditions-title">Set up for a repeatable measurement</h3>
    <p>The camera measures a steady setup matter.</p>
    <div class="condition-grid">
      <article>
        <svg viewBox="0 0 150 65" role="img" aria-label="Dark fitted top on light background, or light fitted top on dark background">
          <rect x="1" y="1" width="70" height="62" rx="8" fill="#eee"/><rect x="79" y="1" width="70" height="62" rx="8" fill="#26333b"/>
          <path d="M24 12 12 22 20 33 25 28 24 54 49 54 48 28 53 33 61 22 49 12 43 17 30 17Z" fill="#26333b"/>
          <path d="M102 12 90 22 98 33 103 28 102 54 127 54 126 28 131 33 139 22 127 12 121 17 108 17Z" fill="#fafafa"/>
        </svg>
        <b>01 · Fitted, contrasting top</b><p>Wear a close-fitting, plain top. Dark on a light wall or light on a dark wall both work. Avoid loose sleeves, folds, and similar clothing/background colors.</p>
      </article>
      <article><span class="condition-icon" aria-hidden="true">☀</span><b>02 · Clear, even light</b><p>Light your torso from the front or side. Avoid backlight, moving shadows, flickering screens, and clipped white clothing. Clean the lens.</p></article>
      <article><svg viewBox="0 0 150 65" aria-hidden="true"><rect x="51" y="5" width="48" height="29" rx="5" fill="none" stroke="currentColor" stroke-width="3"/><circle cx="75" cy="19" r="8" fill="none" stroke="currentColor" stroke-width="3"/><path d="M75 35V58M75 35 53 59M75 35 97 59" stroke="currentColor" stroke-width="3"/></svg><b>03 · Fix the camera</b><p>Use a stand at torso height, no handheld filming or zoom changes. Fill the guide with your chest and waist; keep the whole breathing edge visible.</p></article>
      <article><span class="condition-icon" aria-hidden="true">↕</span><b>04 · Stay side-on</b><p>Settle before confirming Position. Keep feet, hips, shoulders and arms still; do not lean, talk, or turn your head during capture. Reposition if the outline leaves the box.</p></article>
      <article><svg viewBox="0 0 150 65" aria-hidden="true"><path d="M5 36Q15 12 25 36T45 36T65 36T85 36T105 36T125 36T145 36" fill="none" stroke="currentColor" stroke-width="3"/></svg><b>05 · Natural breathing first</b><p>Keep your normal comfortable rhythm; do not speed up or deliberately make breaths smaller. Prepare on the spoken cue, then begin the full inhale or exhale on the bell. Stop if uncomfortable.</p></article>
      <article><span class="condition-icon" aria-hidden="true">720p+</span><b>06 · Check capture quality</b><p>Use a clear HD source where available. Close heavy apps. Low light can lower camera FPS. Compare the same camera, distance, clothing and posture across tests; HD alone does not guarantee reliability.</p></article>
    </div>
    <p class="condition-note">A rejected result may come from capture or software limitations. It is not a judgment about your breathing. Keep the recording and export diagnostics for review.</p>
  </section>
</template>
<style scoped>
.capture-conditions { margin-top:24px; } h3 { margin:0 0 8px; } .capture-conditions > p { color:var(--ink-soft); line-height:1.6; }
.condition-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin:16px 0; }
article { border:1px solid var(--rule); border-radius:8px; padding:16px; background:var(--paper); display:flex; flex-direction:column; gap:10px; }
svg,.condition-icon { width:150px; max-width:100%; height:65px; color:#16704a; align-self:center; }
.condition-icon { display:grid; place-items:center; font:600 26px system-ui; }
b { font-size:14px; } article p { margin:0; color:var(--ink-soft); font-size:13px; line-height:1.6; }.condition-note { padding:12px; border-left:3px solid #16704a; }
@media(max-width:800px) { .condition-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media(max-width:480px) { .condition-grid { grid-template-columns:1fr; } }
</style>

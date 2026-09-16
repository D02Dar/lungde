<template><aside class="panel fixture-panel"><div class="panel-head">
    <div>
        <h2>Position fixture</h2>
    <p>The same upper-body box is used throughout measurement.</p>
    </div></div>
    <div class="panel-body">
        <BodyPositionFigure compact title="Side-on, steady back, clear chest" caption="The enclosed silhouette drives the Realtime path; the offline motion ROI stays inside this box."/>

        <ol class="fixture-steps"><li>
            <b>1</b>

    <span>Keep the camera roughly level with the chest.</span></li><li><b>2</b><span>Include the head, shoulders, chest, and waist.</span></li><li><b>3</b>

    <span>The box freezes after confirmation; do not adjust it during measurement.</span></li></ol></div></aside></template>
    <script setup>import BodyPositionFigure from'./BodyPositionFigure.vue';</script>

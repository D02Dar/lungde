<template>
  <Teleport to="body">
    <Transition name="guide-overlay">
      <div v-if="visible" class="position-guide-overlay" @click="$emit('close')">
        <section class="position-guide-card measurement-tutorial-card" @click.stop>
          <button class="guide-close" type="button" aria-label="Close tutorial" @click="$emit('close')">
            <PhX :size="22" weight="bold" />
          </button>

          <div class="tutorial-content">
            <header class="tutorial-header">
              <p class="eyebrow">Breathing measurement guide</p>
              <h2>How the measurement works</h2>
              <p>This measurement tracks the side-view chest outline as a pixel-area proxy. Match the Guide conditions and follow the actual capture sequence below.</p>
            </header>

            <div class="tutorial-steps">
              <article v-for="(step, index) in steps" :key="step.key" class="tutorial-step">
                <span class="step-number">{{ index + 1 }}</span>
                <div class="step-content">
                  <h3>{{ step.title }}</h3>
                  <p class="step-description">{{ step.description }}</p>
                  <p v-if="step.duration" class="step-duration">{{ step.duration }}</p>
                </div>
              </article>
            </div>

            <aside class="tutorial-notes">
              <h3>Important reminders</h3>
              <ul>
                <li><strong>Voice means prepare; bell means begin.</strong> Do not start the maximum manoeuvre during the spoken preparation.</li>
                <li><strong>Breathe naturally.</strong> Do not deliberately alter normal-breathing frequency or depth to influence the ratio.</li>
                <li><strong>Keep shoulders relaxed.</strong> Shoulder movement or torso rotation will affect the measurement.</li>
                <li><strong>Stay in frame.</strong> Keep your upper body visible throughout the sequence.</li>
                <li><strong>This is a motion proxy.</strong> Results reflect chest displacement, not actual lung volume.</li>
              </ul>
            </aside>

            <div class="tutorial-actions">
              <button class="btn btn-primary" type="button" @click="$emit('close')">Got it</button>
            </div>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { PhX } from '@phosphor-icons/vue';

defineProps({ visible: Boolean });
defineEmits(['close']);

const steps = [
  {
    key: 'prepare',
    title: 'Prepare',
    description: 'Stand side-on, settle your feet and hips, relax your shoulders, and keep the fitted shirt edge visible.',
    duration: '3 seconds',
  },
  {
    key: 'tidal',
    title: 'Normal breathing',
    description: 'Breathe at your natural comfortable pace without talking, leaning, or deliberately changing depth.',
    duration: '12 seconds',
  },
  {
    key: 'inhalePrep',
    title: 'Prepare to inhale',
    description: 'The voice announces the next action. Get ready, but wait for the bell.',
    duration: '3 seconds',
  },
  {
    key: 'inhale',
    title: 'Full inhale',
    description: 'Breathe in slowly and fully until your chest is comfortably expanded.',
    duration: '8 seconds',
  },
  {
    key: 'exhalePrep',
    title: 'Prepare to exhale',
    description: 'The voice announces the next action. Keep the end position and wait for the bell.',
    duration: '3 seconds',
  },
  {
    key: 'slowExhale',
    title: 'Slow exhale',
    description: 'Breathe out slowly and fully until your chest naturally settles.',
    duration: '8 seconds',
  },
  {
    key: 'finish',
    title: 'Complete',
    description: 'Measurement complete. Resume normal breathing.',
    duration: null,
  },
];
</script>

<style scoped>
.measurement-tutorial-card {
  max-width: 640px;
  max-height: 90vh;
  overflow-y: auto;
}

.tutorial-content {
  display: flex;
  flex-direction: column;
  gap: 32px;
  padding: 32px;
}

.tutorial-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tutorial-header .eyebrow {
  font-size: var(--step--1);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--ink-soft);
  margin: 0;
}

.tutorial-header h2 {
  font-size: var(--step-2);
  font-weight: 600;
  line-height: 1.2;
  margin: 0;
}

.tutorial-header > p {
  color: var(--ink-soft);
  line-height: 1.5;
  margin: 0;
}

.tutorial-steps {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.tutorial-step {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.step-number {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--instrument);
  color: var(--panel);
  font-weight: 600;
  font-size: var(--step--1);
  font-family: var(--mono);
}

.step-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.step-content h3 {
  font-size: var(--step-0);
  font-weight: 600;
  margin: 0;
  line-height: 1.4;
}

.step-description {
  color: var(--ink-soft);
  line-height: 1.5;
  margin: 0;
}

.step-duration {
  font-size: var(--step--1);
  color: var(--ink-softer);
  font-family: var(--mono);
  margin: 0;
}

.tutorial-notes {
  padding: 20px;
  background: var(--paper-tint);
  border-radius: 8px;
  border: 1px solid var(--rule);
}

.tutorial-notes h3 {
  font-size: var(--step-0);
  font-weight: 600;
  margin: 0 0 12px;
}

.tutorial-notes ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tutorial-notes li {
  padding-left: 20px;
  position: relative;
  line-height: 1.5;
  color: var(--ink-soft);
}

.tutorial-notes li::before {
  content: "•";
  position: absolute;
  left: 6px;
  color: var(--instrument);
  font-weight: bold;
}

.tutorial-notes li strong {
  color: var(--ink);
  font-weight: 600;
}

.tutorial-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
}

.tutorial-actions .btn {
  min-width: 140px;
}

@media (max-width: 640px) {
  .tutorial-content {
    padding: 24px;
    gap: 24px;
  }

  .tutorial-header h2 {
    font-size: var(--step-1);
  }

  .tutorial-steps {
    gap: 16px;
  }

  .step-number {
    width: 28px;
    height: 28px;
  }
}
</style>

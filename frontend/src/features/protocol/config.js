"use strict";

export const protocol = [
  { key: "countdown", label: "Ready", action: "Get ready", detail: "Stand side-on, relax your shoulders, and keep your body still.", seconds: 3, prompt: "Stand side-on, relax your shoulders, and keep your body still.", voice: "Get ready. Keep still." },
  { key: "tidal", label: "Normal breathing", action: "Breathe normally", detail: "Breathe naturally at a comfortable pace.", seconds: 12, prompt: "Breathe normally at your natural pace.", voice: "Breathe normally." },
  { key: "inhalePrep", label: "Prepare to inhale", action: "Get ready to breathe in", detail: "After the bell, breathe in for 8 seconds.", seconds: 3, prompt: "After the bell, breathe in for 8 seconds.", voice: "Next, breathe in for eight seconds.", beep: false },
  { key: "maxInhale", label: "Full inhale", action: "Breathe in fully", detail: "Breathe in slowly until your chest is comfortably expanded.", seconds: 8, prompt: "Breathe in slowly and fully.", voice: "", followupCues: [{ atSeconds: 5, voice: "Keep going." }, { atSeconds: 6.5, voice: "Keep going." }] },
  { key: "exhalePrep", label: "Prepare to exhale", action: "Get ready to breathe out", detail: "After the bell, breathe out for 8 seconds.", seconds: 3, prompt: "After the bell, breathe out for 8 seconds.", voice: "Next, breathe out for eight seconds.", beep: false },
  { key: "maxExhale", label: "Slow exhale", action: "Breathe out fully", detail: "Breathe out slowly and evenly until your chest naturally settles.", seconds: 8, prompt: "Breathe out slowly and fully.", voice: "", followupCues: [{ atSeconds: 5, voice: "Keep going." }, { atSeconds: 6.5, voice: "Keep going." }] },
];

export const stages = [
  { key: "guide", label: "Guide" },
  { key: "mark", label: "Position" },
  { key: "measure", label: "Measure" },
];

export function phaseLabel(key) {
  return protocol.find((step) => step.key === key)?.label || key || "Waiting";
}

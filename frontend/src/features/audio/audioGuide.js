"use strict";

export class AudioGuide {
  constructor({ voiceEnabled = () => true, beepEnabled = () => true, lang = "en-US" } = {}) {
    this.voiceEnabled = voiceEnabled; this.beepEnabled = beepEnabled; this.lang = lang; this.context = null; this.lastSpeech = null;
  }
  initialise() {
    if (!this.context) { const AudioContextCtor = window.AudioContext || window.webkitAudioContext; if (AudioContextCtor) this.context = new AudioContextCtor(); }
    if (this.context?.state === "suspended") this.context.resume();
  }
  beep(frequency = 880, durationMs = 140, gainValue = 0.07) {
    if (!this.beepEnabled() || !this.context) return;
    const oscillator = this.context.createOscillator(); const gain = this.context.createGain();
    oscillator.frequency.value = frequency; oscillator.type = "sine";
    gain.gain.setValueAtTime(0.0001, this.context.currentTime); gain.gain.exponentialRampToValueAtTime(gainValue, this.context.currentTime + 0.015); gain.gain.exponentialRampToValueAtTime(0.0001, this.context.currentTime + durationMs / 1000);
    oscillator.connect(gain); gain.connect(this.context.destination); oscillator.start(); oscillator.stop(this.context.currentTime + durationMs / 1000 + 0.02);
  }
  speak(text, { key = text, minIntervalMs = 2500 } = {}) {
    if (!this.voiceEnabled() || !window.speechSynthesis || !text) return false;
    const now = performance.now(); if (this.lastSpeech?.key === key && now - this.lastSpeech.at < minIntervalMs) return false;
    this.lastSpeech = { key, at: now }; window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text); utterance.lang = this.lang; utterance.rate = 0.95; utterance.pitch = 1;
    window.speechSynthesis.speak(utterance); return true;
  }
  cancel() { window.speechSynthesis?.cancel?.(); this.lastSpeech = null; }
}

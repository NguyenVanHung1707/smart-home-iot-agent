export const DEFAULT_SILENCE_MS = 2_000;
// ponytail: RMS works for normal rooms; tune this knob or use streaming
// Silero VAD when persistent background noise makes energy detection unreliable.
export const DEFAULT_SPEECH_THRESHOLD = 0.018;
export const DEFAULT_MIN_SPEECH_MS = 120;

type VoiceActivityOptions = {
  silenceMs?: number;
  speechThreshold?: number;
  minSpeechMs?: number;
};

function rms(samples: Float32Array) {
  if (!samples.length) return 0;
  let sum = 0;
  for (const sample of samples) sum += sample * sample;
  return Math.sqrt(sum / samples.length);
}

export class VoiceActivityDetector {
  private readonly silenceMs: number;
  private readonly speechThreshold: number;
  private readonly minSpeechMs: number;
  private candidateSpeechMs = 0;
  private lastSpeechAt = 0;
  private speechStarted = false;
  private silenceTriggered = false;

  constructor(options: VoiceActivityOptions = {}) {
    this.silenceMs = options.silenceMs ?? DEFAULT_SILENCE_MS;
    this.speechThreshold = options.speechThreshold ?? DEFAULT_SPEECH_THRESHOLD;
    this.minSpeechMs = options.minSpeechMs ?? DEFAULT_MIN_SPEECH_MS;
  }

  update(samples: Float32Array, nowMs: number, frameMs: number) {
    if (this.silenceTriggered) return false;
    if (rms(samples) >= this.speechThreshold) {
      this.candidateSpeechMs += frameMs;
      this.lastSpeechAt = nowMs;
      this.speechStarted ||= this.candidateSpeechMs >= this.minSpeechMs;
      return false;
    }
    if (!this.speechStarted) {
      this.candidateSpeechMs = 0;
      return false;
    }
    if (nowMs - this.lastSpeechAt < this.silenceMs) return false;
    this.silenceTriggered = true;
    return true;
  }
}

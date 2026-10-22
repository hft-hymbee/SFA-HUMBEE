type FeedbackCue = "notification" | "punchIn" | "punchOut";

type Tone = {
  frequency: number;
  durationMs: number;
  atMs: number;
  gain?: number;
  type?: OscillatorType;
};

const CUES: Record<FeedbackCue, Tone[]> = {
  notification: [
    { frequency: 880, durationMs: 80, atMs: 0, gain: 0.1 },
    { frequency: 1175, durationMs: 140, atMs: 105, gain: 0.12 },
  ],
  punchIn: [
    { frequency: 523, durationMs: 90, atMs: 0, gain: 0.13, type: "triangle" },
    { frequency: 659, durationMs: 90, atMs: 95, gain: 0.13, type: "triangle" },
    { frequency: 784, durationMs: 170, atMs: 190, gain: 0.16, type: "triangle" },
  ],
  punchOut: [
    { frequency: 698, durationMs: 100, atMs: 0, gain: 0.13, type: "triangle" },
    { frequency: 523, durationMs: 190, atMs: 115, gain: 0.16, type: "triangle" },
  ],
};

let audioContext: AudioContext | null = null;
let unlockBound = false;
let lastUnreadActorId = "";
let lastUnreadCount: number | undefined;

function prefersReducedMotion() {
  return typeof window !== "undefined"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function getAudioContext() {
  if (typeof window === "undefined") return null;
  const AudioContextCtor = window.AudioContext ?? (window as typeof window & {
    webkitAudioContext?: typeof AudioContext;
  }).webkitAudioContext;
  if (!AudioContextCtor) return null;
  audioContext ??= new AudioContextCtor();
  return audioContext;
}

function bindAudioUnlock() {
  if (typeof window === "undefined" || unlockBound) return;
  unlockBound = true;
  const unlock = () => {
    const context = getAudioContext();
    if (context?.state === "suspended") {
      void context.resume();
    }
  };
  window.addEventListener("pointerdown", unlock, { passive: true });
  window.addEventListener("keydown", unlock);
}

function playTones(tones: Tone[]) {
  bindAudioUnlock();
  const context = getAudioContext();
  if (!context) return;
  if (context.state === "suspended") {
    void context.resume();
  }
  const now = context.currentTime;
  for (const tone of tones) {
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = tone.type ?? "sine";
    oscillator.frequency.value = tone.frequency;
    const peak = tone.gain ?? 0.12;
    const start = now + tone.atMs / 1000;
    const end = start + tone.durationMs / 1000;
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(peak, start + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, Math.max(start + 0.02, end));
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start(start);
    oscillator.stop(end + 0.02);
  }
}

export function vibrate(pattern: VibratePattern) {
  if (typeof navigator === "undefined" || !navigator.vibrate) return;
  if (pattern !== 0 && prefersReducedMotion()) return;
  navigator.vibrate(pattern);
}

export function playFeedback(cue: FeedbackCue) {
  playTones(CUES[cue]);
}

export function noteUnreadCount(actorId: string, count: number) {
  bindAudioUnlock();
  if (!actorId) return;
  if (actorId !== lastUnreadActorId) {
    lastUnreadActorId = actorId;
    lastUnreadCount = count;
    return;
  }
  if (lastUnreadCount === undefined) {
    lastUnreadCount = count;
    return;
  }
  if (count > lastUnreadCount) {
    playFeedback("notification");
  }
  lastUnreadCount = count;
}

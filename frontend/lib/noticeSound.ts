"use client";

type NoticeSoundType = "success" | "error" | "loading" | "blank" | "custom";

type Tone = {
  frequency: number;
  start: number;
  duration: number;
  volume?: number;
  wave?: OscillatorType;
};

let audioContext: AudioContext | null = null;

const getAudioContext = () => {
  if (typeof window === "undefined") return null;

  const AudioContextClass =
    window.AudioContext ??
    (window as Window & typeof globalThis & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioContextClass) return null;

  audioContext ??= new AudioContextClass();
  return audioContext;
};

export const unlockNoticeAudio = () => {
  const context = getAudioContext();
  if (!context || context.state !== "suspended") return;
  context.resume().catch(() => undefined);
};

const scheduleTone = (context: AudioContext, destination: AudioNode, tone: Tone, masterVolume: number) => {
  const now = context.currentTime;
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  const startAt = now + tone.start;
  const endAt = startAt + tone.duration;
  const peak = Math.min(0.95, Math.max(0.05, (tone.volume ?? 1) * masterVolume));

  oscillator.type = tone.wave ?? "sine";
  oscillator.frequency.setValueAtTime(tone.frequency, startAt);
  gain.gain.setValueAtTime(0.0001, startAt);
  gain.gain.exponentialRampToValueAtTime(peak, startAt + 0.012);
  gain.gain.exponentialRampToValueAtTime(0.0001, endAt);

  oscillator.connect(gain);
  gain.connect(destination);
  oscillator.start(startAt);
  oscillator.stop(endAt + 0.02);
};

const tonesByType: Record<NoticeSoundType, { volume: number; tones: Tone[] }> = {
  success: {
    volume: 0.9,
    tones: [
      { frequency: 660, start: 0, duration: 0.1 },
      { frequency: 880, start: 0.08, duration: 0.11 },
      { frequency: 1320, start: 0.17, duration: 0.16 },
    ],
  },
  error: {
    volume: 0.95,
    tones: [
      { frequency: 880, start: 0, duration: 0.16, wave: "square" },
      { frequency: 440, start: 0.13, duration: 0.18, wave: "sawtooth" },
      { frequency: 220, start: 0.29, duration: 0.22, wave: "square" },
    ],
  },
  loading: {
    volume: 0.74,
    tones: [
      { frequency: 520, start: 0, duration: 0.08 },
      { frequency: 660, start: 0.09, duration: 0.09 },
    ],
  },
  custom: {
    volume: 0.72,
    tones: [
      { frequency: 740, start: 0, duration: 0.1 },
      { frequency: 560, start: 0.1, duration: 0.08 },
    ],
  },
  blank: {
    volume: 0.72,
    tones: [{ frequency: 620, start: 0, duration: 0.11 }],
  },
};

export const playNoticeSound = (type: NoticeSoundType) => {
  const context = getAudioContext();
  if (!context) return;

  const play = () => {
    const preset = tonesByType[type] ?? tonesByType.blank;
    const compressor = context.createDynamicsCompressor();
    compressor.threshold.value = -18;
    compressor.knee.value = 8;
    compressor.ratio.value = 12;
    compressor.attack.value = 0.003;
    compressor.release.value = 0.18;
    compressor.connect(context.destination);

    preset.tones.forEach((tone) => scheduleTone(context, compressor, tone, preset.volume));
    window.setTimeout(() => compressor.disconnect(), 900);
  };

  if (context.state === "suspended") {
    context.resume().then(play).catch(() => undefined);
    return;
  }

  play();
};

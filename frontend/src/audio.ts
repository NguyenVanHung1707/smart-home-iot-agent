import {
  DEFAULT_MIN_SPEECH_MS,
  DEFAULT_SILENCE_MS,
  DEFAULT_SPEECH_THRESHOLD,
  VoiceActivityDetector,
} from "./vad";

const TARGET_SAMPLE_RATE = 16_000;

type RecorderOptions = {
  onSilence?: () => void;
  silenceMs?: number;
  speechThreshold?: number;
  minSpeechMs?: number;
};

function mergeChunks(chunks: Float32Array[]) {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const merged = new Float32Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return merged;
}

function resample(input: Float32Array, sourceRate: number) {
  if (sourceRate === TARGET_SAMPLE_RATE) return input;
  const ratio = sourceRate / TARGET_SAMPLE_RATE;
  const output = new Float32Array(Math.round(input.length / ratio));
  for (let index = 0; index < output.length; index += 1) {
    const start = Math.floor(index * ratio);
    const end = Math.min(input.length, Math.floor((index + 1) * ratio));
    let sum = 0;
    for (let cursor = start; cursor < end; cursor += 1) sum += input[cursor];
    output[index] = sum / Math.max(1, end - start);
  }
  return output;
}

export function encodePcmWav(samples: Float32Array, sampleRate = TARGET_SAMPLE_RATE) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeAscii = (offset: number, value: string) => {
    for (let index = 0; index < value.length; index += 1) view.setUint8(offset + index, value.charCodeAt(index));
  };

  writeAscii(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeAscii(8, "WAVE");
  writeAscii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, index) => {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + index * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  });
  return new Blob([buffer], { type: "audio/wav" });
}

export class BrowserWavRecorder {
  private constructor(
    private readonly context: AudioContext,
    private readonly stream: MediaStream,
    private readonly source: MediaStreamAudioSourceNode,
    private readonly processor: ScriptProcessorNode,
    private readonly chunks: Float32Array[],
  ) {}

  static async start({
    onSilence,
    silenceMs = DEFAULT_SILENCE_MS,
    speechThreshold = DEFAULT_SPEECH_THRESHOLD,
    minSpeechMs = DEFAULT_MIN_SPEECH_MS,
  }: RecorderOptions = {}) {
    if (!window.isSecureContext) {
      throw new Error("Microphone cần HTTPS hoặc truy cập qua localhost.");
    }
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("Trình duyệt không hỗ trợ thu âm microphone.");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 }, video: false });
    } catch (error) {
      if (error instanceof DOMException && error.name === "NotAllowedError") {
        throw new Error("Microphone đang bị chặn. Hãy cấp quyền rồi thử lại.");
      }
      if (error instanceof DOMException && error.name === "NotFoundError") {
        throw new Error("Không tìm thấy microphone trên thiết bị này.");
      }
      throw error;
    }
    const context = new AudioContext();
    await context.resume();
    const source = context.createMediaStreamSource(stream);
    const processor = context.createScriptProcessor(4096, 1, 1);
    const chunks: Float32Array[] = [];
    const vad = new VoiceActivityDetector({ silenceMs, speechThreshold, minSpeechMs });
    processor.onaudioprocess = (event) => {
      const samples = new Float32Array(event.inputBuffer.getChannelData(0));
      chunks.push(samples);
      const frameMs = (samples.length / context.sampleRate) * 1_000;
      if (onSilence && vad.update(samples, performance.now(), frameMs)) queueMicrotask(onSilence);
    };
    source.connect(processor);
    processor.connect(context.destination);
    return new BrowserWavRecorder(context, stream, source, processor, chunks);
  }

  async stop() {
    const sourceRate = this.context.sampleRate;
    this.source.disconnect();
    this.processor.disconnect();
    this.processor.onaudioprocess = null;
    this.stream.getTracks().forEach((track) => track.stop());
    await this.context.close();
    const pcm = resample(mergeChunks(this.chunks), sourceRate);
    if (!pcm.length) throw new Error("Không thu được dữ liệu âm thanh.");
    return encodePcmWav(pcm);
  }

  cancel() {
    this.source.disconnect();
    this.processor.disconnect();
    this.processor.onaudioprocess = null;
    this.stream.getTracks().forEach((track) => track.stop());
    void this.context.close();
  }
}

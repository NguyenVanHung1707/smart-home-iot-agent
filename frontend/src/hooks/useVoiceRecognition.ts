import { useEffect, useRef, useState } from "react";
import { BrowserWavRecorder } from "../audio";
import { synthesizeVoice, transcribeAudio } from "../api/client";
import type {
  SpeechRecognitionLike,
  SpeechRecognitionWindow,
  VoiceMode,
  VoiceState,
} from "../types";

const emptyVoiceState: VoiceState = {
  open: false,
  mode: "command",
  listening: false,
  error: "",
  finalTranscript: "",
  interimTranscript: "",
};

export function useVoiceRecognition() {
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const wavRecorderRef = useRef<BrowserWavRecorder | null>(null);
  const recordingTimerRef = useRef<number | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  const [voice, setVoice] = useState<VoiceState>(emptyVoiceState);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
      recognitionRef.current = null;
      if (recordingTimerRef.current !== null) {
        window.clearTimeout(recordingTimerRef.current);
      }
      wavRecorderRef.current?.cancel();
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
      }
    };
  }, []);

  function openVoice(mode: VoiceMode = "command") {
    setVoice({ ...emptyVoiceState, open: true, mode });
  }

  function stopVoice() {
    if (recordingTimerRef.current !== null) {
      window.clearTimeout(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    wavRecorderRef.current?.cancel();
    wavRecorderRef.current = null;
    setVoice((current) => ({ ...current, listening: false }));
    setAudioLevel(0);
  }

  function closeVoice() {
    stopVoice();
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
      setIsPlayingAudio(false);
    }
    setVoice((current) => ({ ...current, open: false, finalTranscript: "", interimTranscript: "" }));
  }

  function resetTranscript() {
    setVoice((current) => ({ ...current, finalTranscript: "", interimTranscript: "" }));
  }

  function stopSpeaking() {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setIsPlayingAudio(false);
  }

  function fallbackBrowserSpeech(cleanText: string): number {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      setIsPlayingAudio(false);
      return 0;
    }
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(cleanText);
      utterance.lang = "vi-VN";
      utterance.rate = 1.05;
      const voices = window.speechSynthesis.getVoices();
      const viVoice = voices.find((v) => v.lang.toLowerCase().includes("vi"));
      if (viVoice) {
        utterance.voice = viVoice;
      }
      utterance.onstart = () => setIsPlayingAudio(true);
      utterance.onend = () => setIsPlayingAudio(false);
      utterance.onerror = () => setIsPlayingAudio(false);
      window.speechSynthesis.speak(utterance);
      return 50;
    } catch {
      setIsPlayingAudio(false);
      return 0;
    }
  }

  async function speak(text: string, force = false): Promise<number> {
    if ((!ttsEnabled && !force) || !text.trim()) return 0;
    stopSpeaking();

    // Làm sạch ký tự markdown và định dạng để giọng đọc tự nhiên
    const cleanSpeakText = text
      .replace(/[*_#`~[\]]/g, " ")
      .replace(/https?:\/\/\S+/g, "")
      .replace(/°C/g, " độ C")
      .replace(/%/g, " phần trăm")
      .replace(/\s+/g, " ")
      .trim();

    if (!cleanSpeakText) {
      setIsPlayingAudio(false);
      return 0;
    }

    setIsPlayingAudio(true);

    try {
      const { audioUrl, latencyMs } = await synthesizeVoice(cleanSpeakText);
      const audio = new Audio(audioUrl);
      currentAudioRef.current = audio;
      audio.addEventListener("ended", () => {
        URL.revokeObjectURL(audioUrl);
        setIsPlayingAudio(false);
        currentAudioRef.current = null;
      }, { once: true });
      audio.addEventListener("error", () => {
        URL.revokeObjectURL(audioUrl);
        currentAudioRef.current = null;
        fallbackBrowserSpeech(cleanSpeakText);
      }, { once: true });
      await audio.play();
      return latencyMs;
    } catch {
      return fallbackBrowserSpeech(cleanSpeakText);
    }
  }

  async function startWavRecording(onComplete: (transcript: string) => void) {
    try {
      wavRecorderRef.current = await BrowserWavRecorder.start({
        onSilence: async () => {
          if (!wavRecorderRef.current) return;
          const recorder = wavRecorderRef.current;
          wavRecorderRef.current = null;
          setVoice((cur) => ({ ...cur, listening: false }));
          try {
            const wavBlob = await recorder.stop();
            const result = await transcribeAudio(wavBlob);
            setVoice((cur) => ({ ...cur, finalTranscript: result.transcript }));
            if (result.transcript) {
              onComplete(result.transcript);
            }
          } catch (e) {
            setVoice((cur) => ({
              ...cur,
              error: e instanceof Error ? e.message : "Lỗi nhận dạng âm thanh",
            }));
          }
        },
      });

      setVoice((cur) => ({ ...cur, open: true, listening: true, error: "" }));

      // Max recording timer
      recordingTimerRef.current = window.setTimeout(async () => {
        if (!wavRecorderRef.current) return;
        const recorder = wavRecorderRef.current;
        wavRecorderRef.current = null;
        setVoice((cur) => ({ ...cur, listening: false }));
        try {
          const wavBlob = await recorder.stop();
          const result = await transcribeAudio(wavBlob);
          setVoice((cur) => ({ ...cur, finalTranscript: result.transcript }));
          if (result.transcript) {
            onComplete(result.transcript);
          }
        } catch (e) {
          setVoice((cur) => ({
            ...cur,
            error: e instanceof Error ? e.message : "Hết thời gian thu âm",
          }));
        }
      }, 15000);
    } catch (err) {
      setVoice((cur) => ({
        ...cur,
        listening: false,
        error: err instanceof Error ? err.message : "Không thể truy cập microphone.",
      }));
    }
  }

  function toggleVoice(
    mode: VoiceMode = voice.mode,
    onFinalTranscript?: (text: string) => void,
    useAudioWav = false,
  ) {
    if (voice.listening) {
      stopVoice();
      return;
    }

    openVoice(mode);

    if (useAudioWav) {
      void startWavRecording((text) => onFinalTranscript?.(text));
      return;
    }

    const SpeechRecognition =
      (window as SpeechRecognitionWindow).SpeechRecognition ||
      (window as SpeechRecognitionWindow).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      // Fallback to BrowserWavRecorder if available
      void startWavRecording((text) => onFinalTranscript?.(text));
      return;
    }

    const recognition = new SpeechRecognition();
    recognitionRef.current = recognition;
    recognition.lang = "vi-VN";
    recognition.interimResults = true;
    recognition.continuous = false;

    recognition.onstart = () => {
      setVoice((current) => ({ ...current, open: true, mode, listening: true, error: "" }));
    };

    recognition.onresult = (event) => {
      const results = Array.from(event.results);
      const interimText = results
        .filter((result) => !result.isFinal)
        .map((result) => result[0].transcript)
        .join(" ")
        .trim();
      const finalText = results
        .filter((result) => result.isFinal)
        .map((result) => result[0].transcript)
        .join(" ")
        .trim();

      setVoice((current) => ({
        ...current,
        interimTranscript: interimText,
        finalTranscript: finalText || current.finalTranscript,
      }));

      if (finalText) {
        onFinalTranscript?.(finalText);
        recognition.stop();
      }
    };

    recognition.onerror = () => {
      // If Web Speech fails, fallback to wav recorder next time
      setVoice((current) => ({
        ...current,
        listening: false,
        error: "Không nghe rõ câu lệnh. Hãy nói gần micro hơn hoặc nhập tay.",
      }));
    };

    recognition.onend = () => {
      recognitionRef.current = null;
      setVoice((current) => ({ ...current, listening: false }));
    };

    try {
      recognition.start();
    } catch {
      void startWavRecording((text) => onFinalTranscript?.(text));
    }
  }

  return {
    voice,
    ttsEnabled,
    setTtsEnabled,
    isPlayingAudio,
    audioLevel,
    speak,
    stopSpeaking,
    openVoice,
    stopVoice,
    closeVoice,
    resetTranscript,
    toggleVoice,
  };
}

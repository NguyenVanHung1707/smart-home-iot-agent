import { useEffect, useRef } from "react";
import { useDialogFocus } from "../../hooks/useDialogFocus";
import type { ChatMessage, VoiceMode } from "../../types";
import { Icon } from "../shared/Icon";
import { VoiceComposer } from "./VoiceComposer";
import { VoiceFallbackInput } from "./VoiceFallbackInput";
import { VoiceTranscript } from "./VoiceTranscript";

export function VoiceOverlay({
  open,
  mode,
  listening,
  busy,
  error,
  transcript,
  manualValue,
  messages = [],
  latestAssistant = "",
  voiceStatusReady,
  ttsEnabled,
  onClose,
  onStop,
  onToggle,
  onSwitchMode,
  onToggleTts,
  onManualChange,
  onSend,
}: {
  open: boolean;
  mode: VoiceMode;
  listening: boolean;
  busy: boolean;
  error: string;
  transcript: string;
  manualValue: string;
  messages?: ChatMessage[];
  latestAssistant?: string;
  voiceStatusReady: boolean;
  ttsEnabled: boolean;
  onClose: () => void;
  onStop: () => void;
  onToggle: () => void;
  onSwitchMode: (mode: VoiceMode) => void;
  onToggleTts: () => void;
  onManualChange: (value: string) => void;
  onSend: () => void;
}) {
  const dialogRef = useDialogFocus<HTMLElement>(open, onClose);
  const historyBottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (historyBottomRef.current) {
      historyBottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, transcript]);

  if (!open) return null;

  const statusText =
    error ||
    (busy
      ? "Llama AI đang phân tích ý định và lập kế hoạch..."
      : listening
        ? "Đang lắng nghe tiếng Việt (Realtime VAD)..."
        : voiceStatusReady
          ? "Chạm vào biểu tượng micro để bắt đầu nói."
          : "Đang sẵn sàng nhận diện; bạn cũng có thể nhập tay câu lệnh.");

  const canSend = !busy && Boolean(transcript.trim() || manualValue.trim());

  return (
    <div className="hm-voice-overlay" onClick={onClose}>
      <section
        ref={dialogRef}
        className="hm-voice-session"
        role="dialog"
        aria-modal="true"
        aria-labelledby="hm-voice-title"
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="hm-voice-head">
          <button
            className="hm-icon-button"
            type="button"
            onClick={onClose}
            aria-label="Đóng trợ lý giọng nói"
          >
            <Icon name="close" />
          </button>
          <div className="hm-voice-header-info">
            <span className="hm-voice-sub">HOMEMIND LOCAL ASSISTANT</span>
            <strong id="hm-voice-title">
              {mode === "chat" ? "Trò chuyện thông minh" : "Điều khiển nhà bằng giọng nói"}
            </strong>
          </div>
          <button
            className="hm-icon-button danger"
            type="button"
            disabled={!listening}
            onClick={onStop}
            aria-label="Dừng lắng nghe"
          >
            <Icon name="micOff" />
          </button>
        </header>

        {/* Mode & TTS Controls bar */}
        <div className="hm-voice-tabs-bar">
          <div className="hm-voice-mode-tabs">
            <button
              type="button"
              className={`hm-tab-btn ${mode === "command" ? "active" : ""}`}
              onClick={() => onSwitchMode("command")}
            >
              Lệnh thiết bị
            </button>
            <button
              type="button"
              className={`hm-tab-btn ${mode === "chat" ? "active" : ""}`}
              onClick={() => onSwitchMode("chat")}
            >
              Trò chuyện AI
            </button>
          </div>

          <button
            type="button"
            className={`hm-tts-toggle-btn ${ttsEnabled ? "active" : ""}`}
            onClick={onToggleTts}
            title="Bật/Tắt giọng đọc phản hồi Piper TTS"
          >
            <span>TTS: {ttsEnabled ? "BẬT" : "TẮT"}</span>
          </button>
        </div>

        <VoiceComposer
          listening={listening}
          disabled={busy}
          statusText={statusText}
          onToggle={onToggle}
        />

        <VoiceTranscript transcript={transcript} />

        {/* Conversation history thread */}
        <div className="hm-voice-history-scroll" aria-label="Lịch sử tương tác">
          {messages && messages.length > 0 ? (
            <div className="hm-voice-message-list">
              {messages.map((msg, idx) => (
                <div
                  key={msg.id || idx}
                  className={`hm-voice-msg-bubble ${msg.role === "user" ? "user" : "assistant"}`}
                >
                  <div className="hm-voice-msg-header">
                    <span className="hm-voice-msg-sender">
                      <Icon name={msg.role === "user" ? "mic" : "sparkles"} />
                      {msg.role === "user" ? "Bạn (Giọng nói / STT)" : "HomeMind Hub"}
                    </span>
                    <span className="hm-voice-msg-seq">#{idx + 1}</span>
                  </div>
                  <p className="hm-voice-msg-content">{msg.text}</p>
                </div>
              ))}
              <div ref={historyBottomRef} />
            </div>
          ) : latestAssistant ? (
            <div className="hm-voice-last-reply" aria-live="polite">
              <div className="hm-reply-header">
                <Icon name="sparkles" />
                <span>Phản hồi từ HomeMind Hub</span>
              </div>
              <p>{latestAssistant}</p>
            </div>
          ) : (
            <div className="hm-voice-empty-hint">
              <span>Chưa có lịch sử đối thoại trong phiên này. Hãy nói hoặc nhập lệnh để bắt đầu.</span>
            </div>
          )}
        </div>

        <VoiceFallbackInput
          value={manualValue}
          canSend={canSend}
          onChange={onManualChange}
          onSend={onSend}
        />
      </section>
    </div>
  );
}

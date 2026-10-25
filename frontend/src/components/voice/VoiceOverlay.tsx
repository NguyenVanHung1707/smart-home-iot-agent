import { useEffect, useRef } from "react";
import { useDialogFocus } from "../../hooks/useDialogFocus";
import type { ChatMessage, DataMode } from "../../types";
import { Icon } from "../shared/Icon";
import { VoiceComposer } from "./VoiceComposer";
import { VoiceFallbackInput } from "./VoiceFallbackInput";
import { VoiceTranscript } from "./VoiceTranscript";

export interface ScenarioPrompt {
  id: string;
  label: string;
  prompt: string;
  category: string;
  icon: "sparkles" | "sun" | "bulb" | "shield" | "thermo" | "info";
}

export const TEST_SCENARIOS: ScenarioPrompt[] = [
  {
    id: "weather",
    label: "Thời tiết hôm nay",
    prompt: "Dự báo thời tiết ngoài trời hôm nay thế nào?",
    category: "Dự báo",
    icon: "sun",
  },
  {
    id: "energy",
    label: "Tiêu thụ điện năng",
    prompt: "Hôm nay nhà mình tiêu thụ bao nhiêu điện năng?",
    category: "Năng lượng",
    icon: "bulb",
  },
  {
    id: "air",
    label: "Chất lượng không khí",
    prompt: "Chất lượng không khí trong nhà có sạch không?",
    category: "Môi trường",
    icon: "thermo",
  },
  {
    id: "notes",
    label: "Ghi chú gia đình",
    prompt: "Xem danh sách ghi chú",
    category: "Nhắc việc",
    icon: "info",
  },
  {
    id: "poem",
    label: "Làm một bài thơ",
    prompt: "Làm một bài thơ 4 câu ngắn về ngôi nhà thông minh và buổi tối ấm áp đi.",
    category: "Sáng tạo",
    icon: "sparkles",
  },
  {
    id: "security",
    label: "Kiểm tra an ninh cửa",
    prompt: "Cửa chính hiện tại đã được khóa an toàn chưa?",
    category: "An ninh",
    icon: "shield",
  },
];

export function VoiceOverlay({
  open,
  dataMode = "real",
  listening,
  busy,
  error,
  transcript,
  manualValue,
  messages = [],
  latestAssistant = "",
  voiceStatusReady,
  ttsEnabled,
  isPlayingAudio = false,
  onClose,
  onStop,
  onToggle,
  onToggleTts,
  onManualChange,
  onSend,
  onSpeakText,
  onStopSpeaking,
}: {
  open: boolean;
  dataMode?: DataMode;
  mode?: string;
  listening: boolean;
  busy: boolean;
  error: string;
  transcript: string;
  manualValue: string;
  messages?: ChatMessage[];
  latestAssistant?: string;
  voiceStatusReady: boolean;
  ttsEnabled: boolean;
  isPlayingAudio?: boolean;
  onClose: () => void;
  onStop: () => void;
  onToggle: () => void;
  onSwitchMode?: (mode: any) => void;
  onToggleTts: () => void;
  onManualChange: (value: string) => void;
  onSend: (customPrompt?: string) => void;
  onSpeakText?: (text: string) => void;
  onStopSpeaking?: () => void;
}) {
  const dialogRef = useDialogFocus<HTMLElement>(open, onClose);
  const historyBottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (historyBottomRef.current) {
      historyBottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, transcript, busy]);

  if (!open) return null;

  const assistantName = "Trợ lý Xiaozhi (Local AI)";

  const statusText =
    error ||
    (busy
      ? "Xiaozhi đang suy nghĩ câu trả lời..."
      : listening
        ? "Đang lắng nghe tiếng Việt (Realtime VAD)..."
        : voiceStatusReady
          ? "Chạm vào biểu tượng micro để bắt đầu nói với Xiaozhi."
          : "Trợ lý Xiaozhi sẵn sàng. Hãy nói hoặc chọn kịch bản bên dưới.");

  const canSend = !busy && Boolean(transcript.trim() || manualValue.trim());

  function handleSelectScenario(scenario: ScenarioPrompt) {
    if (busy) return;
    onManualChange(scenario.prompt);
    onSend(scenario.prompt);
  }

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
        {/* Header */}
        <header className="hm-voice-head">
          <button
            className="hm-icon-button"
            type="button"
            onClick={onClose}
            aria-label="Đóng trò chuyện AI"
          >
            <Icon name="close" />
          </button>

          <div className="hm-voice-header-info">
            <div className="hm-voice-badge-row">
              <span className="hm-voice-status-dot" />
              <span className="hm-voice-engine-badge">GPU Accelerated • Qwen 2.5</span>
            </div>
            <strong id="hm-voice-title">Trò Chuyện AI Xiaozhi</strong>
            <span className="hm-voice-desc">Đối thoại tiếng Việt thông minh & quản lý nhà</span>
          </div>

          <div className="hm-voice-header-actions">
            <button
              type="button"
              className={`hm-tts-pill-btn ${ttsEnabled ? "active" : ""}`}
              onClick={onToggleTts}
              title={ttsEnabled ? "Giọng đọc AI đang BẬT (Piper TTS)" : "Giọng đọc AI đang TẮT"}
              aria-label="Bật tắt giọng đọc AI"
            >
              <span className="hm-tts-icon-wrap">
                <Icon name="sparkles" />
              </span>
              <span>TTS: {ttsEnabled ? "BẬT" : "TẮT"}</span>
            </button>
            {listening ? (
              <button
                className="hm-icon-button danger"
                type="button"
                onClick={onStop}
                aria-label="Dừng lắng nghe"
                title="Dừng lắng nghe"
              >
                <Icon name="micOff" />
              </button>
            ) : null}
          </div>
        </header>

        {/* Center Interactive Orb */}
        <VoiceComposer
          listening={listening}
          disabled={busy}
          statusText={statusText}
          onToggle={onToggle}
        />

        {/* Realtime STT Transcript Card (if listening or active) */}
        {(transcript || listening) ? (
          <VoiceTranscript transcript={transcript} />
        ) : null}

        {/* Conversation Stream */}
        <div className="hm-voice-history-scroll" aria-label="Lịch sử đối thoại">
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
                      {msg.role === "user" ? "Bạn" : assistantName}
                    </span>
                    <div className="hm-voice-msg-actions">
                      {msg.role === "assistant" && onSpeakText ? (
                        <button
                          type="button"
                          className="hm-msg-speak-action-btn"
                          onClick={() => onSpeakText(msg.text)}
                          title="Nghe giọng đọc câu trả lời này"
                          aria-label="Nghe lại câu trả lời"
                        >
                          <Icon name="volume" />
                          <span>Nghe</span>
                        </button>
                      ) : null}
                      <span className="hm-voice-msg-seq">#{idx + 1}</span>
                    </div>
                  </div>
                  <p className="hm-voice-msg-content">{msg.text}</p>
                </div>
              ))}
              {isPlayingAudio ? (
                <div className="hm-voice-audio-status-bar" role="status">
                  <div className="hm-soundwave-anim">
                    <span /><span /><span /><span />
                  </div>
                  <span>Trợ lý Xiaozhi đang phát giọng nói...</span>
                  {onStopSpeaking ? (
                    <button
                      type="button"
                      className="hm-audio-stop-pill"
                      onClick={onStopSpeaking}
                      title="Dừng giọng đọc"
                    >
                      Dừng
                    </button>
                  ) : null}
                </div>
              ) : null}
              {busy ? (
                <div className="hm-voice-msg-bubble assistant typing">
                  <div className="hm-voice-msg-header">
                    <span className="hm-voice-msg-sender">
                      <Icon name="sparkles" />
                      {assistantName}
                    </span>
                  </div>
                  <div className="hm-typing-indicator">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              ) : null}
              <div ref={historyBottomRef} />
            </div>
          ) : latestAssistant ? (
            <div className="hm-voice-last-reply" aria-live="polite">
              <div className="hm-reply-header">
                <Icon name="sparkles" />
                <span>Phản hồi từ {assistantName}</span>
                {onSpeakText ? (
                  <button
                    type="button"
                    className="hm-msg-speak-action-btn"
                    onClick={() => onSpeakText(latestAssistant)}
                    title="Nghe giọng đọc"
                  >
                    <Icon name="volume" />
                    <span>Nghe</span>
                  </button>
                ) : null}
              </div>
              <p>{latestAssistant}</p>
            </div>
          ) : (
            <div className="hm-voice-welcome-card">
              <div className="hm-welcome-icon">
                <Icon name="sparkles" />
              </div>
              <h4>Chào bạn! Tôi là Xiaozhi</h4>
              <p>
                Tôi có thể trò chuyện, chia sẻ kiến thức, tư vấn lối sống và kiểm tra không gian sống
                cho bạn. Hãy nói hoặc chọn nhanh kịch bản gợi ý bên dưới!
              </p>
            </div>
          )}
        </div>

        {/* Quick Test Scenarios Bar */}
        <div className="hm-voice-scenarios-section">
          <div className="hm-scenarios-header">
            <span>💡 Kịch bản trò chuyện thử nghiệm:</span>
          </div>
          <div className="hm-scenarios-grid">
            {TEST_SCENARIOS.map((sc) => (
              <button
                key={sc.id}
                type="button"
                className="hm-scenario-chip"
                disabled={busy}
                onClick={() => handleSelectScenario(sc)}
                title={sc.prompt}
              >
                <Icon name={sc.icon} />
                <span className="hm-chip-text">{sc.label}</span>
                <span className="hm-chip-tag">{sc.category}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Input Bar */}
        <VoiceFallbackInput
          value={manualValue}
          canSend={canSend}
          onChange={onManualChange}
          onSend={() => onSend()}
        />
      </section>
    </div>
  );
}

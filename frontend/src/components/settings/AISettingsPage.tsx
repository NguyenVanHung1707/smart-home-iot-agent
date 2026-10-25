import React, { useEffect, useState } from "react";
import { getAiConfig, resetAiConfig, saveAiConfig, synthesizeVoice } from "../../api/client";
import type { ApiDeviceCommand } from "../../api/types";
import { Icon } from "../shared/Icon";
import { PresetPanel } from "../rooms/PresetPanel";
import type {
  AiConfigData,
  AiModelOption,
  AiPersonaPreset,
  AiVoiceOption,
  Device,
  HomePreset,
  Role,
} from "../../types";

const PERSONA_ICONS: Record<string, string> = {
  gentle: "🌸",
  butler: "🤵",
  tech: "⚡",
  security: "🛡️",
  custom: "🎨",
};

interface AISettingsPageProps {
  role?: Role;
  devices?: Device[];
  presets?: HomePreset[];
  onPresetsChange?: (next: HomePreset[]) => void;
  onDeviceCommand?: (device: Device, command: ApiDeviceCommand) => Promise<void>;
  onNotify: (message: string) => void;
  initialTab?: "ai" | "presets";
}

export function AISettingsPage({
  role = "homeadmin",
  devices = [],
  presets: homePresets = [],
  onPresetsChange = () => {},
  onDeviceCommand = async () => {},
  onNotify,
  initialTab = "ai",
}: AISettingsPageProps) {
  const [activeTab, setActiveTab] = useState<"ai" | "presets">(initialTab);
  const [config, setConfig] = useState<AiConfigData | null>(null);
  const [personaPresets, setPersonaPresets] = useState<AiPersonaPreset[]>([]);
  const [voices, setVoices] = useState<AiVoiceOption[]>([]);
  const [models, setModels] = useState<AiModelOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testText, setTestText] = useState("");
  const [isPlayingTest, setIsPlayingTest] = useState(false);
  const [newWakeWord, setNewWakeWord] = useState("");

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    loadConfiguration();
  }, []);

  async function loadConfiguration() {
    setLoading(true);
    try {
      const res = await getAiConfig();
      setConfig(res.config);
      setPersonaPresets(res.presets);
      setVoices(res.voices);
      setModels(res.models);
      setTestText(res.config.greeting_text || "Dạ em chào anh chị! Em có thể giúp gì cho gia đình mình ạ?");
    } catch {
      onNotify("Không tải được cấu hình AI từ máy chủ.");
    } finally {
      setLoading(false);
    }
  }

  function handleSelectPreset(preset: AiPersonaPreset) {
    if (!config) return;
    setConfig({
      ...config,
      role: preset.id,
      role_name: preset.name,
      voice: preset.voice || config.voice,
      temperature: preset.temperature ?? config.temperature,
      system_prompt: preset.prompt || config.system_prompt,
      greeting_text: preset.greeting || config.greeting_text,
    });
    if (preset.greeting) {
      setTestText(preset.greeting);
    }
    onNotify(`Đã áp dụng mẫu nhân vật "${preset.name}".`);
  }

  function handleInsertPromptTag(tagText: string) {
    if (!config) return;
    const current = config.system_prompt.trim();
    const updated = current ? `${current}\n${tagText}` : tagText;
    setConfig({ ...config, system_prompt: updated });
  }

  function handleAddWakeWord() {
    const clean = newWakeWord.trim().toLowerCase();
    if (!clean || !config) return;
    if (config.wake_words.includes(clean)) {
      setNewWakeWord("");
      return;
    }
    setConfig({
      ...config,
      wake_words: [...config.wake_words, clean],
    });
    setNewWakeWord("");
  }

  function handleRemoveWakeWord(word: string) {
    if (!config) return;
    setConfig({
      ...config,
      wake_words: config.wake_words.filter((w) => w !== word),
    });
  }

  async function handleTestVoice() {
    const sentence = testText.trim() || config?.greeting_text || "Xin chào bạn, hệ thống AI đã sẵn sàng.";
    if (isPlayingTest) return;

    setIsPlayingTest(true);

    try {
      const { audioUrl } = await synthesizeVoice(sentence);
      const audio = new Audio(audioUrl);
      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        setIsPlayingTest(false);
      };
      audio.onerror = () => {
        URL.revokeObjectURL(audioUrl);
        fallbackBrowserTts(sentence);
      };
      await audio.play();
      return;
    } catch {
      fallbackBrowserTts(sentence);
    }
  }

  function fallbackBrowserTts(sentence: string) {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(sentence);
      utterance.lang = "vi-VN";
      utterance.rate = config?.speech_rate ?? 1.0;
      utterance.pitch = Math.max(0.5, Math.min(1.5, 1.0 + (config?.speech_pitch ?? 0) * 0.05));
      utterance.onend = () => setIsPlayingTest(false);
      utterance.onerror = () => setIsPlayingTest(false);
      window.speechSynthesis.speak(utterance);
    } else {
      setIsPlayingTest(false);
    }
  }

  async function handleSave() {
    if (!config) return;
    setSaving(true);
    try {
      const res = await saveAiConfig(config);
      setConfig(res.config);
      onNotify("Đã lưu và đồng bộ cấu hình AI thành công tới Master ESP32 & Web Hub!");
    } catch {
      onNotify("Không thể lưu cấu hình AI. Vui lòng kiểm tra kết nối.");
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    if (!window.confirm("Bạn có chắc chắn muốn khôi phục toàn bộ cấu hình AI về mặc định ban đầu không?")) {
      return;
    }
    setSaving(true);
    try {
      const res = await resetAiConfig();
      setConfig(res.config);
      onNotify("Đã khôi phục cấu hình AI về mặc định ban đầu.");
    } catch {
      onNotify("Không thể khôi phục mặc định.");
    } finally {
      setSaving(false);
    }
  }

  if (loading || !config) {
    return (
      <div className="hm-page" style={{ padding: 24, textAlign: "center" }}>
        <p style={{ color: "var(--hm-muted)" }}>Đang tải thông số cấu hình AI...</p>
      </div>
    );
  }

  return (
    <div className="hm-page hm-ai-settings-page">
      {/* Page Header */}
      <div>
        <h2 className="hm-page-title">Trợ Lý AI & Kịch Bản Ngữ Cảnh</h2>
        <p className="hm-page-intro">
          Trung tâm điều phối thông minh: Tùy biến giọng đọc AI, System Prompt và thiết lập các kịch bản ngữ cảnh tự động cho gia đình.
        </p>

        {/* Unified Tab Switcher */}
        <div className="hm-ai-nav-tabs">
          <button
            type="button"
            className={`hm-ai-nav-tab ${activeTab === "ai" ? "active" : ""}`}
            onClick={() => setActiveTab("ai")}
          >
            <Icon name="cpu" />
            <span>Trợ lý AI & Giọng nói</span>
          </button>
          <button
            type="button"
            className={`hm-ai-nav-tab ${activeTab === "presets" ? "active" : ""}`}
            onClick={() => setActiveTab("presets")}
          >
            <Icon name="sparkles" />
            <span>Kịch bản & Ngữ cảnh {homePresets.length ? `(${homePresets.length})` : ""}</span>
          </button>
        </div>
      </div>

      {activeTab === "presets" ? (
        <PresetPanel
          variant="page"
          devices={devices}
          presets={homePresets}
          canEdit={role === "homeadmin"}
          onPresetsChange={onPresetsChange}
          onDeviceCommand={onDeviceCommand}
        />
      ) : (
        <>
          <div className="hm-ai-header-badges">
            <span className="hm-ai-badge live">Voice AI Gateway: Đang chạy</span>
            <span className="hm-ai-badge">Mô hình: {config.model}</span>
            <span className="hm-ai-badge">Giọng đọc: {config.voice}</span>
          </div>

          {/* Section 1: Persona Presets */}
          <section className="hm-ai-section">
            <h3 className="hm-ai-section-title">
              <Icon name="sparkles" />
              <span>1. Chọn Tính Cách & Vai Trò (Persona Presets)</span>
            </h3>
            <p className="hm-ai-section-desc">
              Chọn một phong cách mẫu phù hợp với gia đình bạn để tự động điều chỉnh lời nhắc, giọng điệu và mức độ sáng tạo.
            </p>

            <div className="hm-persona-grid">
              {personaPresets.map((preset) => {
                const isSelected = config.role === preset.id;
                return (
                  <button
                    type="button"
                    key={preset.id}
                    className={`hm-persona-card ${isSelected ? "active" : ""}`}
                    onClick={() => handleSelectPreset(preset)}
                  >
                    <div className="hm-persona-header">
                      <span className="hm-persona-icon">{PERSONA_ICONS[preset.id] || "🤖"}</span>
                      {isSelected ? <span className="hm-persona-check">✓</span> : null}
                    </div>
                    <h4 className="hm-persona-name">{preset.name}</h4>
                    <p className="hm-persona-tagline">{preset.tagline}</p>
                    <div className="hm-persona-meta">
                      <span>Giọng: {preset.voice.includes("HoaiMy") ? "Hoài My (Nữ)" : preset.voice.includes("NamMinh") ? "Nam Minh (Nam)" : "Tùy biến"}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          {/* Section 2: Voice & Speech Settings */}
          <section className="hm-ai-section">
            <h3 className="hm-ai-section-title">
              <Icon name="mic" />
              <span>2. Cài Đặt Giọng Nói & Tốc Độ Đọc (Voice & Speech Synthesis)</span>
            </h3>
            <p className="hm-ai-section-desc">
              Chọn giọng đọc tiếng Việt truyền cảm, điều chỉnh tốc độ nói và kiểm tra âm thanh trực tiếp trên trình duyệt.
            </p>

            <div className="hm-ai-grid-2">
              <div className="hm-field-group">
                <label className="hm-field-label" htmlFor="ai-voice-select">
                  Giọng đọc Tiếng Việt (EdgeTTS / Hub)
                </label>
                <select
                  id="ai-voice-select"
                  className="hm-select"
                  value={config.voice}
                  onChange={(e) => setConfig({ ...config, voice: e.target.value })}
                >
                  {voices.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name} · {v.description}
                    </option>
                  ))}
                </select>
              </div>

              <div className="hm-field-group">
                <label className="hm-field-label">
                  <span>Tốc độ đọc (Speech Speed)</span>
                  <span className="hm-field-hint">Mặc định: 1.0x</span>
                </label>
                <div className="hm-range-container">
                  <input
                    type="range"
                    className="hm-range"
                    min="0.8"
                    max="1.4"
                    step="0.05"
                    value={config.speech_rate}
                    onChange={(e) => setConfig({ ...config, speech_rate: parseFloat(e.target.value) })}
                  />
                  <span className="hm-range-val">{config.speech_rate.toFixed(2)}x</span>
                </div>
              </div>
            </div>

            <div className="hm-voice-test-box">
              <label className="hm-field-label">Thử nghiệm giọng đọc thực tế:</label>
              <div className="hm-voice-test-row">
                <input
                  type="text"
                  className="hm-input hm-voice-test-input"
                  value={testText}
                  onChange={(e) => setTestText(e.target.value)}
                  placeholder="Nhập câu bạn muốn trợ lý đọc thử..."
                />
                <button
                  type="button"
                  className="hm-btn-test-voice"
                  onClick={handleTestVoice}
                  disabled={isPlayingTest}
                >
                  {isPlayingTest ? (
                    <>
                      <span className="hm-audio-wave">
                        <span className="hm-audio-bar" />
                        <span className="hm-audio-bar" />
                        <span className="hm-audio-bar" />
                        <span className="hm-audio-bar" />
                      </span>
                      <span>Đang đọc...</span>
                    </>
                  ) : (
                    <>
                      <span>🔊</span>
                      <span>Nghe thử giọng</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </section>

          {/* Section 3: System Prompt & Rules */}
          <section className="hm-ai-section">
            <h3 className="hm-ai-section-title">
              <Icon name="pencil" />
              <span>3. Lời Nhắc Hệ Thống (System Prompt & Quy Tắc Ứng Xử)</span>
            </h3>
            <p className="hm-ai-section-desc">
              Chỉ thị cốt lõi định hình tính cách, phong cách xưng hô và các quy tắc khi điều khiển thiết bị thông minh.
            </p>

            <div className="hm-prompt-container">
              <div className="hm-prompt-tags">
                <span style={{ fontSize: 12, color: "var(--hm-subtle)", alignSelf: "center" }}>Gợi ý chèn nhanh:</span>
                <button
                  type="button"
                  className="hm-prompt-tag"
                  onClick={() => handleInsertPromptTag("- Khi điều khiển thiết bị (đèn, quạt, cửa...), gọi function 'control_smart_home'.")}
                >
                  + Điều khiển thiết bị
                </button>
                <button
                  type="button"
                  className="hm-prompt-tag"
                  onClick={() => handleInsertPromptTag("- Khi hỏi nhiệt độ, độ ẩm, an toàn gas, gọi function 'get_smart_home_state'.")}
                >
                  + Đọc cảm biến
                </button>
                <button
                  type="button"
                  className="hm-prompt-tag"
                  onClick={() => handleInsertPromptTag("- Khi cần tra cứu thông tin ngoài mạng, gọi function 'search_internet'.")}
                >
                  + Tìm kiếm Internet
                </button>
                <button
                  type="button"
                  className="hm-prompt-tag"
                  onClick={() => handleInsertPromptTag("- Khi cần phát nhạc, mở bài hát, gọi function 'play_youtube_music'.")}
                >
                  + Phát nhạc YouTube
                </button>
                <button
                  type="button"
                  className="hm-prompt-tag"
                  onClick={() => handleInsertPromptTag("- Xưng 'em', gọi 'anh/chị', trả lời ngắn gọn 1-2 câu súc tích.")}
                >
                  + Xưng em gọi anh/chị
                </button>
              </div>

              <textarea
                className="hm-prompt-textarea"
                rows={10}
                value={config.system_prompt}
                onChange={(e) => setConfig({ ...config, system_prompt: e.target.value })}
                placeholder="Nhập System Prompt chi tiết cho trợ lý..."
              />
            </div>
          </section>

          {/* Section 4: AI Model & Wake Words */}
          <section className="hm-ai-section">
            <h3 className="hm-ai-section-title">
              <Icon name="cpu" />
              <span>4. Mô Hình AI & Từ Khóa Đánh Thức (Model & Wake Words)</span>
            </h3>

            <div className="hm-ai-grid-2">
              <div className="hm-field-group">
                <label className="hm-field-label" htmlFor="ai-model-select">
                  Mô hình Trí Tuệ Nhân Tạo (LLM Engine)
                </label>
                <select
                  id="ai-model-select"
                  className="hm-select"
                  value={config.model}
                  onChange={(e) => setConfig({ ...config, model: e.target.value })}
                >
                  {models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.provider}) · {m.description}
                    </option>
                  ))}
                </select>
              </div>

              <div className="hm-field-group">
                <label className="hm-field-label">
                  <span>Độ sáng tạo (Temperature)</span>
                  <span className="hm-field-hint">
                    {config.temperature <= 0.4 ? "Chính xác & kỷ luật" : config.temperature <= 0.75 ? "Tự nhiên & linh hoạt" : "Sáng tạo cao"}
                  </span>
                </label>
                <div className="hm-range-container">
                  <input
                    type="range"
                    className="hm-range"
                    min="0.1"
                    max="1.0"
                    step="0.05"
                    value={config.temperature}
                    onChange={(e) => setConfig({ ...config, temperature: parseFloat(e.target.value) })}
                  />
                  <span className="hm-range-val">{config.temperature.toFixed(2)}</span>
                </div>
              </div>
            </div>

            <div className="hm-field-group" style={{ marginTop: 10 }}>
              <label className="hm-field-label">
                <span>Từ khóa đánh thức bo mạch ESP32 (Wake Words)</span>
                <span className="hm-field-hint">Các từ gọi để đánh thức loa Master Gateway</span>
              </label>
              <div className="hm-chips-container">
                {config.wake_words.map((word) => (
                  <span key={word} className="hm-chip">
                    <span>{word}</span>
                    <button
                      type="button"
                      className="hm-chip-remove"
                      onClick={() => handleRemoveWakeWord(word)}
                      title="Xóa từ khóa"
                    >
                      &times;
                    </button>
                  </span>
                ))}
              </div>

              <div className="hm-chip-add-box">
                <input
                  type="text"
                  className="hm-input"
                  style={{ maxWidth: 300 }}
                  placeholder="Thêm từ khóa mới (vd: jarvis, ê bot)..."
                  value={newWakeWord}
                  onChange={(e) => setNewWakeWord(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddWakeWord();
                    }
                  }}
                />
                <button
                  type="button"
                  className="hm-btn-reset"
                  style={{ padding: "8px 16px" }}
                  onClick={handleAddWakeWord}
                >
                  + Thêm
                </button>
              </div>
            </div>
          </section>

          {/* Action Footer */}
          <div className="hm-ai-actions">
            <button
              type="button"
              className="hm-btn-reset"
              onClick={handleReset}
              disabled={saving}
            >
              Khôi phục mặc định
            </button>
            <button
              type="button"
              className="hm-btn-save"
              onClick={handleSave}
              disabled={saving}
            >
              <Icon name="check" />
              <span>{saving ? "Đang đồng bộ..." : "Lưu & Đồng bộ lên ESP32 / Hub"}</span>
            </button>
          </div>
        </>
      )}
    </div>
  );
}

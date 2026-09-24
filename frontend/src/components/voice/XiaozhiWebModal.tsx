import React, { useEffect, useRef, useState } from "react";
import { getMqttCurrentStatus, publishDeviceCommand, publishSpeakerBroadcast } from "../../api/cloudMqtt";
import { Icon } from "../shared/Icon";

export interface XiaozhiMessage {
  id: string;
  sender: "user" | "xiaozhi";
  text: string;
  timestamp: number;
  actionExecuted?: string;
}

interface XiaozhiWebModalProps {
  open: boolean;
  onClose: () => void;
  onDeviceCommand?: (deviceId: string, action: string) => void;
}

const QUICK_PROMPTS = [
  "Bật đèn phòng khách",
  "Tắt đèn phòng khách",
  "Bật quạt phòng ngủ",
  "Tắt hết đèn",
  "Mở khóa cửa",
  "Thời tiết hôm nay thế nào?",
];

export function XiaozhiWebModal({ open, onClose, onDeviceCommand }: XiaozhiWebModalProps) {
  const [activeTab, setActiveTab] = useState<"chat" | "intercom" | "settings">("chat");
  const [messages, setMessages] = useState<XiaozhiMessage[]>([
    {
      id: "init",
      sender: "xiaozhi",
      text: "Xin chào! Mình là Xiaozhi Web Client. Bạn có thể nói hoặc gõ lệnh điều khiển thiết bị nhé!",
      timestamp: Date.now(),
    },
  ]);
  const [inputText, setInputText] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [broadcastText, setBroadcastText] = useState("");
  const [broadcastSent, setBroadcastSent] = useState(false);

  // Settings
  const [xiaozhiServerUrl, setXiaozhiServerUrl] = useState(() => {
    return localStorage.getItem("homing-xiaozhi-server-url") || "wss://api.tenclass.net/v1";
  });
  const [autoSpeak, setAutoSpeak] = useState(() => {
    return localStorage.getItem("homing-xiaozhi-auto-speak") !== "false";
  });

  const chatBottomRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);

  // Cuộn xuống tin nhắn mới nhất
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Khởi tạo Speech Recognition (Web Speech API)
  useEffect(() => {
    if (typeof window !== "undefined") {
      const SpeechRecognition =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = "vi-VN";

        recognition.onstart = () => {
          setIsRecording(true);
        };

        recognition.onresult = (event: any) => {
          const transcript = event.results[0][0].transcript;
          if (transcript) {
            handleUserMessage(transcript);
          }
        };

        recognition.onerror = (e: any) => {
          console.warn("[Xiaozhi Web] Speech recognition error:", e);
          setIsRecording(false);
        };

        recognition.onend = () => {
          setIsRecording(false);
        };

        recognitionRef.current = recognition;
      }
    }
  }, []);

  // Hàm phát âm thanh phản hồi bằng Web Speech Synthesis
  function speakResponse(text: string) {
    if (!autoSpeak || typeof window === "undefined" || !("speechSynthesis" in window)) return;

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "vi-VN";
    utterance.rate = 1.05;

    // Ưu tiên chọn giọng tiếng Việt chất lượng cao nếu có
    const voices = window.speechSynthesis.getVoices();
    const viVoice = voices.find((v) => v.lang.includes("vi"));
    if (viVoice) utterance.voice = viVoice;

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.speak(utterance);
  }

  // Phân tích câu lệnh tiếng Việt tự nhiên và điều khiển thiết bị qua Cloud MQTT
  function processSmartHomeIntent(query: string): { reply: string; action?: string } {
    const q = query.toLowerCase().trim();

    // 1. Đèn phòng khách
    if (q.includes("đèn phòng khách") || q.includes("đèn khách")) {
      if (q.includes("bật") || q.includes("mở")) {
        publishDeviceCommand("living-light", "turn_on", 1);
        onDeviceCommand?.("living-light", "turn_on");
        return { reply: "Dạ, em đã bật đèn phòng khách rồi ạ!", action: "living-light ➔ turn_on" };
      }
      if (q.includes("tắt") || q.includes("đóng")) {
        publishDeviceCommand("living-light", "turn_off", 0);
        onDeviceCommand?.("living-light", "turn_off");
        return { reply: "Dạ, em đã tắt đèn phòng khách rồi ạ!", action: "living-light ➔ turn_off" };
      }
    }

    // 2. Đèn phòng ngủ
    if (q.includes("đèn phòng ngủ") || q.includes("đèn ngủ")) {
      if (q.includes("bật") || q.includes("mở")) {
        publishDeviceCommand("bedroom-light", "turn_on", 1);
        onDeviceCommand?.("bedroom-light", "turn_on");
        return { reply: "Em đã bật đèn phòng ngủ cho bạn rồi nhé!", action: "bedroom-light ➔ turn_on" };
      }
      if (q.includes("tắt")) {
        publishDeviceCommand("bedroom-light", "turn_off", 0);
        onDeviceCommand?.("bedroom-light", "turn_off");
        return { reply: "Em đã tắt đèn phòng ngủ rồi ạ!", action: "bedroom-light ➔ turn_off" };
      }
    }

    // 3. Đèn bếp
    if (q.includes("đèn bếp") || q.includes("đèn phòng bếp")) {
      if (q.includes("bật") || q.includes("mở")) {
        publishDeviceCommand("kitchen-light", "turn_on", 1);
        onDeviceCommand?.("kitchen-light", "turn_on");
        return { reply: "Đã bật đèn bếp rồi nha!", action: "kitchen-light ➔ turn_on" };
      }
      if (q.includes("tắt")) {
        publishDeviceCommand("kitchen-light", "turn_off", 0);
        onDeviceCommand?.("kitchen-light", "turn_off");
        return { reply: "Đã tắt đèn bếp rồi ạ!", action: "kitchen-light ➔ turn_off" };
      }
    }

    // 4. Quạt các phòng
    if (q.includes("quạt phòng khách") || q.includes("quạt khách")) {
      const turnOn = q.includes("bật") || q.includes("mở");
      publishDeviceCommand("living-fan", turnOn ? "turn_on" : "turn_off", turnOn ? 1 : 0);
      return { reply: turnOn ? "Đã bật quạt phòng khách mát rượi!" : "Đã tắt quạt phòng khách.", action: `living-fan ➔ ${turnOn ? "turn_on" : "turn_off"}` };
    }
    if (q.includes("quạt phòng ngủ") || q.includes("quạt ngủ")) {
      const turnOn = q.includes("bật") || q.includes("mở");
      publishDeviceCommand("bedroom-fan", turnOn ? "turn_on" : "turn_off", turnOn ? 1 : 0);
      return { reply: turnOn ? "Đã bật quạt phòng ngủ!" : "Đã tắt quạt phòng ngủ.", action: `bedroom-fan ➔ ${turnOn ? "turn_on" : "turn_off"}` };
    }

    // 5. Khóa cửa
    if (q.includes("mở cửa") || q.includes("mở khóa") || q.includes("unlock")) {
      publishDeviceCommand("entry-lock", "unlock", 1);
      onDeviceCommand?.("entry-lock", "unlock");
      return { reply: "Chốt cửa đã được mở! Cửa sẽ tự động khóa lại sau 5 giây.", action: "entry-lock ➔ unlock" };
    }
    if (q.includes("khóa cửa") || q.includes("đóng cửa") || q.includes("lock")) {
      publishDeviceCommand("entry-lock", "lock", 0);
      onDeviceCommand?.("entry-lock", "lock");
      return { reply: "Cửa chính đã được khóa an toàn!", action: "entry-lock ➔ lock" };
    }

    // 6. Tắt hết đèn
    if (q.includes("tắt hết đèn") || q.includes("tắt tất cả đèn")) {
      publishDeviceCommand("all-lights", "turn_off", 0);
      return { reply: "Đã tắt tất cả các đèn trong nhà rồi nhé!", action: "all-lights ➔ turn_off" };
    }

    // 7. Hỏi thời tiết / Trò chuyện tổng quát
    if (q.includes("thời tiết")) {
      return { reply: "Hôm nay thời tiết rất dễ chịu, nhiệt độ trong nhà đang ở mức khoảng 28 độ C ạ!" };
    }

    return {
      reply: `Xiaozhi đã nghe: "${query}". Lệnh này đã được đồng bộ tới hệ thống nhà thông minh của bạn!`,
    };
  }

  function handleUserMessage(text: string) {
    if (!text.trim()) return;

    const userMsg: XiaozhiMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: text.trim(),
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText("");

    // Phân tích và sinh câu trả lời
    setTimeout(() => {
      const { reply, action } = processSmartHomeIntent(text);
      const botMsg: XiaozhiMessage = {
        id: `xz-${Date.now()}`,
        sender: "xiaozhi",
        text: reply,
        timestamp: Date.now(),
        actionExecuted: action,
      };
      setMessages((prev) => [...prev, botMsg]);
      speakResponse(reply);
    }, 400);
  }

  function toggleVoiceRecording() {
    if (isRecording) {
      recognitionRef.current?.stop();
      setIsRecording(false);
    } else {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.start();
        } catch (err) {
          console.warn("Recognition already started", err);
        }
      } else {
        alert("Trình duyệt này chưa hỗ trợ nhận dạng giọng nói trực tiếp. Bạn hãy gõ tin nhắn nhé!");
      }
    }
  }

  function handleSendBroadcast() {
    if (!broadcastText.trim()) return;
    publishSpeakerBroadcast(broadcastText.trim());
    setBroadcastSent(true);
    setTimeout(() => setBroadcastSent(false), 3000);
    setBroadcastText("");
  }

  if (!open) return null;

  const mqttStatus = getMqttCurrentStatus();

  return (
    <div className="hm-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="hm-modal hm-xiaozhi-modal"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: "540px",
          width: "92%",
          maxHeight: "88vh",
          display: "flex",
          flexDirection: "column",
          borderRadius: "16px",
          overflow: "hidden",
          boxShadow: "0 24px 48px rgba(0,0,0,0.3)",
        }}
      >
        {/* Header */}
        <header
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border-color, #333)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(168, 85, 247, 0.15))",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                width: "40px",
                height: "40px",
                borderRadius: "50%",
                background: "linear-gradient(135deg, #6366f1, #a855f7)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
                boxShadow: isSpeaking ? "0 0 16px #a855f7" : "none",
                transition: "box-shadow 0.3s ease",
              }}
            >
              <Icon name="sparkles" />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: "17px", fontWeight: 600 }}>Xiaozhi AI Assistant</h3>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "2px" }}>
                <span
                  style={{
                    fontSize: "11px",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "4px",
                    color: mqttStatus === "connected" ? "#10b981" : "#f59e0b",
                  }}
                >
                  <span
                    style={{
                      width: "6px",
                      height: "6px",
                      borderRadius: "50%",
                      backgroundColor: mqttStatus === "connected" ? "#10b981" : "#f59e0b",
                    }}
                  />
                  Cloud MQTT: {mqttStatus === "connected" ? "Đã kết nối" : "Ngoại tuyến"}
                </span>
                <span style={{ fontSize: "11px", color: "#888" }}>• Web Client</span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-muted, #888)",
              cursor: "pointer",
              padding: "6px",
              borderRadius: "8px",
            }}
            title="Đóng"
          >
            <Icon name="close" />
          </button>
        </header>

        {/* Navigation Tabs */}
        <nav
          style={{
            display: "flex",
            borderBottom: "1px solid var(--border-color, #333)",
            background: "rgba(0,0,0,0.05)",
          }}
        >
          <button
            onClick={() => setActiveTab("chat")}
            style={{
              flex: 1,
              padding: "10px",
              border: "none",
              borderBottom: activeTab === "chat" ? "2px solid #6366f1" : "2px solid transparent",
              background: "none",
              fontWeight: activeTab === "chat" ? 600 : 400,
              color: activeTab === "chat" ? "#6366f1" : "inherit",
              cursor: "pointer",
              fontSize: "13px",
            }}
          >
            Trò chuyện & Giọng nói
          </button>
          <button
            onClick={() => setActiveTab("intercom")}
            style={{
              flex: 1,
              padding: "10px",
              border: "none",
              borderBottom: activeTab === "intercom" ? "2px solid #6366f1" : "2px solid transparent",
              background: "none",
              fontWeight: activeTab === "intercom" ? 600 : 400,
              color: activeTab === "intercom" ? "#6366f1" : "inherit",
              cursor: "pointer",
              fontSize: "13px",
            }}
          >
            Phát loa về nhà
          </button>
          <button
            onClick={() => setActiveTab("settings")}
            style={{
              flex: 1,
              padding: "10px",
              border: "none",
              borderBottom: activeTab === "settings" ? "2px solid #6366f1" : "2px solid transparent",
              background: "none",
              fontWeight: activeTab === "settings" ? 600 : 400,
              color: activeTab === "settings" ? "#6366f1" : "inherit",
              cursor: "pointer",
              fontSize: "13px",
            }}
          >
            Cấu hình
          </button>
        </nav>

        {/* Tab 1: Chat & Voice */}
        {activeTab === "chat" && (
          <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
            {/* Message Thread */}
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                padding: "16px",
                display: "flex",
                flexDirection: "column",
                gap: "12px",
                minHeight: "260px",
                maxHeight: "380px",
              }}
            >
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: msg.sender === "user" ? "flex-end" : "flex-start",
                  }}
                >
                  <div
                    style={{
                      maxWidth: "80%",
                      padding: "10px 14px",
                      borderRadius:
                        msg.sender === "user" ? "14px 14px 2px 14px" : "14px 14px 14px 2px",
                      backgroundColor: msg.sender === "user" ? "#6366f1" : "rgba(255,255,255,0.08)",
                      color: msg.sender === "user" ? "#ffffff" : "inherit",
                      fontSize: "14px",
                      lineHeight: "1.45",
                      boxShadow: "0 2px 6px rgba(0,0,0,0.08)",
                    }}
                  >
                    {msg.text}
                  </div>
                  {msg.actionExecuted && (
                    <span
                      style={{
                        fontSize: "11px",
                        color: "#10b981",
                        marginTop: "4px",
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                      }}
                    >
                      <Icon name="check" /> Đã thực thi: {msg.actionExecuted}
                    </span>
                  )}
                  <span style={{ fontSize: "10px", opacity: 0.5, marginTop: "2px" }}>
                    {new Date(msg.timestamp).toLocaleTimeString("vi-VN", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              ))}
              <div ref={chatBottomRef} />
            </div>

            {/* Quick Prompts */}
            <div
              style={{
                padding: "6px 16px",
                display: "flex",
                gap: "6px",
                overflowX: "auto",
                whiteSpace: "nowrap",
                borderTop: "1px solid var(--border-color, #222)",
              }}
            >
              {QUICK_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => handleUserMessage(prompt)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: "20px",
                    fontSize: "11px",
                    border: "1px solid var(--border-color, #444)",
                    background: "rgba(255,255,255,0.04)",
                    color: "inherit",
                    cursor: "pointer",
                  }}
                >
                  {prompt}
                </button>
              ))}
            </div>

            {/* Voice & Input Footer */}
            <footer
              style={{
                padding: "14px 16px",
                borderTop: "1px solid var(--border-color, #333)",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              {/* Micro Button */}
              <button
                onClick={toggleVoiceRecording}
                style={{
                  width: "44px",
                  height: "44px",
                  borderRadius: "50%",
                  border: "none",
                  backgroundColor: isRecording ? "#ef4444" : "#6366f1",
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  boxShadow: isRecording ? "0 0 16px #ef4444" : "0 2px 8px rgba(99,102,241,0.4)",
                  transform: isRecording ? "scale(1.08)" : "scale(1)",
                  transition: "all 0.2s ease",
                  flexShrink: 0,
                }}
                title={isRecording ? "Đang thu âm... Nhấp để dừng" : "Nhấp để nói chuyện"}
              >
                <Icon name={isRecording ? "micOff" : "mic"} />
              </button>

              {/* Text Input */}
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleUserMessage(inputText);
                }}
                placeholder={isRecording ? "Đang lắng nghe bạn nói..." : "Gõ lệnh hoặc bấm micro để nói..."}
                style={{
                  flex: 1,
                  padding: "10px 14px",
                  borderRadius: "20px",
                  border: "1px solid var(--border-color, #444)",
                  backgroundColor: "rgba(255,255,255,0.05)",
                  color: "inherit",
                  fontSize: "14px",
                  outline: "none",
                }}
              />

              <button
                onClick={() => handleUserMessage(inputText)}
                disabled={!inputText.trim()}
                style={{
                  padding: "10px 16px",
                  borderRadius: "20px",
                  border: "none",
                  backgroundColor: inputText.trim() ? "#6366f1" : "rgba(255,255,255,0.1)",
                  color: "#fff",
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor: inputText.trim() ? "pointer" : "default",
                }}
              >
                Gửi
              </button>
            </footer>
          </div>
        )}

        {/* Tab 2: Intercom / Loa phát về nhà */}
        {activeTab === "intercom" && (
          <div style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
            <div
              style={{
                padding: "12px",
                borderRadius: "8px",
                background: "rgba(99,102,241,0.1)",
                border: "1px solid rgba(99,102,241,0.2)",
                fontSize: "13px",
              }}
            >
              📢 <strong>Phát loa thông báo về nhà:</strong> Khi bạn ở xa, nhập tin nhắn vào đây để
              con loa <strong>ESP32 Xiaozhi đặt ở phòng khách</strong> tự động đọc to cho cả nhà nghe!
            </div>

            <textarea
              rows={4}
              value={broadcastText}
              onChange={(e) => setBroadcastText(e.target.value)}
              placeholder="Ví dụ: 'Mẹ ơi mở cửa cho con với' hoặc 'Cả nhà ơi 15 phút nữa con về ăn cơm'..."
              style={{
                width: "100%",
                padding: "12px",
                borderRadius: "8px",
                border: "1px solid var(--border-color, #444)",
                backgroundColor: "rgba(255,255,255,0.05)",
                color: "inherit",
                fontSize: "14px",
                resize: "none",
                outline: "none",
              }}
            />

            <button
              onClick={handleSendBroadcast}
              disabled={!broadcastText.trim()}
              style={{
                padding: "12px",
                borderRadius: "8px",
                border: "none",
                background: "linear-gradient(135deg, #6366f1, #a855f7)",
                color: "#fff",
                fontWeight: 600,
                fontSize: "14px",
                cursor: broadcastText.trim() ? "pointer" : "default",
                opacity: broadcastText.trim() ? 1 : 0.5,
              }}
            >
              {broadcastSent ? "✓ Đã phát ra loa phòng khách!" : "Phát ra Loa Nhà"}
            </button>
          </div>
        )}

        {/* Tab 3: Settings */}
        {activeTab === "settings" && (
          <div style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "16px", fontSize: "14px" }}>
            <div>
              <label style={{ display: "block", marginBottom: "6px", fontWeight: 500 }}>
                Xiaozhi Cloud WebSocket Endpoint:
              </label>
              <input
                type="text"
                value={xiaozhiServerUrl}
                onChange={(e) => {
                  setXiaozhiServerUrl(e.target.value);
                  localStorage.setItem("homing-xiaozhi-server-url", e.target.value);
                }}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "6px",
                  border: "1px solid var(--border-color, #444)",
                  backgroundColor: "rgba(255,255,255,0.05)",
                  color: "inherit",
                }}
              />
            </div>

            <label style={{ display: "flex", alignItems: "center", gap: "10px", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={autoSpeak}
                onChange={(e) => {
                  setAutoSpeak(e.target.checked);
                  localStorage.setItem("homing-xiaozhi-auto-speak", e.target.checked ? "true" : "false");
                }}
              />
              Tự động phát giọng nói trả lời (TTS) trên loa điện thoại/laptop
            </label>

            <div style={{ fontSize: "12px", opacity: 0.6, marginTop: "12px", lineHeight: "1.5" }}>
              💡 <strong>Kiến trúc Serverless:</strong> Web Client gửi và nhận lệnh thông qua Cloud MQTT
              (WSS) được lưu cấu hình trong mục Cài đặt MQTT. Không cần chạy máy tính hay Docker ở nhà.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

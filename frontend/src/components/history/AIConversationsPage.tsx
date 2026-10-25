import { useEffect, useState, useMemo, useRef } from "react";
import type { AIConversationItem } from "../../types";
import { getAIConversations, clearAIConversations, deleteAIConversation, synthesizeVoice } from "../../api/client";
import { Icon } from "../shared/Icon";
import { SectionHeading } from "../shared/SectionHeading";

type FilterTab = "all" | "web" | "esp_ai" | "device_action";

export function AIConversationsPage({
  onNotify,
}: {
  onNotify?: (title: string, message: string, type?: "info" | "online" | "offline") => void;
}) {
  const [conversations, setConversations] = useState<AIConversationItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [playingId, setPlayingId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const fetchConversations = async () => {
    try {
      setLoading(true);
      const res = await getAIConversations({ limit: 200 });
      setConversations(res.items || []);
      setTotalCount(res.total || 0);
    } catch (err) {
      console.error("Failed to load AI conversations:", err);
      onNotify?.("Lỗi tải lịch sử", "Không kết nối được Hub để lấy nhật ký hội thoại AI.", "offline");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchConversations();

    // Auto cleanup audio on unmount
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  // Compute live stats
  const stats = useMemo(() => {
    const webCount = conversations.filter((c) => c.source === "web").length;
    const espCount = conversations.filter((c) => c.source === "esp_ai").length;
    const actionCount = conversations.filter((c) => !!c.device_action).length;
    return {
      total: conversations.length,
      web: webCount,
      esp: espCount,
      actions: actionCount,
    };
  }, [conversations]);

  // Filter conversations
  const filteredConversations = useMemo(() => {
    return conversations.filter((item) => {
      // Tab filter
      if (activeTab === "web" && item.source !== "web") return false;
      if (activeTab === "esp_ai" && item.source !== "esp_ai") return false;
      if (activeTab === "device_action" && !item.device_action) return false;

      // Search filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const inUser = item.user_query.toLowerCase().includes(q);
        const inAi = item.ai_response.toLowerCase().includes(q);
        const inAction = (item.device_action || "").toLowerCase().includes(q);
        const inIntent = (item.intent || "").toLowerCase().includes(q);
        if (!inUser && !inAi && !inAction && !inIntent) return false;
      }

      return true;
    });
  }, [conversations, activeTab, searchQuery]);

  const handlePlayAudio = async (item: AIConversationItem) => {
    if (!item.audio_url && !item.ai_response) return;

    if (playingId === item.id) {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      setPlayingId(null);
      return;
    }

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }

    setPlayingId(item.id);

    // 1. Nếu có audio_url (từ ESP32 AI Gateway hoặc máy chủ TTS cache)
    if (item.audio_url) {
      try {
        const audio = new Audio(item.audio_url);
        audioRef.current = audio;

        audio.onended = () => {
          setPlayingId(null);
          audioRef.current = null;
        };

        audio.onerror = () => {
          audioRef.current = null;
          void playSpeechText(item.ai_response, item.id);
        };

        await audio.play();
        return;
      } catch {
        void playSpeechText(item.ai_response, item.id);
        return;
      }
    }

    // 2. Nếu không có audio_url (cuộc trò chuyện từ Web AI Chat), tổng hợp ngay lập tức
    void playSpeechText(item.ai_response, item.id);
  };

  const playSpeechText = async (text: string, itemId: string) => {
    const cleanText = (text || "").replace(/[*_#`~[\]]/g, " ").replace(/\s+/g, " ").trim();
    if (!cleanText) {
      setPlayingId(null);
      return;
    }
    try {
      const { audioUrl } = await synthesizeVoice(cleanText);
      const audio = new Audio(audioUrl);
      audioRef.current = audio;
      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        setPlayingId(null);
        audioRef.current = null;
      };
      audio.onerror = () => {
        URL.revokeObjectURL(audioUrl);
        fallbackSpeechSynthesis(cleanText, itemId);
      };
      await audio.play();
    } catch {
      fallbackSpeechSynthesis(cleanText, itemId);
    }
  };

  const fallbackSpeechSynthesis = (cleanText: string, itemId: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      setPlayingId(null);
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = "vi-VN";
    utterance.onstart = () => setPlayingId(itemId);
    utterance.onend = () => setPlayingId(null);
    utterance.onerror = () => setPlayingId(null);
    window.speechSynthesis.speak(utterance);
  };

  const handleDeleteItem = async (id: string) => {
    try {
      await deleteAIConversation(id);
      setConversations((prev) => prev.filter((item) => item.id !== id));
      setTotalCount((prev) => Math.max(0, prev - 1));
      onNotify?.("Đã xóa", "Đã xóa 1 đoạn hội thoại khỏi lịch sử.", "info");
    } catch (e) {
      console.error("Failed to delete item:", e);
      onNotify?.("Lỗi", "Không thể xóa đoạn hội thoại này.", "offline");
    }
  };

  const handleClearHistory = async () => {
    const confirmText =
      activeTab === "all"
        ? "Bạn có chắc chắn muốn xóa toàn bộ lịch sử trò chuyện AI?"
        : `Bạn có chắc muốn xóa lịch sử trò chuyện mục ${activeTab}?`;

    if (!window.confirm(confirmText)) return;

    try {
      const filterSource = activeTab === "web" || activeTab === "esp_ai" ? activeTab : undefined;
      await clearAIConversations(filterSource);
      await fetchConversations();
      onNotify?.("Đã làm sạch", "Lịch sử cuộc trò chuyện AI đã được dọn sạch.", "online");
    } catch (e) {
      console.error("Failed to clear conversations:", e);
      onNotify?.("Lỗi", "Không thể xóa lịch sử cuộc trò chuyện.", "offline");
    }
  };

  const formatTimestamp = (isoStr: string) => {
    try {
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return isoStr;

      const timePart = d.toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });

      const datePart = d.toLocaleDateString("vi-VN", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });

      return `${timePart} · ${datePart}`;
    } catch {
      return isoStr;
    }
  };

  return (
    <section className="hm-conv-page" aria-label="Lịch sử Hội thoại AI">
      <SectionHeading
        eyebrow="Omnichannel AI History"
        title="Lịch Sử Tất Cả Cuộc Trò Chuyện Với AI"
        aside={<span className="hm-count">{filteredConversations.length} / {totalCount} Lượt</span>}
      />
      <p className="hm-page-intro">
        Xem và quản lý tất cả các tương tác thoại và chat thông minh được ghi nhận từ <strong>Trang Web</strong> và <strong>ESP32 AI Gateway (Xiaozhi Hardware)</strong> trong cùng một nơi.
      </p>

      {/* KPI Stats Overview */}
      <div className="hm-conv-stats-grid">
        <div className="hm-conv-stat-card">
          <div className="hm-conv-stat-icon">
            <Icon name="sparkles" />
          </div>
          <div className="hm-conv-stat-info">
            <span className="hm-conv-stat-value">{stats.total}</span>
            <span className="hm-conv-stat-label">Tổng cuộc trò chuyện</span>
          </div>
        </div>

        <div className="hm-conv-stat-card">
          <div className="hm-conv-stat-icon web">
            <Icon name="list" />
          </div>
          <div className="hm-conv-stat-info">
            <span className="hm-conv-stat-value">{stats.web}</span>
            <span className="hm-conv-stat-label">Từ Web AI Chat</span>
          </div>
        </div>

        <div className="hm-conv-stat-card">
          <div className="hm-conv-stat-icon esp">
            <Icon name="mic" />
          </div>
          <div className="hm-conv-stat-info">
            <span className="hm-conv-stat-value">{stats.esp}</span>
            <span className="hm-conv-stat-label">Từ ESP32 Gateway</span>
          </div>
        </div>

        <div className="hm-conv-stat-card">
          <div className="hm-conv-stat-icon action">
            <Icon name="power" />
          </div>
          <div className="hm-conv-stat-info">
            <span className="hm-conv-stat-value">{stats.actions}</span>
            <span className="hm-conv-stat-label">Lệnh thiết bị thực thi</span>
          </div>
        </div>
      </div>

      {/* Control Toolbar */}
      <div className="hm-conv-toolbar">
        {/* Filter Pills */}
        <div className="hm-conv-filters">
          <button
            type="button"
            className={`hm-conv-filter-btn ${activeTab === "all" ? "active" : ""}`}
            onClick={() => setActiveTab("all")}
          >
            <span>Tất cả</span>
            <span className="hm-conv-filter-count">{stats.total}</span>
          </button>

          <button
            type="button"
            className={`hm-conv-filter-btn ${activeTab === "web" ? "active" : ""}`}
            onClick={() => setActiveTab("web")}
          >
            <Icon name="list" />
            <span>Web AI</span>
            <span className="hm-conv-filter-count">{stats.web}</span>
          </button>

          <button
            type="button"
            className={`hm-conv-filter-btn ${activeTab === "esp_ai" ? "active" : ""}`}
            onClick={() => setActiveTab("esp_ai")}
          >
            <Icon name="mic" />
            <span>ESP AI (Gateway)</span>
            <span className="hm-conv-filter-count">{stats.esp}</span>
          </button>

          <button
            type="button"
            className={`hm-conv-filter-btn ${activeTab === "device_action" ? "active" : ""}`}
            onClick={() => setActiveTab("device_action")}
          >
            <Icon name="power" />
            <span>Có lệnh thiết bị</span>
            <span className="hm-conv-filter-count">{stats.actions}</span>
          </button>
        </div>

        {/* Search & Actions */}
        <div className="hm-conv-search-actions">
          <div className="hm-conv-search-box">
            <div className="hm-conv-search-icon">
              <Icon name="list" />
            </div>
            <input
              type="text"
              className="hm-conv-search-input"
              placeholder="Tìm câu hỏi, câu trả lời, thiết bị..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <button
            type="button"
            className="hm-conv-btn-secondary"
            title="Làm mới danh sách"
            onClick={fetchConversations}
          >
            <Icon name="refresh" />
            <span>Làm mới</span>
          </button>

          {conversations.length > 0 && (
            <button
              type="button"
              className="hm-conv-btn-danger"
              title="Xóa toàn bộ lịch sử"
              onClick={handleClearHistory}
            >
              <Icon name="trash" />
              <span>Xóa lịch sử</span>
            </button>
          )}
        </div>
      </div>

      {/* Conversation List */}
      {loading ? (
        <div className="hm-conv-empty">
          <div className="hm-conv-empty-icon" style={{ animation: "spin 1.5s linear infinite" }}>
            <Icon name="refresh" />
          </div>
          <p className="hm-conv-empty-title">Đang tải lịch sử cuộc trò chuyện...</p>
        </div>
      ) : filteredConversations.length === 0 ? (
        <div className="hm-conv-empty">
          <div className="hm-conv-empty-icon">
            <Icon name="sparkles" />
          </div>
          <p className="hm-conv-empty-title">Không tìm thấy cuộc trò chuyện nào</p>
          <p className="hm-conv-empty-desc">
            {searchQuery
              ? `Không có kết quả nào khớp với "${searchQuery}". Hãy thử từ khóa khác.`
              : "Chưa có lượt tương tác nào được lưu. Hãy thử nói 'Alo' vào ESP32 hoặc chat trên Web để bắt đầu!"}
          </p>
        </div>
      ) : (
        <div className="hm-conv-list">
          {filteredConversations.map((item) => {
            const isEsp = item.source === "esp_ai";
            const isPlaying = playingId === item.id;

            return (
              <article key={item.id} className="hm-conv-card">
                {/* Card Header */}
                <div className="hm-conv-card-header">
                  <div className="hm-conv-meta-left">
                    <span className={`hm-conv-badge-source ${isEsp ? "esp_ai" : "web"}`}>
                      <Icon name={isEsp ? "mic" : "list"} />
                      <span>{isEsp ? "ESP32 AI Gateway" : "Web AI Chat"}</span>
                    </span>

                    <time className="hm-conv-time">
                      <Icon name="clock" /> {formatTimestamp(item.created_at)}
                    </time>

                    {item.session_id && item.session_id !== "default" && (
                      <span className="hm-conv-session-tag" title="Mã phiên">
                        #{item.session_id.slice(-8)}
                      </span>
                    )}
                  </div>

                  <button
                    type="button"
                    className="hm-conv-delete-btn"
                    title="Xóa lượt trò chuyện này"
                    onClick={() => handleDeleteItem(item.id)}
                  >
                    <Icon name="trash" />
                  </button>
                </div>

                {/* Conversation Body */}
                <div className="hm-conv-body">
                  {/* User Speech / Message */}
                  <div className="hm-conv-bubble user">
                    <div className="hm-conv-avatar user">
                      <Icon name="mic" />
                    </div>
                    <div className="hm-conv-bubble-content">
                      <div className="hm-conv-bubble-sender">Người Dùng</div>
                      <div className="hm-conv-bubble-text">{item.user_query}</div>
                    </div>
                  </div>

                  {/* AI Response */}
                  <div className="hm-conv-bubble ai">
                    <div className="hm-conv-avatar ai">
                      <Icon name="sparkles" />
                    </div>
                    <div className="hm-conv-bubble-content">
                      <div className="hm-conv-bubble-sender">
                        {isEsp ? "Trợ Lý Homing Xiaozhi" : "Trợ Lý AI Web Hub"}
                      </div>
                      <div className="hm-conv-bubble-text">{item.ai_response}</div>
                    </div>
                  </div>
                </div>

                {/* Card Footer: Intent, Device Actions, Audio Player */}
                <div className="hm-conv-card-footer">
                  <div className="hm-conv-badges-wrap">
                    {item.device_action && (
                      <span className="hm-conv-pill-action" title="Hành động điều khiển phần cứng">
                        <Icon name="power" />
                        <span>Kích hoạt: {item.device_action}</span>
                      </span>
                    )}

                    {item.intent && item.intent !== "real_control" && (
                      <span className="hm-conv-pill-intent" title="Ý định phân loại">
                        <span>Ý định: {item.intent}</span>
                      </span>
                    )}
                  </div>

                  {Boolean(item.audio_url || item.ai_response) && (
                    <button
                      type="button"
                      className={`hm-conv-audio-btn ${isPlaying ? "playing" : ""}`}
                      onClick={() => handlePlayAudio(item)}
                      title={isPlaying ? "Dừng phát" : "Nghe lại giọng nói AI"}
                    >
                      <div className="hm-soundwave">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                      <span>{isPlaying ? "Đang phát..." : "Nghe lại giọng AI"}</span>
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

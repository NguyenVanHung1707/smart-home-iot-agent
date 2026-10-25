import { useEffect, useRef, useState } from "react";
import { onCloudMqttState, publishDeviceCommand } from "../../api/cloudMqtt";

export interface MediaTrackInfo {
  track: string;
  artist?: string;
  audioUrl?: string;
  youtubeUrl?: string;
  thumbnail?: string;
}

const DEFAULT_TRACK: MediaTrackInfo = {
  track: "Lạc Trôi",
  artist: "Sơn Tùng M-TP",
  audioUrl: "/xiaozhi/audio/lac_troi_sample.wav",
  youtubeUrl: "https://www.youtube.com/watch?v=Llw9Q6akRo4",
  thumbnail: "https://i.ytimg.com/vi/Llw9Q6akRo4/hqdefault.jpg",
};

export function FloatingMediaPlayer({
  initialTrack,
  onNotify,
}: {
  initialTrack?: MediaTrackInfo;
  onNotify?: (msg: string) => void;
}) {
  const [currentTrack, setCurrentTrack] = useState<MediaTrackInfo>(initialTrack || DEFAULT_TRACK);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [progress, setProgress] = useState<number>(0);
  const [duration, setDuration] = useState<number>(60);
  const [volume, setVolume] = useState<number>(0.85);
  const [minimized, setMinimized] = useState<boolean>(false);
  const [visible, setVisible] = useState<boolean>(true);
  const [playingOnEsp32, setPlayingOnEsp32] = useState<boolean>(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Đồng bộ với audio element
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    audio.volume = volume;

    const handleTimeUpdate = () => {
      setProgress(audio.currentTime);
      if (audio.duration && !isNaN(audio.duration)) {
        setDuration(audio.duration);
      }
    };

    const handleEnded = () => {
      setIsPlaying(false);
      setProgress(0);
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    audio.addEventListener("timeupdate", handleTimeUpdate);
    audio.addEventListener("ended", handleEnded);
    audio.addEventListener("play", handlePlay);
    audio.addEventListener("pause", handlePause);

    return () => {
      audio.removeEventListener("timeupdate", handleTimeUpdate);
      audio.removeEventListener("ended", handleEnded);
      audio.removeEventListener("play", handlePlay);
      audio.removeEventListener("pause", handlePause);
    };
  }, [volume]);

  // Lắng nghe sự kiện MQTT khi ESP32 hoặc Web phát bài mới
  useEffect(() => {
    const unsubscribe = onCloudMqttState((data) => {
      if (data.deviceId === "gateway-speaker" || data.deviceId === "hub-speaker") {
        const payload = data.rawPayload || {};
        if (payload.action === "play" || payload.state?.playing) {
          const track = payload.track || payload.state?.track || "Lạc Trôi";
          const audioUrl = payload.audio_url || payload.state?.audio_stream_url || "/xiaozhi/audio/lac_troi_sample.wav";
          const youtubeUrl = payload.url || payload.state?.media_url;
          setCurrentTrack((prev) => ({
            ...prev,
            track,
            audioUrl,
            youtubeUrl: youtubeUrl || prev.youtubeUrl,
          }));
          setVisible(true);
        }
      }
    });

    return () => unsubscribe();
  }, []);

  const togglePlayWeb = async () => {
    const audio = audioRef.current;
    if (!audio) return;

    if (isPlaying) {
      audio.pause();
    } else {
      try {
        await audio.play();
        if (onNotify) {
          onNotify(`Đang phát '${currentTrack.track}' trên Trình duyệt Web!`);
        }
      } catch (err) {
        console.warn("[Media Player] Autoplay bị chặn bởi trình duyệt:", err);
      }
    }
  };

  const triggerPlayBoth = async () => {
    // 1. Phát trên Web
    const audio = audioRef.current;
    if (audio) {
      try {
        await audio.play();
      } catch (err) {
        console.warn("[Media Player] Web audio play error:", err);
      }
    }

    // 2. Bắn lệnh MQTT để Loa ESP32 AI Gateway phát song song
    setPlayingOnEsp32(true);
    const esp32AudioUrl = "http://192.168.1.105:8093/xiaozhi/audio/lac_troi_sample.wav";
    publishDeviceCommand("gateway-speaker", "play", {
      action: "play",
      track: currentTrack.track,
      audio_url: esp32AudioUrl,
    });

    if (onNotify) {
      onNotify(`Đã kích hoạt phát '${currentTrack.track}' đồng thời trên ESP32 AI Gateway & WEB!`);
    }

    setTimeout(() => setPlayingOnEsp32(false), 3000);
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const nextTime = Number(e.target.value);
    setProgress(nextTime);
    if (audioRef.current) {
      audioRef.current.currentTime = nextTime;
    }
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const nextVol = Number(e.target.value);
    setVolume(nextVol);
    if (audioRef.current) {
      audioRef.current.volume = nextVol;
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  };

  if (!visible) return null;

  return (
    <div className={`floating-music-bar ${minimized ? "minimized" : ""}`} role="region" aria-label="Trình phát nhạc thông minh">
      <audio ref={audioRef} src={currentTrack.audioUrl} preload="auto" />

      {minimized ? (
        <div className="mini-music-pill" onClick={() => setMinimized(false)}>
          <span className={`disc-spin ${isPlaying ? "spinning" : ""}`}>🎵</span>
          <span className="mini-title">{currentTrack.track}</span>
          <button
            type="button"
            className="mini-play-btn"
            onClick={(e) => {
              e.stopPropagation();
              void togglePlayWeb();
            }}
          >
            {isPlaying ? "⏸" : "▶"}
          </button>
        </div>
      ) : (
        <div className="music-bar-container">
          {/* Cột 1: Thông tin bài hát & Thumbnail */}
          <div className="music-info-col">
            <div className={`music-thumb-wrap ${isPlaying ? "spinning" : ""}`}>
              {currentTrack.thumbnail ? (
                <img src={currentTrack.thumbnail} alt={currentTrack.track} className="music-thumb" />
              ) : (
                <div className="music-thumb-placeholder">🎵</div>
              )}
            </div>
            <div className="music-meta">
              <strong className="track-title" title={currentTrack.track}>
                {currentTrack.track}
              </strong>
              <small className="track-artist">{currentTrack.artist || "Sơn Tùng M-TP"}</small>
              <div className="playback-badges">
                <span className="badge-web">🌐 WEB</span>
                <span className="badge-esp32">⚡ ESP32 I2S</span>
              </div>
            </div>
          </div>

          {/* Cột 2: Điều khiển chính & Thanh thời gian */}
          <div className="music-controls-col">
            <div className="control-buttons">
              <button
                type="button"
                className={`btn-play-sync ${playingOnEsp32 ? "active" : ""}`}
                onClick={() => void triggerPlayBoth()}
                title="Bấm để phát đồng thời trên cả Loa ESP32 AI và Loa Web"
              >
                <span>🔥 Phát cả ESP32 & WEB</span>
              </button>

              <button
                type="button"
                className="btn-play-pause"
                onClick={() => void togglePlayWeb()}
                title={isPlaying ? "Tạm dừng trên Web" : "Phát trên Web"}
              >
                {isPlaying ? (
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                    <rect x="6" y="4" width="4" height="16" rx="1" />
                    <rect x="14" y="4" width="4" height="16" rx="1" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                )}
              </button>

              {currentTrack.youtubeUrl && (
                <a
                  href={currentTrack.youtubeUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-youtube-link"
                  title="Mở xem MV gốc trên YouTube"
                >
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
                  </svg>
                  <span>MV YouTube</span>
                </a>
              )}
            </div>

            <div className="music-progress-row">
              <span className="time-text">{formatTime(progress)}</span>
              <input
                type="range"
                min={0}
                max={duration || 60}
                step={0.5}
                value={progress}
                onChange={handleSeek}
                className="music-progress-bar"
                aria-label="Tiến trình bài hát"
              />
              <span className="time-text">{formatTime(duration)}</span>
            </div>
          </div>

          {/* Cột 3: Âm lượng & Nút đóng/thu nhỏ */}
          <div className="music-actions-col">
            <div className="volume-control">
              <span className="volume-icon">🔊</span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={volume}
                onChange={handleVolumeChange}
                className="volume-slider"
                title={`Âm lượng: ${Math.round(volume * 100)}%`}
                aria-label="Âm lượng Web"
              />
            </div>

            <button
              type="button"
              className="btn-window-action"
              onClick={() => setMinimized(true)}
              title="Thu nhỏ thanh phát nhạc"
              aria-label="Thu nhỏ"
            >
              _
            </button>
            <button
              type="button"
              className="btn-window-action close"
              onClick={() => {
                if (audioRef.current) audioRef.current.pause();
                setVisible(false);
              }}
              title="Đóng trình phát nhạc"
              aria-label="Đóng"
            >
              &times;
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

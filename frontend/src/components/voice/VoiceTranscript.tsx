import { Icon } from "../shared/Icon";

export function VoiceTranscript({ transcript }: { transcript: string }) {
  return (
    <div className={`hm-voice-transcript ${transcript ? "active" : ""}`} aria-live="polite">
      <div className="hm-transcript-header">
        <span className="hm-transcript-title">
          <Icon name="sparkles" />
          <b>Nhận diện giọng nói (Faster-Whisper GPU)</b>
        </span>
        <div className="hm-voice-soundbars" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
        </div>
      </div>
      <p className={transcript ? "hm-transcript-content" : "hm-transcript-content empty"}>
        {transcript || "Đang chuyển giọng nói tiếng Việt thành văn bản theo thời gian thực..."}
      </p>
    </div>
  );
}

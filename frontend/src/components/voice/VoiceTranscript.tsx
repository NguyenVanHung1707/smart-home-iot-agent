import { Icon } from "../shared/Icon";

export function VoiceTranscript({ transcript }: { transcript: string }) {
  return (
    <div className={`hm-voice-transcript ${transcript ? "active" : ""}`} aria-live="polite">
      <span>
        <Icon name="sparkles" />
        <b>Nhận diện giọng nói (Realtime STT)</b>
      </span>
      <p className={transcript ? "" : "empty"}>
        {transcript || "Nội dung bạn nói sẽ xuất hiện ở đây theo thời gian thực..."}
      </p>
    </div>
  );
}

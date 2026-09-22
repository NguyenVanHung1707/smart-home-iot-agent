import { Icon } from "../shared/Icon";

export function FloatingVoiceButton({ listening, onClick }: { listening: boolean; onClick: () => void }) {
  return (
    <section className={`hm-floating-voice ${listening ? "active" : ""}`} aria-label="Điều khiển nhà bằng giọng nói từ trang Phòng">
      <button
        type="button"
        className="hm-floating-voice-button"
        onClick={onClick}
        aria-label={listening ? "Dừng nghe" : "Bật trợ lý giọng nói"}
      >
        <Icon name="mic" />
        <span>Trợ lý</span>
      </button>
    </section>
  );
}

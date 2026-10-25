import { Icon } from "../shared/Icon";

export function VoiceComposer({
  listening,
  disabled,
  statusText,
  onToggle,
}: {
  listening: boolean;
  disabled: boolean;
  statusText: string;
  onToggle: () => void;
}) {
  return (
    <div className="hm-voice-composer">
      <div className="hm-voice-orb-wrapper">
        <button
          type="button"
          className={`hm-voice-orb ${listening ? "listening" : ""} ${disabled ? "busy" : ""}`}
          disabled={disabled}
          onClick={onToggle}
          aria-label={listening ? "Dừng lắng nghe" : "Bắt đầu nói với Xiaozhi"}
        >
          <span className="hm-orb-halo" />
          <span className="hm-orb-core" />
          <Icon name={listening ? "micOff" : "mic"} />
        </button>
      </div>
      <p className={`hm-voice-status-text ${listening ? "is-listening" : ""} ${disabled ? "is-busy" : ""}`} aria-live="polite">
        {statusText}
      </p>
    </div>
  );
}

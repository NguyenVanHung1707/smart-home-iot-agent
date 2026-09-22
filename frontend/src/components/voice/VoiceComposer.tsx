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
      <button
        type="button"
        className={`hm-voice-orb ${listening ? "listening" : ""}`}
        disabled={disabled}
        onClick={onToggle}
        aria-label={listening ? "Dừng nghe" : "Bắt đầu nghe"}
      >
        <span />
        <Icon name="mic" />
      </button>
      <p className={`hm-voice-status-text ${listening ? "is-listening" : ""}`} aria-live="polite">
        {statusText}
      </p>
    </div>
  );
}

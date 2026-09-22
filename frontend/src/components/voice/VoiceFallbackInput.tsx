import { Icon } from "../shared/Icon";

export function VoiceFallbackInput({
  value,
  canSend,
  onChange,
  onSend,
}: {
  value: string;
  canSend: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
}) {
  return (
    <div className="hm-voice-fallback">
      <textarea
        rows={2}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (canSend) onSend();
          }
        }}
        aria-label="Nhập câu lệnh bằng bàn phím"
        placeholder="Hoặc gõ câu lệnh tiếng Việt tại đây (Enter để gửi)..."
      />
      <button
        type="button"
        disabled={!canSend}
        onClick={onSend}
        aria-label="Gửi lệnh"
        className="hm-voice-send-btn"
      >
        <Icon name="arrowUp" />
      </button>
    </div>
  );
}

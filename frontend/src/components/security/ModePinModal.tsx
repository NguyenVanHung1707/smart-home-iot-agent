import { FormEvent, useState } from "react";
import { useDialogFocus } from "../../hooks/useDialogFocus";
import { Icon } from "../shared/Icon";

export function ModePinModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const dialogRef = useDialogFocus<HTMLElement>(open, onClose);

  if (!open) return null;

  const handleKeypadPress = (val: string) => {
    if (pin.length < 6) {
      setPin((cur) => cur + val);
      setError("");
    }
  };

  const handleBackspace = () => {
    setPin((cur) => cur.slice(0, -1));
    setError("");
  };

  const handleClear = () => {
    setPin("");
    setError("");
  };

  const handleSubmit = (e?: FormEvent) => {
    e?.preventDefault();
    if (pin !== "2004") {
      setError("Mã PIN không chính xác. Vui lòng thử lại.");
      return;
    }
    setPin("");
    setError("");
    onSuccess();
    onClose();
  };

  return (
    <div className="hm-modal-backdrop" role="presentation" onClick={onClose}>
      <section
        ref={dialogRef}
        className="hm-pin-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="hm-mode-pin-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="hm-pin-head">
          <div className="hm-pin-icon-wrap">
            <Icon name="mqtt" />
          </div>
          <div>
            <strong id="hm-mode-pin-title">Xác thực Mô hình Thông minh</strong>
            <small>Chế độ ESP32 MQTT Thật</small>
          </div>
          <button type="button" className="hm-icon-button" onClick={onClose} aria-label="Đóng modal PIN">
            <Icon name="close" />
          </button>
        </header>

        <p className="hm-pin-desc">
          Vui lòng nhập mã PIN bảo mật 4 chữ số để kết nối và điều khiển mô hình phần cứng thật.
        </p>

        <form onSubmit={handleSubmit}>
          <div className="hm-pin-display">
            <input
              type="password"
              inputMode="numeric"
              maxLength={6}
              value={pin}
              autoFocus
              autoComplete="off"
              placeholder="••••"
              onChange={(e) => {
                setPin(e.target.value);
                setError("");
              }}
              aria-label="Mã PIN 4 số"
            />
          </div>

          {error ? <div className="hm-pin-error" role="alert">{error}</div> : null}

          <div className="hm-pin-keypad" aria-label="Bàn phím số PIN">
            {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((num) => (
              <button
                key={num}
                type="button"
                className="hm-pin-key"
                onClick={() => handleKeypadPress(num)}
              >
                {num}
              </button>
            ))}
            <button type="button" className="hm-pin-key aux" onClick={handleClear}>
              C
            </button>
            <button type="button" className="hm-pin-key" onClick={() => handleKeypadPress("0")}>
              0
            </button>
            <button type="button" className="hm-pin-key aux" onClick={handleBackspace} aria-label="Xóa số">
              ⌫
            </button>
          </div>

          <div className="hm-pin-actions">
            <button type="button" className="hm-pin-btn-cancel" onClick={onClose}>
              Hủy
            </button>
            <button type="submit" className="hm-pin-btn-submit" disabled={!pin}>
              Xác nhận
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

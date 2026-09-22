import { FormEvent, useState } from "react";
import { useDialogFocus } from "../../hooks/useDialogFocus";
import type { Device } from "../../types";
import { Icon } from "../shared/Icon";

export function PinModal({
  device,
  open,
  onClose,
  onUnlockSuccess,
}: {
  device: Device | null;
  open: boolean;
  onClose: () => void;
  onUnlockSuccess: (device: Device) => Promise<void>;
}) {
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const dialogRef = useDialogFocus<HTMLElement>(open, onClose);

  if (!open || !device) return null;

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

  const handleSubmit = async (e?: FormEvent) => {
    e?.preventDefault();
    if (pin !== "1234") {
      setError("Mật khẩu PIN không chính xác! Vui lòng thử lại.");
      return;
    }
    setBusy(true);
    try {
      await onUnlockSuccess(device);
      setPin("");
      setError("");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Mở khóa thất bại.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="hm-modal-backdrop" role="presentation" onClick={onClose}>
      <section
        ref={dialogRef}
        className="hm-pin-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="hm-pin-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="hm-pin-head">
          <div className="hm-pin-icon-wrap">
            <Icon name="lock" />
          </div>
          <div>
            <strong id="hm-pin-title">Xác thực Mở Khóa An Toàn</strong>
            <small>{device.name} ({device.room})</small>
          </div>
          <button type="button" className="hm-icon-button" onClick={onClose} aria-label="Đóng modal PIN">
            <Icon name="close" />
          </button>
        </header>

        <p className="hm-pin-desc">
          Vui lòng nhập mã PIN bảo mật 4 chữ số của quản trị viên để mở khóa cửa.
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
            <button type="button" className="hm-pin-btn-cancel" onClick={onClose} disabled={busy}>
              Hủy
            </button>
            <button type="submit" className="hm-pin-btn-submit" disabled={!pin || busy}>
              {busy ? "Đang mở..." : "Mở khóa"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

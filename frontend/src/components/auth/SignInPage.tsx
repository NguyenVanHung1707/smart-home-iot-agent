import { useState } from "react";
import type { ThemeMode } from "../../types";
import { Icon } from "../shared/Icon";

export function SignInPage({
  theme,
  onToggleTheme,
  onSignIn,
  onBack,
}: {
  theme: ThemeMode;
  onToggleTheme: () => void;
  onSignIn: (email: string, password: string) => Promise<unknown>;
  onBack: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const nextThemeLabel = theme === "dark" ? "Chuyển sang light mode" : "Chuyển sang dark mode";

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    const cleanEmail = email.trim();
    if (!cleanEmail || !password) {
      setError("Vui lòng nhập đầy đủ email và mật khẩu.");
      return;
    }
    if (password.length < 8) {
      setError("Mật khẩu phải có ít nhất 8 ký tự.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await onSignIn(cleanEmail, password);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không đăng nhập được vào Hub.");
    } finally {
      setBusy(false);
    }
  }

  async function handleQuickLogin(quickEmail: string, quickPass: string) {
    if (busy) return;
    setEmail(quickEmail);
    setPassword(quickPass);
    setBusy(true);
    setError("");
    try {
      await onSignIn(quickEmail, quickPass);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không đăng nhập được vào Hub.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="hm-auth">
      <div className="hm-auth-aside">
        <button type="button" className="hm-auth-brand" onClick={onBack}>
          <span><Icon name="house" /></span>
          <b>HomeMind</b>
        </button>
        <h2>Điều khiển ngôi nhà theo cách của bạn</h2>
        <p>
          Toàn bộ nhận diện giọng nói, suy luận và điều khiển thiết bị chạy ngay trong Hub tại nhà.
          Không gửi dữ liệu ra cloud.
        </p>
        <ul className="hm-auth-points">
          <li><Icon name="mic" /><span>Hiểu tiếng Việt tự nhiên</span></li>
          <li><Icon name="cpu" /><span>Tự hiểu và xử lý nhiều bước</span></li>
          <li><Icon name="shield" /><span>An toàn với xác nhận bảo mật</span></li>
        </ul>
      </div>

      <section className="hm-auth-panel">
        <div className="hm-auth-panel-top">
          <button type="button" className="hm-auth-back" onClick={onBack}>
            <Icon name="arrowLeft" />
            <span>Về trang chủ</span>
          </button>
          <button
            type="button"
            className="hm-theme-toggle"
            onClick={onToggleTheme}
            aria-label={nextThemeLabel}
            title={nextThemeLabel}
          >
            <Icon name={theme === "dark" ? "sun" : "moon"} />
            <span>{theme === "dark" ? "Light" : "Dark"}</span>
          </button>
        </div>

        <header className="hm-auth-head">
          <h1>Đăng nhập Hub</h1>
          <p>Dùng tài khoản chủ nhà hoặc thành viên đã được cấp.</p>
        </header>

        <form className="hm-auth-form" onSubmit={handleSubmit} noValidate>
          <label className="hm-field">
            <span>Email</span>
            <input
              type="email"
              name="email"
              autoComplete="email"
              placeholder="ban@homemind.local"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              disabled={busy}
              required
            />
          </label>

          <label className="hm-field">
            <span>Mật khẩu</span>
            <div className="hm-field-affix">
              <input
                type={showPassword ? "text" : "password"}
                name="password"
                autoComplete="current-password"
                placeholder="Tối thiểu 8 ký tự"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={busy}
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((visible) => !visible)}
                aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
              >
                <Icon name={showPassword ? "lock" : "unlock"} />
              </button>
            </div>
          </label>

          {error ? (
            <p className="hm-auth-error" role="alert">
              <Icon name="alert" />
              <span>{error}</span>
            </p>
          ) : null}

          <button type="submit" className="hm-auth-submit" disabled={busy}>
            {busy ? "Đang xác thực..." : "Đăng nhập"}
          </button>

          <div className="hm-quick-login-section">
            <div className="hm-quick-login-title">
              <span>Đăng nhập nhanh</span>
            </div>
            <div className="hm-quick-login-grid">
              <button
                type="button"
                className="hm-quick-login-btn"
                disabled={busy}
                onClick={() => void handleQuickLogin("admin@homing.dev", "Admin@123456")}
              >
                <div className="hm-quick-login-btn-head">
                  <Icon name="shield" />
                  <span>Chủ nhà</span>
                </div>
                <span className="hm-quick-login-btn-sub">admin@homing.dev</span>
              </button>

              <button
                type="button"
                className="hm-quick-login-btn"
                disabled={busy}
                onClick={() => void handleQuickLogin("member@homing.dev", "Member@123456")}
              >
                <div className="hm-quick-login-btn-head">
                  <Icon name="house" />
                  <span>Gia đình</span>
                </div>
                <span className="hm-quick-login-btn-sub">member@homing.dev</span>
              </button>
            </div>
          </div>
        </form>
      </section>
    </main>
  );
}

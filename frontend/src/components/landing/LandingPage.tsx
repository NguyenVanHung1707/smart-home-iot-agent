import { useEffect, useState } from "react";
import type { ThemeMode } from "../../types";
import { Icon } from "../shared/Icon";
import { DeviceArt, MicArt } from "./deviceArt";
import {
  landingCommands,
  landingFaqs,
  landingFlowDevices,
  landingPipeline,
  landingSecurity,
  landingStats,
} from "./landingContent";

const navAnchors = [
  { id: "cach-hoat-dong", label: "Cách hoạt động" },
  { id: "bao-mat", label: "Bảo mật" },
  { id: "cau-hoi", label: "Câu hỏi" },
];

export function LandingPage({
  theme,
  onToggleTheme,
  onSignIn,
}: {
  theme: ThemeMode;
  onToggleTheme: () => void;
  onSignIn: () => void;
}) {
  const nextThemeLabel = theme === "dark" ? "Chuyển sang light mode" : "Chuyển sang dark mode";

  return (
    <div className="hm-landing">
      <header className="hm-landing-nav">
        <a className="hm-landing-logo" href="#top">
          <span><Icon name="house" /></span>
          <b>HomeMind</b>
          <em>Hub</em>
        </a>

        <nav aria-label="Mục lục trang">
          {navAnchors.map((anchor) => (
            <a key={anchor.id} href={`#${anchor.id}`}>{anchor.label}</a>
          ))}
        </nav>

        <div className="hm-landing-nav-actions">
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
          <button type="button" className="hm-landing-btn primary" onClick={onSignIn}>
            Đăng nhập
          </button>
        </div>
      </header>

      <main id="top">
        <LandingHero onSignIn={onSignIn} />
        <LandingStats />
        <LandingFlow />
        <LandingPipeline />
        <LandingLocalVsCloud />
        <LandingSecurity />
        <LandingFaq />
      </main>

      <footer className="hm-landing-footer">
        <span>HomeMind Hub — Trợ lý nhà thông minh.</span>
        <span>Nhà của bạn, cách của bạn</span>
      </footer>
    </div>
  );
}

function LandingHero({ onSignIn }: { onSignIn: () => void }) {
  return (
    <section className="hm-landing-hero">
      <div className="hm-landing-hero-copy">
        <h1>
          Nhà của bạn.<br />
          <em>Cách của bạn.</em>
        </h1>
        <p className="hm-landing-lead">
          HomeMind nghe, suy luận và điều khiển thiết bị ngay trên Hub tại nhà — tiện lợi, an toàn, thông minh
        </p>
        <div className="hm-landing-hero-actions">
          <button type="button" className="hm-landing-btn primary lg" onClick={onSignIn}>
            Đăng nhập ngay
          </button>
          <a className="hm-landing-btn ghost lg" href="#cach-hoat-dong">
            Xem cách hoạt động
          </a>
        </div>
      </div>

      <div className="hm-landing-hero-visual" aria-hidden="true">
        <div className="hm-landing-orb" />
        <div className="hm-landing-pulse">
          <span /><span /><span />
        </div>
        <div className="hm-landing-hero-chip">
          <Icon name="mic" />
          <span>Đang nghe…</span>
        </div>
      </div>
    </section>
  );
}

function LandingStats() {
  return (
    <section className="hm-landing-stats" aria-label="Số liệu hệ thống">
      {landingStats.map((stat) => (
        <div key={stat.label}>
          <b>{stat.value}</b>
          <span>{stat.label}</span>
        </div>
      ))}
    </section>
  );
}

/** Bus ngang trong hệ toạ độ SVG 600x420; thiết bị nằm 3 cột x 2 hàng quanh bus. */
const flowBusY = 210;
const flowColumnX = [100, 300, 500];

/** Nhánh rẽ từ bus lên (hàng trên) hoặc xuống (hàng dưới) tới chân thiết bị. */
function flowStub(x: number, up: boolean) {
  const corner = up ? flowBusY - 12 : flowBusY + 12;
  const endY = up ? 150 : 270;
  return `M${x - 46} ${flowBusY} H${x - 12} Q${x} ${flowBusY} ${x} ${corner} V${endY}`;
}

function LandingFlow() {
  const [index, setIndex] = useState(0);
  const [phase, setPhase] = useState<"listening" | "acting">("listening");

  useEffect(() => {
    const toActing = window.setTimeout(() => setPhase("acting"), 1600);
    const next = window.setTimeout(() => {
      setPhase("listening");
      setIndex((current) => (current + 1) % landingCommands.length);
    }, 5200);
    return () => {
      window.clearTimeout(toActing);
      window.clearTimeout(next);
    };
  }, [index]);

  const active = landingCommands[index];
  const isActing = phase === "acting";

  return (
    <section className="hm-landing-section hm-landing-flow">
      <div className="hm-landing-section-head">
        <h2>Một câu nói, nhiều việc được làm</h2>
        <p>Agent tách câu ghép, hỏi lại khi thiếu thông tin và từ chối khi câu lệnh không phải mệnh lệnh thật.</p>
      </div>

      <div className={`hm-landing-flow-stage${isActing ? " is-acting" : ""}`}>
        <div className="hm-landing-flow-hub">
          <span className="hm-landing-flow-lead" aria-hidden="true" />
          <div className="hm-landing-flow-core">
            <MicArt />
          </div>

          <div className="hm-landing-flow-say">
            <span className={`hm-landing-wave${isActing ? "" : " active"}`} aria-hidden="true">
              <span /><span /><span /><span /><span /><span /><span />
            </span>

            <div className="hm-landing-flow-bubbles">
              <p className="hm-landing-flow-bubble user" key={`say-${index}`}>
                “{active.say}”
              </p>
              {isActing ? (
                <p className="hm-landing-flow-bubble hub" key={`reply-${index}`}>
                  {active.reply}
                </p>
              ) : (
                <p className="hm-landing-flow-bubble hub is-thinking">Đang phân tích lệnh trên Hub…</p>
              )}
            </div>
          </div>
        </div>

        <div className="hm-landing-flow-web">
          <svg
            className="hm-landing-flow-cable"
            viewBox="0 0 600 420"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path className="hm-landing-bus" d={`M0 ${flowBusY} H${flowColumnX[flowColumnX.length - 1]}`} vectorEffect="non-scaling-stroke" />
            {landingFlowDevices.map((device, position) => {
              const up = position < 3;
              const x = flowColumnX[position % 3];
              const lit = isActing && active.targets.includes(device.id);
              return (
                <g key={device.id} className={`hm-landing-branch${lit ? " lit" : ""}`}>
                  <path d={flowStub(x, up)} vectorEffect="non-scaling-stroke" />
                  <circle cx={x} cy={up ? 150 : 270} r="4.5" />
                </g>
              );
            })}
          </svg>

          <ul className="hm-landing-flow-devices">
            {landingFlowDevices.map((device) => (
              <li
                key={device.id}
                className={isActing && active.targets.includes(device.id) ? "lit" : ""}
                role="img"
                aria-label={device.label}
              >
                <DeviceArt id={device.id} />
              </li>
            ))}
          </ul>
        </div>
      </div>

    </section>
  );
}

function LandingPipeline() {
  return (
    <section className="hm-landing-section" id="cach-hoat-dong">
      <div className="hm-landing-section-head">
        <h2>Ba bước, tất cả trong nhà</h2>
        <p>Mọi yêu cầu được xử lý ngay trong nhà — nhanh, riêng tư và luôn dưới sự kiểm soát của bạn.</p>
      </div>

      <ol className="hm-landing-pipeline">
        {landingPipeline.map((item) => (
          <li key={item.step}>
            <span className="hm-landing-pipeline-icon"><Icon name={item.icon} /></span>
            <b className="hm-landing-pipeline-step">{item.step}</b>
            <h3>{item.title}</h3>
            <p>{item.detail}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

function LandingLocalVsCloud() {
  return (
    <section className="hm-landing-section hm-landing-compare">
      <div className="hm-landing-section-head">
        <h2>Mọi thứ ngay tại nhà</h2>
        <p>Nhanh, riêng tư và không phụ thuộc Internet.</p>
      </div>

      <div className="hm-landing-compare-grid">
        <article className="hm-landing-compare-card recommended">
          <span><Icon name="sparkles" /></span>
          <h3>Nhanh chóng</h3>
          <p>Phản hồi ngay khi bạn đưa ra yêu cầu.</p>
        </article>

        <article className="hm-landing-compare-card">
          <span><Icon name="shield" /></span>
          <h3>Riêng tư</h3>
          <p>Dữ liệu nhạy cảm được giữ và xử lý trong nhà.</p>
        </article>

        <article className="hm-landing-compare-card">
          <span><Icon name="wifiOff" /></span>
          <h3>Luôn sẵn sàng</h3>
          <p>Các chức năng chính vẫn hoạt động khi không có Internet.</p>
        </article>
      </div>
    </section>
  );
}

function LandingSecurity() {
  return (
    <section className="hm-landing-section" id="bao-mat">
      <div className="hm-landing-section-head">
        <h2>An toàn trước khi hành động</h2>
        <p>Tác vụ an ninh luôn cần thêm một lớp xác nhận của con người.</p>
      </div>

      <div className="hm-landing-cards">
        {landingSecurity.map((item) => (
          <article key={item.title}>
            <span><Icon name={item.icon} /></span>
            <h3>{item.title}</h3>
            <p>{item.detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function LandingFaq() {
  return (
    <section className="hm-landing-section hm-landing-faq" id="cau-hoi">
      <div className="hm-landing-section-head">
        <h2>Vài câu hỏi thường gặp</h2>
      </div>

      <div className="hm-landing-faq-list">
        {landingFaqs.map((faq) => (
          <details key={faq.question}>
            <summary>
              <span>{faq.question}</span>
              <Icon name="arrowRight" />
            </summary>
            <p>{faq.answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

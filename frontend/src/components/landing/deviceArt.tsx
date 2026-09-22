/* Line-art thiết bị cho sơ đồ mạch ở landing.
   Vẽ tay bằng SVG stroke (không thêm thư viện icon mới) nhưng chi tiết hơn
   bộ Icon dùng chung, để người xem nhận ra ngay đèn / điều hòa / quạt / rèm /
   cửa / cảm biến — tương tự bộ line-art của Home Assistant Voice PE. */

import type { ReactElement } from "react";
import type { LandingDeviceId } from "./landingContent";

function Bulb() {
  return (
    <>
      <path d="M48 14a21 21 0 0 0-13 37.5V60h26v-8.5A21 21 0 0 0 48 14Z" />
      <path d="M37 68h22M39 75h18M42 82h12" />
      <path d="M44 34a6 6 0 0 1 8 0" />
    </>
  );
}

function AirConditioner() {
  return (
    <>
      <rect x="14" y="20" width="68" height="26" rx="7" />
      <path d="M20 38h56" />
      <path d="M22 28h12" />
      <path d="M28 58c5-7 11 7 16 0M52 58c5-7 11 7 16 0" />
      <path d="M28 74c5-7 11 7 16 0M52 74c5-7 11 7 16 0" />
    </>
  );
}

/** Quạt cây: lồng bảo vệ + 4 cánh + trục và chân đế. */
function StandFan() {
  const blade = "M48 34C41 27 42 16 48 13c6 3 7 14 0 21Z";
  return (
    <>
      <circle cx="48" cy="36" r="25" />
      {[0, 90, 180, 270].map((angle) => (
        <path key={angle} d={blade} transform={`rotate(${angle} 48 36)`} />
      ))}
      <circle cx="48" cy="36" r="4" />
      <path d="M48 61v18" />
      <path d="M41 79h14v6H41z" />
      <path d="M34 89h28" />
    </>
  );
}

/** Rèm cửa: thanh treo, hai tấm rèm hai bên và diềm rèm vắt qua cửa sổ. */
function Curtains() {
  return (
    <>
      <path d="M12 14h72" />
      <circle cx="9" cy="14" r="2.6" />
      <circle cx="87" cy="14" r="2.6" />
      <path d="M20 14h56v60H20z" />
      <path d="M20 14h13v60H20z" />
      <path d="M24.5 16v58M29 16v58" />
      <path d="M63 14h13v60H63z" />
      <path d="M67 16v58M71.5 16v58" />
      <path d="M33 14c8 12 22 12 30 0" />
      <path d="M14 80h68" />
    </>
  );
}

/** Cửa đang khoá: cánh cửa có bản lề, tay nắm và ổ khoá móc đã đóng. */
function DoorLock() {
  return (
    <>
      <path d="M26 8h44v78H26z" />
      <path d="M18 86h60" />
      <path d="M33 15h30v24H33z" />
      <path d="M26 18h-6M26 70h-6" />
      <circle cx="61" cy="48" r="2.6" />
      <rect x="37" y="54" width="20" height="17" rx="3.5" />
      <path d="M42 54v-4.5a5 5 0 0 1 10 0V54" />
      <path d="M47 61v4" />
    </>
  );
}

/** Cảm biến nhiệt độ: nhiệt kế có bầu thuỷ ngân và vạch chia. */
function Thermometer() {
  return (
    <>
      <path d="M56 58V22a8 8 0 0 0-16 0v36a13 13 0 1 0 16 0Z" />
      <path d="M48 34v28" />
      <circle cx="48" cy="70" r="6" />
      <path d="M60 28h8M60 38h5M60 48h8" />
    </>
  );
}

const art: Record<LandingDeviceId, () => ReactElement> = {
  bulb: Bulb,
  ac: AirConditioner,
  fan: StandFan,
  curtain: Curtains,
  door: DoorLock,
  sensor: Thermometer,
};

export function DeviceArt({ id }: { id: LandingDeviceId }) {
  const Shape = art[id];
  return (
    <svg className="hm-landing-device-art" viewBox="0 0 96 96" aria-hidden="true">
      <Shape />
    </svg>
  );
}

/** Mic đặt ngay điểm bắt đầu của bus mạch. */
export function MicArt() {
  return (
    <svg className="hm-landing-mic-art" viewBox="0 0 96 110" aria-hidden="true">
      <rect className="hm-mic-body" x="33" y="10" width="30" height="56" rx="15" />
      <path className="hm-mic-grille" d="M33 24h30M33 34h30M33 44h30" />
      <path className="hm-mic-arc" d="M22 50v5a26 26 0 0 0 52 0v-5" />
      <path className="hm-mic-stem" d="M48 81v13" />
      <path className="hm-mic-base" d="M32 102h32" />
      <circle className="hm-mic-led" cx="48" cy="19" r="3.5" />
    </svg>
  );
}

import type { IconName } from "../../types";
import type { ReactNode } from "react";

type IconDefinition = string | ReactNode;
const icons: Record<IconName, IconDefinition> = {
  alert: "M12 9v4 M12 17h.01 M10.3 3.9 2.6 17.1A2 2 0 0 0 4.3 20h15.4a2 2 0 0 0 1.7-2.9L13.7 3.9a2 2 0 0 0-3.4 0Z",
  arrowLeft: "M19 12H5 m7 7-7-7 7-7",
  arrowRight: "M5 12h14 m-7-7 7 7-7 7",
  arrowUp: "M12 19V5 M5 12l7-7 7 7",
  bed: "M3 7v12 M21 12v7 M3 12h18 M7 12V9h5v3",
  bell: "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9 M10 21h4",
  chart: "M4 19V5 M4 19h16 M8 16v-5 M12 16V8 M16 16v-3",
  check: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z M9 12l2 2 4-5",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z M12 7v5l3 2",
  close: "M18 6 6 18 M6 6l12 12",
  door: "M14 3H6v18h8 M14 7h4v14h-4z M11 12h.01",
  house: "M3 11l9-7 9 7 M5 10v10h14V10 M9 20v-6h6v6",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z M12 11v5 M12 8h.01",
  list: "M8 6h13 M8 12h13 M8 18h13 M3 6h.01 M3 12h.01 M3 18h.01",
  menu: "M4 6h16 M4 12h16 M4 18h16",
  mic: "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z M19 10v2a7 7 0 0 1-14 0v-2 M12 19v3",
  micOff: "M12 3a3 3 0 0 0-3 3v4 M15 9.3V6a3 3 0 0 0-5.1-2.1 M19 10v2a7 7 0 0 1-.7 3 M5 10v2a7 7 0 0 0 11 5.7 M12 19v3 M3 3l18 18",
  power: "M12 2v10 M18.4 6.6a9 9 0 1 1-12.8 0",
  powerOff: "M12 2v4 M6.8 6.8a9 9 0 0 0 10.4 14.4 M18.4 6.6A9 9 0 0 1 20 17 M3 3l18 18",
  settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z M4 12h2m12 0h2M12 4v2m0 12v2M6.3 6.3l1.4 1.4m8.6 8.6 1.4 1.4m0-11.4-1.4 1.4m-8.6 8.6-1.4 1.4",
  shield: "M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z M9 12l2 2 4-5",
  sofa: "M4 11V8a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v3 M4 14h16v5H4z M2 14v5 M22 14v5",
  sparkles: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8Z M18 16l.8 2.2L21 19l-2.2.8L18 22l-.8-2.2L15 19l2.2-.8Z",
  sun: "M12 4V2 M12 22v-2 M4.93 4.93 3.52 3.52 M20.48 20.48l-1.41-1.41 M4 12H2 M22 12h-2 M4.93 19.07l-1.41 1.41 M20.48 3.52l-1.41 1.41 M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10Z",
  sunrise: "M12 2v8 M4.2 10.2 6 12 M19.8 10.2 18 12 M4 18h16 M6 15a6 6 0 0 1 12 0",
  moon: "M21 13.6A8.5 8.5 0 0 1 10.4 3 7 7 0 1 0 21 13.6Z",
  wifi: "M5 13a10 10 0 0 1 14 0 M8.5 16.5a5 5 0 0 1 7 0 M12 20h.01",
  wifiOff: "M8.5 16.5a5 5 0 0 1 7 0 M2 8.8a15 15 0 0 1 3.1-2.1 M12 20h.01 M17 5.4a15 15 0 0 1 5 3.4 M3 3l18 18",
  x: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z M15 9l-6 6 M9 9l6 6",
  mqtt: "M4 4h16v4H4z M4 10h16v4H4z M4 16h16v4H4z M9 4v16 M15 4v16",
  cpu: "M4 4h16v16H4z M9 9h6v6H9z M9 1v3 M15 1v3 M9 20v3 M15 20v3 M1 9h3 M1 15h3 M20 9h3 M20 15h3",
  lock: "M7 11V7a5 5 0 0 1 10 0v4 M5 11h14v10H5z M12 15v2",
  unlock: "M7 11V7a5 5 0 0 1 9.9-1 M5 11h14v10H5z M12 15v2",
  sliders: "M4 21v-7 M4 10V3 M12 21v-9 M12 8V3 M20 21v-5 M20 12V3 M1 14h6 M9 8h6 M17 16h6",
  refresh: "M21.5 2v6h-6 M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.19",
  plus: "M12 5v14 M5 12h14",
  trash: "M3 6h18 M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6 M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2 M10 11v6 M14 11v6",
  pencil: "M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z",
  kitchen: "M4 3v8a3 3 0 0 0 6 0V3 M7 3v18 M14 3v18 M14 3h6 M14 8h4 M14 13h6",
  desk: "M3 7h18v5H3z M6 12v9m12-9v9M3 21h18",
  bulb: "M9 18h6m-5 3h4M8 14a6 6 0 1 1 8 0c-1 1-1 2-1 4H9c0-2 0-3-1-4Z",
  tv: "M4 5h16v12H4zM8 21h8M12 17v4",
  fan: "M12 12m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0 M12 10c-2-5-7-3-5 0 1 1 3 1 5 0Zm2 2c5-2 3-7 0-5-1 1-1 3 0 5Zm-2 2c2 5 7 3 5 0-1-1-3-1-5 0Z",
  ac: "M3 6h18M5 6v8m14-8v8M7 10h10M8 21l4-7 4 7",
  drop: "M12 3s6 6.1 6 11a6 6 0 0 1-12 0c0-4.9 6-11 6-11Z",
  thermo: "M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0ZM12 5v11",
};

export function Icon({ name }: { name: IconName }) {
  const definition = icons[name] || icons.house;
  return (
    <svg className="hm-icon" viewBox="0 0 24 24" aria-hidden="true">
      {typeof definition === "string" ? <path d={definition} /> : definition}
    </svg>
  );
}

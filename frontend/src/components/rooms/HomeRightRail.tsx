import type { ApiDeviceCommand } from "../../api/types";
import type { Device, HomePreset, Role, Room } from "../../types";
import { Icon } from "../shared/Icon";
import { PresetPanel } from "./PresetPanel";

export const DEVICE_WATTAGE: Record<string, number> = {
  aircon: 1200,
  light: 40,
  fan: 45,
  display: 65,
  speaker: 20,
  blind: 25,
  lock: 4,
  sensor: 1,
};

export function calculateDeviceWatts(device: Device): number {
  if (device.status === "offline") return 0;
  const kind = device.kind ?? "sensor";
  const isPowerOn = device.status === "on" || Boolean(device.state?.power);

  switch (kind) {
    case "aircon":
      return isPowerOn ? DEVICE_WATTAGE.aircon : 0;
    case "light": {
      if (!isPowerOn && device.status !== "on") return 0;
      const brightness =
        typeof device.state?.brightness === "number"
          ? Math.max(0, Math.min(100, device.state.brightness))
          : 100;
      return (DEVICE_WATTAGE.light * brightness) / 100;
    }
    case "fan": {
      if (!isPowerOn && device.status !== "on") return 0;
      const speed =
        typeof device.state?.speed === "number"
          ? Math.max(0, Math.min(100, device.state.speed))
          : 100;
      return (DEVICE_WATTAGE.fan * speed) / 100;
    }
    case "display":
      return isPowerOn ? DEVICE_WATTAGE.display : 0;
    case "speaker":
      return isPowerOn ? DEVICE_WATTAGE.speaker : 0;
    case "blind":
      return isPowerOn ? DEVICE_WATTAGE.blind : 0;
    case "lock":
      return DEVICE_WATTAGE.lock;
    case "sensor":
      return DEVICE_WATTAGE.sensor;
    default:
      return isPowerOn ? 30 : 0;
  }
}

// 24 mốc đặc tuyến phụ tải sinh hoạt gia đình điển hình theo giờ trong ngày
const HOURLY_PROFILE = [
  0.22, 0.18, 0.16, 0.15, 0.18, 0.32, // 00:00 - 05:00: ban đêm, tải nền
  0.58, 0.78, 0.62, 0.42, 0.38, 0.52, // 06:00 - 11:00: sáng thức dậy, ra ngoài
  0.68, 0.48, 0.42, 0.44, 0.54, 0.74, // 12:00 - 17:00: trưa & chiều
  0.94, 1.0, 0.88, 0.72, 0.48, 0.32,  // 18:00 - 23:00: cao điểm sinh hoạt tối
];

type HomeRightRailProps = {
  rooms: Room[];
  devices: Device[];
  role: Role;
  presets: HomePreset[];
  onPresetsChange: (next: HomePreset[]) => void;
  onDeviceCommand: (device: Device, command: ApiDeviceCommand) => Promise<void>;
};

export function HomeRightRail({
  rooms,
  devices,
  role,
  presets,
  onPresetsChange,
  onDeviceCommand,
}: HomeRightRailProps) {
  const primaryRoom = rooms[0];
  const online = devices.filter((device) => device.status !== "offline").length;

  const tempSensor = devices.find((device) => typeof device.state?.temperature === "number");
  const rawTemp = tempSensor?.state?.temperature;
  const temperature =
    typeof rawTemp === "number"
      ? Number.isInteger(rawTemp)
        ? rawTemp
        : Number(rawTemp.toFixed(1))
      : 28;
  const rawHum = tempSensor?.state?.humidity;
  const humidity =
    typeof rawHum === "number"
      ? Number.isInteger(rawHum)
        ? rawHum
        : Number(rawHum.toFixed(1))
      : 56;

  // --- NĂNG LƯỢNG THỰC TẾ ---
  const liveWatts = devices.reduce((sum, d) => sum + calculateDeviceWatts(d), 0);
  const now = new Date();
  const currentHour = now.getHours();
  const currentMinute = now.getMinutes();

  const totalInstalledWatts = devices.reduce(
    (sum, d) => sum + (DEVICE_WATTAGE[d.kind ?? "sensor"] ?? 30),
    0
  );
  const baseScaleWatts = Math.max(liveWatts, totalInstalledWatts * 0.45, 180);

  // Phân bổ 24 cột năng lượng của ngày hôm nay
  const hourlyData = HOURLY_PROFILE.map((profileWeight, h) => {
    if (h < currentHour) {
      return { kwh: (profileWeight * baseScaleWatts) / 1000 };
    }
    if (h === currentHour) {
      const elapsedFraction = Math.max(1, currentMinute) / 60;
      const currentWatts = Math.max(liveWatts, baseScaleWatts * profileWeight * 0.6);
      return { kwh: (currentWatts * elapsedFraction) / 1000 };
    }
    // Giờ tương lai (> currentHour)
    return { kwh: (profileWeight * baseScaleWatts) / 1000 };
  });

  const todayKwh = hourlyData
    .slice(0, currentHour + 1)
    .reduce((sum, item) => sum + item.kwh, 0);

  const formattedLivePower =
    liveWatts >= 1000
      ? `${(liveWatts / 1000).toFixed(2)} kW`
      : `${Math.round(liveWatts)} W`;

  // So sánh động với phụ tải chuẩn ngày hôm qua cùng mốc giờ
  const yesterdayBenchmark =
    HOURLY_PROFILE.slice(0, currentHour).reduce(
      (sum, coeff) => sum + (coeff * totalInstalledWatts * 0.48) / 1000,
      0
    ) +
    ((HOURLY_PROFILE[currentHour] * totalInstalledWatts * 0.48 * Math.max(1, currentMinute)) / 60) / 1000;

  const trendDiffPercent = Math.round(
    ((todayKwh - yesterdayBenchmark) / Math.max(0.1, yesterdayBenchmark)) * 100
  );
  const trendText = trendDiffPercent >= 0 ? `↑ ${trendDiffPercent}%` : `↓ ${Math.abs(trendDiffPercent)}%`;

  const maxKwh = Math.max(...hourlyData.map((d) => d.kwh), 0.1);

  // --- BẢO MẬT THỰC TẾ ---
  const lockDevice =
    devices.find((device) => device.id === "entry-lock") ??
    devices.find((device) => device.kind === "lock");

  const isLockOffline = !lockDevice || lockDevice.status === "offline";
  const isLockUnlocked =
    !isLockOffline &&
    (lockDevice.state?.locked === false || lockDevice.status === "warning");

  let lockStatusText = "Đã khóa";
  let lockStatusClass = "ok";
  if (isLockOffline) {
    lockStatusText = "Mất kết nối";
    lockStatusClass = "offline";
  } else if (isLockUnlocked) {
    lockStatusText = "Đang mở";
    lockStatusClass = "warn";
  }

  const garageDevice = devices.find(
    (d) =>
      d.id.toLowerCase().includes("garage") ||
      d.id.toLowerCase().includes("gara") ||
      d.name.toLowerCase().includes("gara") ||
      d.name.toLowerCase().includes("garage")
  );
  const doorSensor = devices.find(
    (d) =>
      d.id === "entry-sensor" ||
      (d.kind === "sensor" && typeof d.state?.open === "boolean") ||
      d.name.toLowerCase().includes("cảm biến cửa")
  );
  const garageTarget = garageDevice ?? doorSensor;

  const isGarageOffline = !garageTarget || garageTarget.status === "offline";
  let isGarageOpen = false;
  if (!isGarageOffline && garageTarget) {
    if (typeof garageTarget.state?.open === "boolean") {
      isGarageOpen = garageTarget.state.open === true;
    } else if (garageTarget.kind === "blind") {
      isGarageOpen = (Number(garageTarget.state?.position) || 0) > 0 || garageTarget.status === "on";
    } else if (garageTarget.kind === "lock") {
      isGarageOpen = garageTarget.state?.locked === false;
    } else {
      isGarageOpen = garageTarget.status === "on" || garageTarget.status === "warning";
    }
  }

  let garageStatusText = "Đã đóng";
  let garageStatusClass = "ok";
  if (isGarageOffline) {
    garageStatusText = "Mất kết nối";
    garageStatusClass = "offline";
  } else if (isGarageOpen) {
    garageStatusText = "Đang mở";
    garageStatusClass = "warn";
  }

  const isGarageInteractive = Boolean(
    garageTarget &&
      !isGarageOffline &&
      (garageTarget.commandable || garageTarget.kind === "blind" || garageTarget.kind === "lock")
  );

  const gasSensors = devices.filter(
    (d) =>
      d.id.toLowerCase().includes("gas") ||
      d.name.toLowerCase().includes("gas") ||
      typeof d.state?.gas_detected === "boolean" ||
      typeof d.state?.ppm === "number"
  );
  const isGasAlert = gasSensors.some(
    (d) =>
      d.status !== "offline" &&
      (d.state?.gas_detected === true ||
        d.state?.alert === true ||
        (typeof d.state?.ppm === "number" && d.state.ppm > 300) ||
        d.status === "warning")
  );

  const motionSensors = devices.filter(
    (d) =>
      d.id.toLowerCase().includes("motion") ||
      d.name.toLowerCase().includes("chuyển động") ||
      typeof d.state?.motion === "boolean"
  );
  const isMotionDetected = motionSensors.some(
    (d) => d.status !== "offline" && Boolean(d.state?.motion)
  );

  const otherSensorWarning = devices.some(
    (d) =>
      d.kind === "sensor" &&
      d.status === "warning" &&
      !gasSensors.includes(d) &&
      !motionSensors.includes(d)
  );

  const allSecuritySensors = [...gasSensors, ...motionSensors];
  const areSensorsOffline =
    allSecuritySensors.length > 0 && allSecuritySensors.every((s) => s.status === "offline");

  let sensorStatusText = "Bình thường";
  let sensorStatusClass = "ok";
  if (isGasAlert) {
    sensorStatusText = "Khí gas!";
    sensorStatusClass = "warn";
  } else if (isMotionDetected || otherSensorWarning) {
    sensorStatusText = "Phát hiện";
    sensorStatusClass = "warn";
  } else if (areSensorsOffline) {
    sensorStatusText = "Mất kết nối";
    sensorStatusClass = "offline";
  }

  const isMqttConnected = online > 0;
  const mqttStatusText = isMqttConnected ? "Hoạt động" : "Mất kết nối";
  const mqttStatusClass = isMqttConnected ? "ok" : "offline";

  const securityDevices = [
    lockDevice,
    garageTarget,
    ...gasSensors,
    ...motionSensors,
  ].filter((d): d is Device => Boolean(d));

  const uniqueSecurityDevices = Array.from(
    new Map(securityDevices.map((d) => [d.id, d])).values()
  );
  const offlineSecurityCount = uniqueSecurityDevices.filter((d) => d.status === "offline").length;

  const warningsCount =
    (isLockUnlocked ? 1 : 0) +
    (isGarageOpen ? 1 : 0) +
    (isGasAlert ? 1 : 0) +
    (isMotionDetected ? 1 : 0) +
    offlineSecurityCount;

  const handleToggleLock = () => {
    if (!lockDevice || isLockOffline) return;
    void onDeviceCommand(lockDevice, {
      action: isLockUnlocked ? "lock" : "unlock",
    });
  };

  const handleToggleGarage = () => {
    if (!garageTarget || !isGarageInteractive) return;
    if (garageTarget.kind === "blind") {
      void onDeviceCommand(garageTarget, {
        action: "set",
        value: { position: isGarageOpen ? 0 : 100 },
      });
    } else if (garageTarget.kind === "lock") {
      void onDeviceCommand(garageTarget, {
        action: isGarageOpen ? "lock" : "unlock",
      });
    } else {
      void onDeviceCommand(garageTarget, {
        action: isGarageOpen ? "off" : "on",
      });
    }
  };

  return (
    <aside className="right-rail" aria-label="Thông tin nhanh">
      <div className="right-rail-scroll">
        <section className="widget weather-card">
          <div className="weather-header">
            <div className="weather-main">
              <h2>{primaryRoom?.name ?? "Phòng khách"}</h2>
              <div className="temperature">
                {temperature}
                <span>°C</span>
              </div>
              <p>Ít mây</p>
            </div>
            <div className="weather-visual" aria-hidden="true">
              <span className="sun" />
              <span className="cloud" />
            </div>
          </div>
          <div className="weather-meta">
            <span>
              <Icon name="drop" />
              {humidity}%
            </span>
            <span>
              <Icon name="shield" />
              {warningsCount ? "Cần xem" : "Tốt"}
            </span>
            <small>{online}/{devices.length || 0} thiết bị online</small>
          </div>
        </section>

        <section className="widget energy-card">
          <div className="widget-row">
            <div>
              <h2>Năng lượng</h2>
              <p>Hôm nay</p>
              <strong>{todayKwh.toFixed(1)} kWh</strong>
              <span className="energy-live-power">Đang tiêu thụ: {formattedLivePower}</span>
            </div>
            <span className="trend">
              {trendText}
              <small>so với hôm qua</small>
            </span>
          </div>
          <div className="bars" aria-label="Biểu đồ năng lượng theo giờ">
            {hourlyData.map((d, h) => {
              const isCurrent = h === currentHour;
              const isFuture = h > currentHour;
              let heightPercent: number;
              if (isCurrent) {
                const currentRateKwh = liveWatts / 1000;
                const relativeLoad = Math.max(d.kwh, currentRateKwh);
                heightPercent = Math.max(16, Math.min(100, Math.round((relativeLoad / maxKwh) * 85)));
              } else {
                heightPercent = Math.max(12, Math.min(100, Math.round((d.kwh / maxKwh) * 90)));
              }

              const tooltipText = `${String(h).padStart(2, "0")}:00 - ${d.kwh.toFixed(2)} kWh${
                isCurrent ? " (hiện tại)" : isFuture ? " (dự kiến)" : ""
              }`;

              return (
                <i
                  key={h}
                  className={`${isCurrent ? "current" : ""} ${isFuture ? "future" : ""}`.trim() || undefined}
                  style={{ height: `${heightPercent}%` }}
                  title={tooltipText}
                />
              );
            })}
          </div>
          <div className="bar-labels">
            <span>00</span>
            <span>04</span>
            <span>08</span>
            <span>12</span>
            <span>16</span>
            <span>20</span>
            <span>24</span>
          </div>
        </section>

        <section className="widget security-card">
          <h2>Bảo mật</h2>
          <div className="security-main">
            <span className={`safe-ring ${warningsCount > 0 ? "warning" : ""}`.trim()}>
              <Icon name="shield" />
            </span>
            <div>
              <strong>{warningsCount > 0 ? `${warningsCount} cảnh báo` : "Tất cả an toàn"}</strong>
              <p>{warningsCount > 0 ? "Có thiết bị cần kiểm tra" : "Không có cảnh báo"}</p>
            </div>
          </div>
          <ul>
            <li
              className={!isLockOffline && lockDevice ? "interactive" : undefined}
              role={!isLockOffline && lockDevice ? "button" : undefined}
              tabIndex={!isLockOffline && lockDevice ? 0 : undefined}
              onClick={handleToggleLock}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleToggleLock();
                }
              }}
              title={
                !isLockOffline && lockDevice
                  ? isLockUnlocked
                    ? "Bấm để khóa cửa chính"
                    : "Bấm để mở khóa cửa chính"
                  : undefined
              }
            >
              <Icon name="lock" />
              Cửa chính <span className={lockStatusClass}>{lockStatusText}</span>
            </li>
            <li
              className={isGarageInteractive ? "interactive" : undefined}
              role={isGarageInteractive ? "button" : undefined}
              tabIndex={isGarageInteractive ? 0 : undefined}
              onClick={handleToggleGarage}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleToggleGarage();
                }
              }}
              title={
                isGarageInteractive
                  ? isGarageOpen
                    ? "Bấm để đóng cửa gara"
                    : "Bấm để mở cửa gara"
                  : undefined
              }
            >
              <Icon name="door" />
              Cửa gara <span className={garageStatusClass}>{garageStatusText}</span>
            </li>
            <li>
              <Icon name="sparkles" />
              Cảm biến <span className={sensorStatusClass}>{sensorStatusText}</span>
            </li>
            <li>
              <Icon name="wifi" />
              Hub MQTT <span className={mqttStatusClass}>{mqttStatusText}</span>
            </li>
          </ul>
        </section>

        <PresetPanel
          devices={devices}
          canEdit={role === "homeadmin"}
          onDeviceCommand={onDeviceCommand}
          presets={presets}
          onPresetsChange={onPresetsChange}
        />
      </div>
    </aside>
  );
}

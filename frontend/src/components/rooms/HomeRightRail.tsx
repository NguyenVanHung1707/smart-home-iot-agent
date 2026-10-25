import type { ApiDeviceCommand } from "../../api/types";
import type { Device, HomePreset, Role, Room } from "../../types";
import { Icon } from "../shared/Icon";
import { PresetPanel } from "./PresetPanel";



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

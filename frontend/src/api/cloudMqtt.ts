import mqtt, { type MqttClient } from "mqtt";

export interface CloudMqttConfig {
  brokerUrl: string;
  username: string;
  password: string;
  topicPrefix: string;
  clientId: string;
  autoConnect: boolean;
}

export type MqttConnectionStatus = "disconnected" | "connecting" | "connected" | "error";

export interface MqttTelemetryMessage {
  deviceId: string;
  action?: string;
  value?: number;
  floatVal?: number;
  rawPayload: any;
  timestamp: number;
}

const STORAGE_KEY = "homing-cloud-mqtt-config";

const DEFAULT_CONFIG: CloudMqttConfig = {
  brokerUrl: (typeof window !== "undefined" && import.meta.env.VITE_HIVEMQ_WSS_URL) || "wss://broker.emqx.io:8084/mqtt",
  username: (typeof window !== "undefined" && import.meta.env.VITE_HIVEMQ_USER) || "",
  password: (typeof window !== "undefined" && import.meta.env.VITE_HIVEMQ_PASS) || "",
  topicPrefix: "homing",
  clientId: `homing-web-${Math.random().toString(16).substring(2, 8)}`,
  autoConnect: true,
};

let clientInstance: MqttClient | null = null;
let currentStatus: MqttConnectionStatus = "disconnected";

const statusListeners = new Set<(status: MqttConnectionStatus) => void>();
const stateListeners = new Set<(data: MqttTelemetryMessage) => void>();
const alertListeners = new Set<(alert: any) => void>();

export function getCloudMqttConfig(): CloudMqttConfig {
  if (typeof window === "undefined") return DEFAULT_CONFIG;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_CONFIG;
    return { ...DEFAULT_CONFIG, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_CONFIG;
  }
}

export function saveCloudMqttConfig(cfg: Partial<CloudMqttConfig>): CloudMqttConfig {
  const updated = { ...getCloudMqttConfig(), ...cfg };
  if (typeof window !== "undefined") {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  }
  return updated;
}

function notifyStatus(status: MqttConnectionStatus) {
  currentStatus = status;
  for (const listener of statusListeners) {
    try {
      listener(status);
    } catch (e) {
      console.error("[CloudMQTT] Error in status listener:", e);
    }
  }
}

export function connectCloudMqtt(customConfig?: Partial<CloudMqttConfig>): MqttClient | null {
  const config = { ...getCloudMqttConfig(), ...customConfig };

  if (clientInstance) {
    clientInstance.end(true);
    clientInstance = null;
  }

  notifyStatus("connecting");
  console.log(`[CloudMQTT] Đang kết nối WSS tới ${config.brokerUrl}...`);

  try {
    clientInstance = mqtt.connect(config.brokerUrl, {
      clientId: config.clientId || `homing-web-${Date.now()}`,
      username: config.username || undefined,
      password: config.password || undefined,
      clean: true,
      connectTimeout: 8000,
      reconnectPeriod: 4000,
    });

    clientInstance.on("connect", () => {
      console.log("[CloudMQTT] Đã kết nối thành công qua WSS!");
      notifyStatus("connected");

      const prefix = config.topicPrefix || "homing";
      clientInstance?.subscribe(`${prefix}/devices/+/state`);
      clientInstance?.subscribe(`${prefix}/devices/+/ack`);
      clientInstance?.subscribe(`${prefix}/security/access_log`);
      clientInstance?.subscribe(`${prefix}/gateway/heartbeat`);
    });

    clientInstance.on("message", (topic, payload) => {
      try {
        const text = payload.toString();
        const json = JSON.parse(text);
        const prefix = config.topicPrefix || "homing";

        if (topic.startsWith(`${prefix}/devices/`) && topic.endsWith("/state")) {
          const parts = topic.split("/");
          const deviceId = parts[2];
          const data: MqttTelemetryMessage = {
            deviceId,
            action: json.action,
            value: json.value,
            floatVal: json.float_val,
            rawPayload: json,
            timestamp: Date.now(),
          };
          for (const listener of stateListeners) {
            listener(data);
          }
        } else if (topic.includes("security") || topic.includes("alarm")) {
          for (const listener of alertListeners) {
            listener(json);
          }
        }
      } catch (err) {
        console.warn("[CloudMQTT] Lỗi parse payload message:", err);
      }
    });

    clientInstance.on("error", (err) => {
      console.error("[CloudMQTT] Lỗi kết nối MQTT:", err);
      notifyStatus("error");
    });

    clientInstance.on("close", () => {
      notifyStatus("disconnected");
    });

    clientInstance.on("offline", () => {
      notifyStatus("disconnected");
    });
  } catch (err) {
    console.error("[CloudMQTT] Ngoại lệ khi khởi tạo client:", err);
    notifyStatus("error");
  }

  return clientInstance;
}

export function disconnectCloudMqtt() {
  if (clientInstance) {
    clientInstance.end();
    clientInstance = null;
    notifyStatus("disconnected");
  }
}

export function publishDeviceCommand(deviceId: string, action: string, value: any = 1): boolean {
  if (!clientInstance || currentStatus !== "connected") {
    console.warn("[CloudMQTT] Chưa kết nối, không thể publish lệnh.");
    return false;
  }

  const config = getCloudMqttConfig();
  const topic = `${config.topicPrefix}/devices/${deviceId}/command`;
  const payload = JSON.stringify({
    action,
    value,
    timestamp: Date.now(),
  });

  clientInstance.publish(topic, payload, { qos: 1 }, (err) => {
    if (err) {
      console.error(`[CloudMQTT] Lỗi publish lệnh tới ${topic}:`, err);
    } else {
      console.log(`[CloudMQTT] Đã publish lệnh: ${topic} -> ${payload}`);
    }
  });

  return true;
}

export function publishSpeakerBroadcast(text: string): boolean {
  if (!clientInstance || currentStatus !== "connected") return false;
  const config = getCloudMqttConfig();
  const topic = `${config.topicPrefix}/speaker/say`;
  clientInstance.publish(topic, text);
  return true;
}

export function onCloudMqttStatus(listener: (status: MqttConnectionStatus) => void): () => void {
  statusListeners.add(listener);
  listener(currentStatus);
  return () => statusListeners.delete(listener);
}

export function onCloudMqttState(listener: (data: MqttTelemetryMessage) => void): () => void {
  stateListeners.add(listener);
  return () => stateListeners.delete(listener);
}

export function onCloudMqttAlert(listener: (alert: any) => void): () => void {
  alertListeners.add(listener);
  return () => alertListeners.delete(listener);
}

export function getMqttCurrentStatus(): MqttConnectionStatus {
  return currentStatus;
}

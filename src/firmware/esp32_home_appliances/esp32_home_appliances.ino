/*
 * ============================================================================
 * DỰ ÁN SMART HOME - ESP32 #1: THIẾT BỊ TRONG NHÀ & GIÁM SÁT MÔI TRƯỜNG
 * (KẾT NỐI TỪ XA CLOUD MQTT OVER WSS - wss://mqtt.blask.id.vn:443/mqtt)
 * ============================================================================
 */

#include <Adafruit_Sensor.h>
#include <ArduinoJson.h>
#include <ArduinoWebsockets.h>
#include <DHT.h>
#include <DHT_U.h>
#include <ESP32Servo.h>
#include <PubSubClient.h>
#include <U8g2lib.h>
#include <WiFi.h>
#include <Wire.h>
#include <vector>

// --- THÔNG TIN MẠNG WIFI & CLOUD WSS BROKER ---
char ssid[] = "TP-Link_ED49";
char pass[] = "76664748";

// Địa chỉ Cloud WebSocket Secure (WSS) Broker ngoài Internet
const char* wss_host = "mqtt.blask.id.vn";
const int wss_port = 443;
const char* wss_path = "/mqtt";

// --- ADAPTER LỚP STREAM CHO PUBSUBCLIENT CHẠY QUA WEBSOCKET SECURE (WSS) ---
class WebsocketClientStream : public Client {
private:
  websockets::WebsocketsClient* _ws;
  String _host;
  uint16_t _port;
  String _path;
  std::vector<uint8_t> _rxBuffer;
  size_t _rxIndex = 0;

public:
  WebsocketClientStream(websockets::WebsocketsClient& ws, const char* host, uint16_t port, const char* path = "/mqtt")
    : _ws(&ws), _host(host), _port(port), _path(path) {
    _ws->setInsecure();
    _ws->addHeader("Sec-WebSocket-Protocol", "mqtt");
    _ws->onMessage([this](websockets::WebsocketsClient&, websockets::WebsocketsMessage msg) {
      const char* ptr = msg.c_str();
      uint32_t len = msg.length();
      if (ptr && len > 0) {
        _rxBuffer.insert(_rxBuffer.end(), (const uint8_t*)ptr, (const uint8_t*)ptr + len);
      }
    });
  }

  int connect(IPAddress ip, uint16_t port) override {
    return connect(ip.toString().c_str(), port);
  }

  int connect(const char *host, uint16_t port) override {
    _rxBuffer.clear();
    _rxIndex = 0;
    String url = "wss://" + _host + ":" + String(_port) + _path;
    return _ws->connect(url) ? 1 : 0;
  }

  size_t write(uint8_t b) override {
    return write(&b, 1);
  }

  size_t write(const uint8_t *buf, size_t size) override {
    if (!_ws->available()) return 0;
    bool ok = _ws->sendBinary((const char*)buf, size);
    return ok ? size : 0;
  }

  int available() override {
    if (_ws->available()) {
      _ws->poll();
    }
    int avail = (int)(_rxBuffer.size() - _rxIndex);
    return avail > 0 ? avail : 0;
  }

  int read() override {
    if (!available()) return -1;
    uint8_t b = _rxBuffer[_rxIndex++];
    if (_rxIndex >= _rxBuffer.size()) {
      _rxBuffer.clear();
      _rxIndex = 0;
    }
    return b;
  }

  int read(uint8_t *buf, size_t size) override {
    int avail = available();
    if (avail <= 0) return -1;
    size_t toRead = (size < (size_t)avail) ? size : (size_t)avail;
    memcpy(buf, _rxBuffer.data() + _rxIndex, toRead);
    _rxIndex += toRead;
    if (_rxIndex >= _rxBuffer.size()) {
      _rxBuffer.clear();
      _rxIndex = 0;
    } else if (_rxIndex > 2048) {
      _rxBuffer.erase(_rxBuffer.begin(), _rxBuffer.begin() + _rxIndex);
      _rxIndex = 0;
    }
    return toRead;
  }

  int peek() override {
    if (!available()) return -1;
    return _rxBuffer[_rxIndex];
  }

  void flush() override {
    if (_ws->available()) {
      _ws->poll();
    }
  }

  void stop() override {
    _ws->close();
    _rxBuffer.clear();
    _rxIndex = 0;
  }

  uint8_t connected() override {
    return _ws->available() ? 1 : 0;
  }

  operator bool() override {
    return _ws->available();
  }
};

websockets::WebsocketsClient wsClient;
WebsocketClientStream wsStream(wsClient, wss_host, wss_port, wss_path);
PubSubClient mqttClient(wsStream);

// OLED SH1106 I2C (128x64) - MÀN HÌNH PHÒNG KHÁCH
U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, /* reset=*/U8X8_PIN_NONE);
String customDisplayText = "";
unsigned long customTextTime = 0;
unsigned long lastMqttRetry = 0;

// --- PIN DEFINITIONS ESP32 #1 ---
#define DHTPIN 14 // Cảm biến DHT11 -> Chân D14
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

#define MQ2_PIN 34 // Cảm biến khí Gas -> Chân D34 (Analog AO)
#define PIR_PIN 35 // Cảm biến chuyển động PIR -> Chân D35
#define LDR_PIN 33 // Cảm biến bóng đêm LDR -> Chân D33 (Analog/Digital)
#define BUZZER_PIN 12 // Còi báo động Gas -> Chân D12
#define SERVO_PIN 13  // Servo cửa sổ -> Chân D13

#define LIGHT_BEDROOM 15 // Đèn Phòng Ngủ -> Chân D15
#define LIGHT_KITCHEN 2  // Đèn Bếp -> Chân D2 (LED Onboard)
#define LIGHT_LIVING 4   // Đèn Phòng Khách -> Chân D4

#define FAN_BEDROOM 16 // Quạt Phòng Ngủ -> Chân D16
#define FAN_KITCHEN 17 // Quạt Phòng Bếp -> Chân D17
#define FAN_LIVING 5   // Quạt Phòng Khách -> Chân D5

#define BTN_LIGHT_BEDROOM 18 // Nút cơ Đèn Ngủ -> Chân D18
#define BTN_LIGHT_KITCHEN 19 // Nút cơ Đèn Bếp -> Chân D19
#define BTN_LIGHT_LIVING 27  // Nút cơ Đèn Khách -> Chân D27
#define BTN_FAN_BEDROOM 32   // Nút cơ Quạt Ngủ -> Chân D32
#define BTN_FAN_KITCHEN 23   // Nút cơ Quạt Bếp -> Chân D23
#define BTN_FAN_LIVING 25    // Nút cơ Quạt Khách -> Chân D25
#define BTN_WINDOW 26        // Nút cơ Cửa Sổ -> Chân D26

// MACRO ĐIỀU KHIỂN RELAY / LED (Mức HIGH = BẬT, Mức LOW = TẮT Chuẩn 100% Code Gốc)
#define RELAY_ON HIGH
#define RELAY_OFF LOW

// --- STATE VARIABLES ---
bool manualLight[3] = {false, false, false}; // Ngủ, Bếp, Khách
bool manualFan[3] = {false, false, false};   // Ngủ, Bếp, Khách
bool windowOpen = false;
Servo windowServo;

unsigned long startTime = 0;
unsigned long lastMotionTime = 0;
unsigned long lastLogTime = 0;
unsigned long lastTelemetryTime = 0;
unsigned long lastSensorReadTime = 0;
unsigned long lastDisplayTime = 0;
float currentTemp = 27.0;
float currentHum = 65.0;
int currentMQ2 = 400;
const unsigned long MOTION_LIGHT_TIMEOUT = 5000;
const unsigned long TELEMETRY_INTERVAL = 3000;

int readMQ2Smooth() {
  long sum = 0;
  for (int i = 0; i < 20; i++) {
    sum += analogRead(MQ2_PIN);
    delayMicroseconds(200);
  }
  return (int)(sum / 20);
}

void initPins() {
  pinMode(PIR_PIN, INPUT);
  pinMode(LDR_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  pinMode(LIGHT_BEDROOM, OUTPUT);
  pinMode(LIGHT_KITCHEN, OUTPUT);
  pinMode(LIGHT_LIVING, OUTPUT);

  digitalWrite(LIGHT_BEDROOM, RELAY_OFF);
  digitalWrite(LIGHT_KITCHEN, RELAY_OFF);
  digitalWrite(LIGHT_LIVING, RELAY_OFF);

  pinMode(FAN_BEDROOM, OUTPUT);
  pinMode(FAN_KITCHEN, OUTPUT);
  pinMode(FAN_LIVING, OUTPUT);
  digitalWrite(FAN_BEDROOM, RELAY_OFF);
  digitalWrite(FAN_KITCHEN, RELAY_OFF);
  digitalWrite(FAN_LIVING, RELAY_OFF);

  pinMode(BTN_LIGHT_BEDROOM, INPUT_PULLUP);
  pinMode(BTN_LIGHT_KITCHEN, INPUT_PULLUP);
  pinMode(BTN_LIGHT_LIVING, INPUT_PULLUP);
  pinMode(BTN_FAN_BEDROOM, INPUT_PULLUP);
  pinMode(BTN_FAN_KITCHEN, INPUT_PULLUP);
  pinMode(BTN_FAN_LIVING, INPUT_PULLUP);
  pinMode(BTN_WINDOW, INPUT_PULLUP);

  windowServo.attach(SERVO_PIN);
  windowServo.write(0);
}

void publishState(const char *deviceId, bool powerVal, const char *commandId = nullptr) {
  String topic = "homing/devices/" + String(deviceId) + "/state";
  StaticJsonDocument<256> doc;
  doc["device_id"] = deviceId;
  JsonObject stateObj = doc.createNestedObject("state");
  stateObj["power"] = powerVal;
  if (commandId && strlen(commandId) > 0) {
    doc["command_id"] = commandId;
  }

  char buffer[256];
  serializeJson(doc, buffer);
  mqttClient.publish(topic.c_str(), buffer, true);
  Serial.printf("[WSS-MQTT Out] %s -> %s\n", topic.c_str(), buffer);
}

void publishWindowPosition(const char *deviceId, int position, const char *commandId = nullptr) {
  String topic = "homing/devices/" + String(deviceId) + "/state";
  StaticJsonDocument<256> doc;
  doc["device_id"] = deviceId;
  JsonObject stateObj = doc.createNestedObject("state");
  stateObj["position"] = position;
  if (commandId && strlen(commandId) > 0) {
    doc["command_id"] = commandId;
  }

  char buffer[256];
  serializeJson(doc, buffer);
  mqttClient.publish(topic.c_str(), buffer, true);
  Serial.printf("[WSS-MQTT Out] %s -> %s\n", topic.c_str(), buffer);
}

unsigned long lastNodeHeartbeat = 0;

void publishNodeHeartbeat() {
  if (!mqttClient.connected()) return;
  StaticJsonDocument<128> doc;
  doc["device_id"] = "esp32_home_appliances";
  doc["node_id"] = "esp32_home_appliances";
  doc["status"] = "ok";
  char buffer[128];
  serializeJson(doc, buffer);
  mqttClient.publish("homing/devices/esp32_home_appliances/ack", buffer);
  Serial.printf("[WSS-MQTT Node Heartbeat] homing/devices/esp32_home_appliances/ack -> %s\n", buffer);
}

void syncDeviceStates() {
  if (!mqttClient.connected()) return;
  publishState("living-light", manualLight[2]);
  delay(10);
  publishState("bedroom-light", manualLight[0]);
  delay(10);
  publishState("kitchen-light", manualLight[1]);
  delay(10);
  publishState("living-fan", manualFan[2]);
  delay(10);
  publishState("bedroom-fan", manualFan[0]);
  delay(10);
  publishState("kitchen-fan", manualFan[1]);
  delay(10);
  publishWindowPosition("living-blind", windowOpen ? 90 : 0);
}

void publishAck(const char *deviceId, const char *commandId,
                const char *status) {
  String topic = "homing/devices/" + String(deviceId) + "/ack";
  StaticJsonDocument<200> doc;
  doc["command_id"] = commandId;
  doc["status"] = status;
  doc["device_id"] = deviceId;
  char buffer[256];
  serializeJson(doc, buffer);
  mqttClient.publish(topic.c_str(), buffer);
  Serial.printf("[WSS-MQTT Ack] %s -> %s\n", topic.c_str(), buffer);
}

void publishDiscovery(const char *deviceId, const char *name, const char *kind, const char *room) {
  StaticJsonDocument<256> doc;
  doc["device_id"] = deviceId;
  doc["name"] = name;
  doc["kind"] = kind;
  doc["room"] = room;
  char buffer[256];
  serializeJson(doc, buffer);
  mqttClient.publish("homing/discovery", buffer);
  Serial.printf("[WSS-MQTT Discovery] homing/discovery -> %s\n", buffer);
}

bool scanRequested = false;

void handleScanResponse() {
  if (!scanRequested) return;
  scanRequested = false;

  Serial.println("[WSS-MQTT Broadcast] Đang phản hồi danh sách thiết bị (an toàn Wi-Fi)...");

  publishDiscovery("living-light", "Đèn phòng khách", "light", "Phòng khách");
  delay(15);
  publishDiscovery("bedroom-light", "Đèn phòng ngủ", "light", "Phòng ngủ");
  delay(15);
  publishDiscovery("kitchen-light", "Đèn phòng bếp", "light", "Phòng bếp");
  delay(15);
  publishDiscovery("living-fan", "Quạt phòng khách", "fan", "Phòng khách");
  delay(15);
  publishDiscovery("bedroom-fan", "Quạt phòng ngủ", "fan", "Phòng ngủ");
  delay(15);
  publishDiscovery("kitchen-fan", "Quạt phòng bếp", "fan", "Phòng bếp");
  delay(15);
  publishDiscovery("living-blind", "Cửa sổ thông gió", "blind", "Phòng khách");
  delay(15);
  publishDiscovery("living-temperature", "Cảm biến nhiệt ẩm", "sensor", "Phòng khách");
  delay(15);
  publishDiscovery("kitchen-gas", "Cảm biến khí Gas", "sensor", "Phòng bếp");
  delay(15);
  publishDiscovery("living-motion", "Cảm biến chuyển động", "sensor", "Phòng khách");
  delay(15);
  publishDiscovery("living-light-sensor", "Cảm biến ánh sáng", "sensor", "Phòng khách");
  delay(15);
  publishDiscovery("living-display", "Màn hình hiển thị", "display", "Phòng khách");
  delay(20);

  publishState("living-light", manualLight[2]);
  delay(15);
  publishState("bedroom-light", manualLight[0]);
  delay(15);
  publishState("kitchen-light", manualLight[1]);
  delay(15);
  publishState("living-fan", manualFan[2]);
  delay(15);
  publishState("bedroom-fan", manualFan[0]);
  delay(15);
  publishState("kitchen-fan", manualFan[1]);
  delay(15);
  publishWindowPosition("living-blind", windowOpen ? 90 : 0);

  Serial.println("[WSS-MQTT Broadcast] Hoàn tất phản hồi quét thiết bị!");
}

void mqttCallback(char *topic, byte *payload, unsigned int length) {
  Serial.printf("[WSS-MQTT In] Topic: %s\n", topic);

  if (String(topic) == "homing/broadcast/scan") {
    Serial.println("[WSS-MQTT Broadcast] Nhận lệnh quét thiết bị! Đã lên lịch phản hồi...");
    scanRequested = true;
    return;
  }

  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, payload, length);
  if (error) {
    Serial.print("[WSS-MQTT Error] Lỗi parse JSON: ");
    Serial.println(error.c_str());
    return;
  }

  String topicStr = String(topic);
  int firstSlash = topicStr.indexOf('/', 7);
  int secondSlash = topicStr.lastIndexOf("/command");
  if (firstSlash == -1 || secondSlash == -1)
    return;

  String deviceId = topicStr.substring(firstSlash + 1, secondSlash);
  const char *commandId = doc["command_id"] | "cmd-unknown";
  const char *action = doc["action"] | "";

  Serial.printf("[WSS-MQTT Command] Device: %s | Action: %s | CmdID: %s\n",
                deviceId.c_str(), action, commandId);

  bool powerState = false;
  if (String(action) == "on")
    powerState = true;
  else if (String(action) == "off")
    powerState = false;
  else if (String(action) == "toggle")
    powerState = true;

  if (deviceId == "living-light") {
    if (String(action) == "toggle")
      manualLight[2] = !manualLight[2];
    else
      manualLight[2] = powerState;
    digitalWrite(LIGHT_LIVING, manualLight[2] ? RELAY_ON : RELAY_OFF);
    publishAck("living-light", commandId, "executed");
    publishState("living-light", manualLight[2], commandId);
  } else if (deviceId == "bedroom-light") {
    if (String(action) == "toggle")
      manualLight[0] = !manualLight[0];
    else
      manualLight[0] = powerState;
    digitalWrite(LIGHT_BEDROOM, manualLight[0] ? RELAY_ON : RELAY_OFF);
    publishAck("bedroom-light", commandId, "executed");
    publishState("bedroom-light", manualLight[0], commandId);
  } else if (deviceId == "kitchen-light") {
    if (String(action) == "toggle")
      manualLight[1] = !manualLight[1];
    else
      manualLight[1] = powerState;
    digitalWrite(LIGHT_KITCHEN, manualLight[1] ? RELAY_ON : RELAY_OFF);
    publishAck("kitchen-light", commandId, "executed");
    publishState("kitchen-light", manualLight[1], commandId);
  } else if (deviceId == "living-fan" || deviceId == "living-aircon") {
    if (String(action) == "toggle")
      manualFan[2] = !manualFan[2];
    else
      manualFan[2] = powerState;
    digitalWrite(FAN_LIVING, manualFan[2] ? RELAY_ON : RELAY_OFF);
    publishAck(deviceId.c_str(), commandId, "executed");
    publishState(deviceId.c_str(), manualFan[2], commandId);
  } else if (deviceId == "bedroom-fan") {
    if (String(action) == "toggle")
      manualFan[0] = !manualFan[0];
    else
      manualFan[0] = powerState;
    digitalWrite(FAN_BEDROOM, manualFan[0] ? RELAY_ON : RELAY_OFF);
    publishAck("bedroom-fan", commandId, "executed");
    publishState("bedroom-fan", manualFan[0], commandId);
  } else if (deviceId == "kitchen-fan") {
    if (String(action) == "toggle")
      manualFan[1] = !manualFan[1];
    else
      manualFan[1] = powerState;
    digitalWrite(FAN_KITCHEN, manualFan[1] ? RELAY_ON : RELAY_OFF);
    publishAck("kitchen-fan", commandId, "executed");
    publishState("kitchen-fan", manualFan[1], commandId);
  } else if (deviceId == "window-servo" || deviceId == "living-blind") {
    int pos = 0;
    if (String(action) == "set") {
      pos = doc["value"]["position"] | 0;
      windowOpen = (pos > 0);
      windowServo.write(pos > 90 ? 90 : pos);
    } else if (String(action) == "open") {
      windowOpen = true;
      pos = 90;
      windowServo.write(pos);
    } else if (String(action) == "close") {
      windowOpen = false;
      pos = 0;
      windowServo.write(pos);
    } else if (String(action) == "toggle") {
      windowOpen = !windowOpen;
      pos = windowOpen ? 90 : 0;
      windowServo.write(pos);
    } else {
      windowOpen = powerState;
      pos = windowOpen ? 90 : 0;
      windowServo.write(pos);
    }
    publishAck(deviceId.c_str(), commandId, "executed");
    publishWindowPosition(deviceId.c_str(), pos, commandId);
  } else if (deviceId == "living-display") {
    if (doc["value"].is<JsonObject>() &&
        doc["value"]["text"].is<const char *>()) {
      customDisplayText = String((const char *)doc["value"]["text"]);
    } else if (doc["value"].is<JsonObject>() &&
               doc["value"]["message"].is<const char *>()) {
      customDisplayText = String((const char *)doc["value"]["message"]);
    } else if (doc["value"].is<const char *>()) {
      customDisplayText = String((const char *)doc["value"]);
    } else {
      customDisplayText = "Homing Hub Ready";
    }
    customTextTime = millis();

    publishAck("living-display", commandId, "executed");

    StaticJsonDocument<256> displayDoc;
    displayDoc["device_id"] = "living-display";
    if (commandId && strlen(commandId) > 0) {
      displayDoc["command_id"] = commandId;
    }
    JsonObject stateObj = displayDoc.createNestedObject("state");
    stateObj["power"] = true;
    stateObj["message"] = customDisplayText;
    char buffer[256];
    serializeJson(displayDoc, buffer);
    mqttClient.publish("homing/devices/living-display/state", buffer, true);
  }
}

unsigned long lastWifiRetry = 0;

void reconnectWiFi() {
  if (WiFi.status() != WL_CONNECTED && (millis() - lastWifiRetry > 4000)) {
    lastWifiRetry = millis();
    Serial.println("[WiFi] Mất kết nối WiFi! Đang thử kết nối lại...");
    WiFi.disconnect();
    WiFi.reconnect();
  }
}

// XỬ LÝ KẾT NỐI CLOUD WSS-MQTT NON-BLOCKING (KHÔNG BỊ LẶP CHỜ VÔ TẬN)
void reconnectMQTT() {
  if (WiFi.status() != WL_CONNECTED)
    return;
  if (mqttClient.connected())
    return;

  if (millis() - lastMqttRetry > 3000) {
    lastMqttRetry = millis();
    Serial.print("[WSS-MQTT Client] Đang thử kết nối Cloud Mosquitto Broker: wss://");
    Serial.print(wss_host);
    Serial.print(":");
    Serial.print(wss_port);
    Serial.println(wss_path);
    
    const char* clientId = "ESP32_Home_Appliances";
    const char* willTopic = "homing/nodes/esp32_home_appliances/lwt";
    const char* willPayload = "{\"node_id\":\"esp32_home_appliances\",\"online\":false,\"status\":\"offline\"}";
    if (mqttClient.connect(clientId, willTopic, 1, true, willPayload)) {
      Serial.println("[WSS-MQTT Client] KẾT NỐI CLOUD WSS THÀNH CÔNG (ĐÃ ĐĂNG KÝ LWT)!");
      mqttClient.subscribe("homing/devices/+/command");
      mqttClient.subscribe("homing/broadcast/scan");
      Serial.println("[WSS-MQTT Client] Subscribed: homing/devices/+/command, homing/broadcast/scan");
      publishState("living-light", manualLight[2]);
      publishState("bedroom-light", manualLight[0]);
      publishState("kitchen-light", manualLight[1]);
      publishState("living-fan", manualFan[2]);
      publishState("bedroom-fan", manualFan[0]);
      publishState("kitchen-fan", manualFan[1]);
      publishWindowPosition("living-blind", windowOpen ? 90 : 0);
    } else {
      Serial.printf("[WSS-MQTT Error] Thất bại, rc=%d. Thử lại sau 3s...\n",
                    mqttClient.state());
    }
  }
}

void controlManualButtons() {
  if (digitalRead(BTN_LIGHT_BEDROOM) == LOW) {
    manualLight[0] = !manualLight[0];
    digitalWrite(LIGHT_BEDROOM, manualLight[0] ? RELAY_ON : RELAY_OFF);
    Serial.println("[Nút Bấm] Đèn Phòng Ngủ: " +
                   String(manualLight[0] ? "BẬT" : "TẮT"));
    publishState("bedroom-light", manualLight[0]);
    delay(200);
  }
  if (digitalRead(BTN_LIGHT_KITCHEN) == LOW) {
    manualLight[1] = !manualLight[1];
    digitalWrite(LIGHT_KITCHEN, manualLight[1] ? RELAY_ON : RELAY_OFF);
    Serial.println("[Nút Bấm] Đèn Phòng Bếp: " +
                   String(manualLight[1] ? "BẬT" : "TẮT"));
    publishState("kitchen-light", manualLight[1]);
    delay(200);
  }
  if (digitalRead(BTN_LIGHT_LIVING) == LOW) {
    manualLight[2] = !manualLight[2];
    digitalWrite(LIGHT_LIVING, manualLight[2] ? RELAY_ON : RELAY_OFF);
    Serial.println("[Nút Bấm] Đèn Phòng Khách: " +
                   String(manualLight[2] ? "BẬT" : "TẮT"));
    publishState("living-light", manualLight[2]);
    delay(200);
  }
  if (digitalRead(BTN_FAN_BEDROOM) == LOW) {
    manualFan[0] = !manualFan[0];
    digitalWrite(FAN_BEDROOM, manualFan[0] ? RELAY_ON : RELAY_OFF);
    Serial.println("[Nút Bấm] Quạt Phòng Ngủ: " +
                   String(manualFan[0] ? "BẬT" : "TẮT"));
    publishState("bedroom-fan", manualFan[0]);
    delay(200);
  }
  if (digitalRead(BTN_FAN_KITCHEN) == LOW) {
    manualFan[1] = !manualFan[1];
    digitalWrite(FAN_KITCHEN, manualFan[1] ? RELAY_ON : RELAY_OFF);
    Serial.println("[Nút Bấm] Quạt Phòng Bếp: " +
                   String(manualFan[1] ? "BẬT" : "TẮT"));
    publishState("kitchen-fan", manualFan[1]);
    delay(200);
  }
  if (digitalRead(BTN_FAN_LIVING) == LOW) {
    manualFan[2] = !manualFan[2];
    digitalWrite(FAN_LIVING, manualFan[2] ? RELAY_ON : RELAY_OFF);
    Serial.println("[Nút Bấm] Quạt Phòng Khách: " +
                   String(manualFan[2] ? "BẬT" : "TẮT"));
    publishState("living-fan", manualFan[2]);
    delay(200);
  }
  if (digitalRead(BTN_WINDOW) == LOW) {
    windowOpen = !windowOpen;
    windowServo.write(windowOpen ? 90 : 0);
    Serial.println("[Nút Bấm] Cửa Sổ Thông Gió: " +
                   String(windowOpen ? "MỞ" : "ĐÓNG"));
    publishWindowPosition("living-blind", windowOpen ? 90 : 0);
    delay(200);
  }
}

void checkMotionAndDarkness() {
  int pirVal = digitalRead(PIR_PIN);
  int ldrAnalog = analogRead(LDR_PIN);

  bool isMotion = (pirVal == LOW);
  bool isDark = (ldrAnalog < 60);

  if (millis() - lastLogTime > 1500) {
    lastLogTime = millis();
    Serial.printf("[DIAGNOSTIC] PIR (D35): Raw=%d (%s) | LDR (D33): Ana=%d "
                  "(%s) -> TRẠNG THÁI ĐÈN: %s\n",
                  pirVal, isMotion ? "CÓ CHUYỂN ĐỘNG" : "KHÔNG CHUYỂN ĐỘNG",
                  ldrAnalog, isDark ? "ĐÃ TỐI" : "TRỜI SÁNG",
                  (isDark && isMotion) ? "BẬT (SÁNG)" : "TẮT");
  }

  if (isDark && isMotion) {
    lastMotionTime = millis();
    digitalWrite(LIGHT_BEDROOM, RELAY_ON);
    digitalWrite(LIGHT_KITCHEN, RELAY_ON);
    digitalWrite(LIGHT_LIVING, RELAY_ON);
  } else {
    if (millis() - lastMotionTime > MOTION_LIGHT_TIMEOUT) {
      if (!manualLight[0])
        digitalWrite(LIGHT_BEDROOM, RELAY_OFF);
      if (!manualLight[1])
        digitalWrite(LIGHT_KITCHEN, RELAY_OFF);
      if (!manualLight[2])
        digitalWrite(LIGHT_LIVING, RELAY_OFF);
    }
  }
}

void checkGasAlert(int mq2_value) {
  if (millis() - startTime < 15000)
    return;

  if (mq2_value > 1200) {
    digitalWrite(BUZZER_PIN, HIGH);
    digitalWrite(FAN_KITCHEN, RELAY_ON);
    windowServo.write(90);
    Serial.println("[CẢNH BÁO KHẨN CẤP] Khí Gas vượt ngưỡng an toàn!");
    u8g2.setCursor(0, 58);
    u8g2.print("! GAS WARNING !");
  } else {
    digitalWrite(BUZZER_PIN, LOW);
  }
}

void sendTelemetry() {
  if (millis() - lastTelemetryTime >= TELEMETRY_INTERVAL) {
    lastTelemetryTime = millis();

    int pirVal = digitalRead(PIR_PIN);
    int ldrAnalog = analogRead(LDR_PIN);
    bool isMotion = (pirVal == LOW);
    bool isDark = (ldrAnalog < 60);

    StaticJsonDocument<256> tempDoc;
    tempDoc["device_id"] = "living-temperature";
    JsonObject stateObj = tempDoc.createNestedObject("state");
    stateObj["temperature"] = currentTemp;
    stateObj["humidity"] = currentHum;
    char tempBuf[256];
    serializeJson(tempDoc, tempBuf);
    mqttClient.publish("homing/devices/living-temperature/state", tempBuf,
                       true);

    StaticJsonDocument<256> gasDoc;
    gasDoc["device_id"] = "kitchen-gas";
    JsonObject gasStateObj = gasDoc.createNestedObject("state");
    gasStateObj["gas_level"] = currentMQ2;
    gasStateObj["alert"] = (currentMQ2 > 1200);
    char gasBuf[256];
    serializeJson(gasDoc, gasBuf);
    mqttClient.publish("homing/devices/kitchen-gas/state", gasBuf, true);

    StaticJsonDocument<256> motionDoc;
    motionDoc["device_id"] = "living-motion";
    JsonObject motionStateObj = motionDoc.createNestedObject("state");
    motionStateObj["motion"] = isMotion;
    char motionBuf[256];
    serializeJson(motionDoc, motionBuf);
    mqttClient.publish("homing/devices/living-motion/state", motionBuf, true);

    StaticJsonDocument<256> ldrDoc;
    ldrDoc["device_id"] = "living-light-sensor";
    JsonObject ldrStateObj = ldrDoc.createNestedObject("state");
    ldrStateObj["light_level"] = ldrAnalog;
    ldrStateObj["is_dark"] = isDark;
    char ldrBuf[256];
    serializeJson(ldrDoc, ldrBuf);
    mqttClient.publish("homing/devices/living-light-sensor/state", ldrBuf,
                       true);

    StaticJsonDocument<256> displayDoc;
    displayDoc["device_id"] = "living-display";
    JsonObject displayStateObj = displayDoc.createNestedObject("state");
    displayStateObj["power"] = true;
    displayStateObj["message"] = customDisplayText.length() > 0
                                     ? customDisplayText
                                     : "Homing Hub Display";
    char displayBuf[256];
    serializeJson(displayDoc, displayBuf);
    mqttClient.publish("homing/devices/living-display/state", displayBuf, true);
  }
}

void setup() {
  Serial.begin(115200);
  startTime = millis();

  // Khởi tạo màn hình OLED ngay lập tức khi cấp nguồn
  u8g2.begin();
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x12_tr);
  u8g2.setCursor(0, 12);
  u8g2.print("Dang ket noi WiFi...");
  u8g2.sendBuffer();

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);
  WiFi.setSleep(false); // Tắt Wi-Fi Power Save để chống rớt gói tin và chống chập chờn kết nối
  WiFi.begin(ssid, pass);
  Serial.print("Đang kết nối WiFi: ");
  Serial.println(ssid);
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 10) {
    delay(300);
    Serial.print(".");
    retry++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Connected! IP Address: ");
    Serial.println(WiFi.localIP());
  }

  // Cấu hình MQTT Client
  mqttClient.setServer(wss_host, wss_port);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(512);
  mqttClient.setKeepAlive(15);

  dht.begin();
  initPins();
  Serial.println("ESP32 #1 (Home Appliances System - Cloud WSS MQTT) SẴN SÀNG!");
}

void loop() {
  reconnectWiFi();
  reconnectMQTT();
  if (mqttClient.connected()) {
    mqttClient.loop();
  }

  handleScanResponse();

  // Gửi heartbeat và đồng bộ trạng thái đèn, quạt định kỳ 3s (< 5s) cho toàn bộ node phần cứng
  if (millis() - lastNodeHeartbeat >= 3000) {
    lastNodeHeartbeat = millis();
    publishNodeHeartbeat();
    syncDeviceStates();
  }

  // Đọc cảm biến định kỳ mỗi 2 giây
  if (millis() - lastSensorReadTime >= 2000) {
    lastSensorReadTime = millis();
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t)) currentTemp = t;
    if (!isnan(h)) currentHum = h;
    currentMQ2 = readMQ2Smooth();

    if (currentTemp > 35) {
      digitalWrite(FAN_LIVING, RELAY_ON);
      Serial.println("[Cảnh báo] Nhiệt độ cao (>35C)! Bật quạt phòng khách.");
    }
  }

  // Cập nhật màn hình OLED định kỳ mỗi 500ms
  if (millis() - lastDisplayTime >= 500) {
    lastDisplayTime = millis();
    u8g2.clearBuffer();
    u8g2.setFont(u8g2_font_6x12_tr);

    if (customDisplayText.length() > 0 && millis() - customTextTime < 10000) {
      u8g2.setCursor(0, 12);
      u8g2.print("HOMING HUB AI:");
      u8g2.setCursor(0, 32);
      u8g2.print(customDisplayText.substring(0, 20));
    } else {
      u8g2.setCursor(0, 12);
      u8g2.print("Nhiet do: ");
      u8g2.print(currentTemp);
      u8g2.print(" C");
      u8g2.setCursor(0, 28);
      u8g2.print("Do am: ");
      u8g2.print(currentHum);
      u8g2.print(" %");
      u8g2.setCursor(0, 44);
      u8g2.print("MQ2: ");
      u8g2.print(currentMQ2);
    }
    u8g2.sendBuffer();
  }

  controlManualButtons();
  checkMotionAndDarkness();
  checkGasAlert(currentMQ2);
  sendTelemetry();
}

/*
 * ============================================================================
 * DỰ ÁN SMART HOME - ESP32 #2: CỔNG CHÍNH & KHÓA CỬA AN NINH THÔNG MINH
 * (KẾT NỐI TỪ XA CLOUD MQTT OVER WSS - wss://mqtt.blask.id.vn:443/mqtt)
 * ============================================================================
 */

#include <ArduinoJson.h>
#include <ArduinoWebsockets.h>
#include <ESP32Servo.h>
#include <Keypad.h>
#include <LiquidCrystal_I2C.h>
#include <MFRC522.h>
#include <PubSubClient.h>
#include <SPI.h>
#include <WiFi.h>
#include <Wire.h>
#include <vector>

// --- THÔNG TIN MẠNG WIFI & MQTT BROKER TRONG MẠNG LAN ---
// Cấu hình mạng WiFi gia đình
char ssid[] = "TP-Link_ED49";            // Tên WiFi
char pass[] = "76664748";                // Mật khẩu WiFi

// Địa chỉ IP LAN của máy tính/server chạy Docker (Mosquitto Port 1883)
// Tra cứu IP: Chạy 'ipconfig' trên Windows hoặc 'hostname -I' trên Linux
const char* mqtt_server = "192.168.1.16"; 
const int mqtt_port = 1883;

// Client kết nối TCP thuần trong mạng WiFi LAN (phản hồi tức thì < 10ms, tiết kiệm RAM)
WiFiClient espClient;
PubSubClient mqttClient(espClient);


// --- KHAI BÁO CHÂN PHẦN CỨNG ---
#define DOOR_SERVO_PIN 4 // Servo mở chốt cửa -> Chân D4
#define BUZZER_PIN 15    // Còi bíp -> Chân D15

#define SS_PIN 5    // RFID SDA -> Chân D5
#define RST_PIN 2   // RFID RST -> Chân D2
#define SCK_PIN 18  // RFID SCK -> Chân D18
#define MISO_PIN 19 // RFID MISO -> Chân D19
#define MOSI_PIN 23 // RFID MOSI -> Chân D23

MFRC522 rfid(SS_PIN, RST_PIN);
Servo doorServo;

// Màn hình LCD I2C 16x2 (Địa chỉ I2C mặc định 0x27)
LiquidCrystal_I2C lcd(0x27, 16, 2);

// Cấu hình Bàn phím ma trận 4x4
const byte ROWS = 4;
const byte COLS = 4;

char keys[ROWS][COLS] = {{'D', 'C', 'B', 'A'},
                         {'#', '9', '6', '3'},
                         {'0', '8', '5', '2'},
                         {'*', '7', '4', '1'}};

byte rowPins[ROWS] = {13, 12, 14, 27}; // Chân Hàng: D13, D12, D14, D27
byte colPins[COLS] = {26, 25, 33, 32}; // Chân Cột: D26, D25, D33, D32
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

// Mật khẩu mở cửa mặc định
String correctPassword = "1234";
String enteredPassword = "";
int wrongAttempts = 0;
bool isLocked = true;
unsigned long lastMqttRetry = 0;
unsigned long lastWifiRetry = 0;
unsigned long lastHeartbeat = 0;
unsigned long unlockTime = 0;
bool autoLockPending = false;

void soundBuzzerBeep(int count, int durationMs) {
  for (int i = 0; i < count; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(durationMs);
    digitalWrite(BUZZER_PIN, LOW);
    delay(durationMs);
  }
}

void publishLockState(bool lockedState, const char *commandId = nullptr) {
  isLocked = lockedState;
  if (!mqttClient.connected())
    return;
  StaticJsonDocument<256> doc;
  doc["device_id"] = "entry-lock";
  JsonObject stateObj = doc.createNestedObject("state");
  stateObj["locked"] = isLocked;
  if (commandId && strlen(commandId) > 0) {
    doc["command_id"] = commandId;
  }
  char buffer[256];
  serializeJson(doc, buffer);
  mqttClient.publish("homing/devices/entry-lock/state", buffer, true);
  Serial.printf("[WSS-MQTT State] homing/devices/entry-lock/state -> %s\n", buffer);
}

unsigned long lastNodeHeartbeat = 0;

void publishNodeHeartbeat() {
  if (!mqttClient.connected())
    return;
  StaticJsonDocument<128> doc;
  doc["device_id"] = "esp32_main_entrance";
  doc["status"] = "ok";
  char buffer[128];
  serializeJson(doc, buffer);
  mqttClient.publish("homing/devices/esp32_main_entrance/ack", buffer);
  Serial.printf("[WSS-MQTT Node Heartbeat] homing/devices/esp32_main_entrance/ack -> %s\n", buffer);
}

void publishAck(const char *commandId, const char *status) {
  if (!mqttClient.connected())
    return;
  StaticJsonDocument<200> doc;
  doc["command_id"] = commandId;
  doc["status"] = status;
  doc["device_id"] = "entry-lock";
  char buffer[256];
  serializeJson(doc, buffer);
  mqttClient.publish("homing/devices/entry-lock/ack", buffer);
  Serial.printf("[WSS-MQTT Ack] homing/devices/entry-lock/ack -> %s\n", buffer);
}

void publishAccessLog(const char *method, bool success, const char *detail) {
  if (!mqttClient.connected())
    return;
  StaticJsonDocument<256> doc;
  doc["method"] = method;
  doc["success"] = success;
  doc["detail"] = detail;
  doc["device_id"] = "entry-lock";
  char buffer[256];
  serializeJson(doc, buffer);
  mqttClient.publish("homing/security/access_log", buffer);
  Serial.printf("[WSS-MQTT Security] homing/security/access_log -> %s\n", buffer);
}

void lockDoor(const char *commandId = nullptr) {
  doorServo.write(0);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("NHA THONG MINH");
  lcd.setCursor(0, 1);
  lcd.print("QUET THE/NHAP MK");
  enteredPassword = "";
  publishLockState(true, commandId);
  Serial.println("[Hệ Thống] Cửa chính -> ĐÃ KHÓA (0 độ).");
}

void unlockDoor(const char *method = "LOCAL", const char *commandId = nullptr) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("CUA DA MO!");
  lcd.setCursor(0, 1);
  lcd.print("XIN MOI VAO...");
  soundBuzzerBeep(2, 100);

  Serial.println("[Hệ Thống] MỞ CỬA! Xoay Servo 90 độ...");
  doorServo.write(90);
  publishLockState(false, commandId);
  publishAccessLog(method, true, "Door Unlocked");

  autoLockPending = true;
  unlockTime = millis();
}

void checkAutoLock() {
  if (autoLockPending && millis() - unlockTime >= 5000) {
    autoLockPending = false;
    lockDoor();
  }
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

  Serial.println("[WSS-MQTT Broadcast] Phản hồi khai báo khóa cửa & trạng thái (an toàn Wi-Fi)...");
  publishDiscovery("entry-lock", "Khóa cửa chính", "lock", "Lối vào");
  delay(15);
  publishLockState(isLocked);
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

  const char *commandId = doc["command_id"] | "cmd-unknown";
  const char *action = doc["action"] | "";

  Serial.printf("[WSS-MQTT Command Entry-Lock] Action: %s | CmdID: %s\n", action,
                commandId);

  if (String(action) == "unlock") {
    publishAck(commandId, "executed");
    unlockDoor("AGENT_REMOTE", commandId);
  } else if (String(action) == "lock") {
    publishAck(commandId, "executed");
    lockDoor(commandId);
  }
}

void reconnectWiFi() {
  if (WiFi.status() != WL_CONNECTED && millis() - lastWifiRetry > 5000) {
    lastWifiRetry = millis();
    Serial.println("[WiFi] Mất kết nối, đang thử kết nối lại WiFi...");
    WiFi.disconnect();
    WiFi.reconnect();
  }
}

// KẾT NỐI LAN TCP-MQTT KHÔNG CHẶN (NON-BLOCKING) - KHÔNG BAO GIỜ LÀM ĐƠ BÀN PHÍM/RFID
void reconnectMQTT() {
  if (WiFi.status() != WL_CONNECTED)
    return;
  if (mqttClient.connected())
    return;

  if (millis() - lastMqttRetry > 5000) {
    lastMqttRetry = millis();
    Serial.print("[LAN-MQTT Client] Đang thử kết nối Mosquitto Broker LAN: ");
    Serial.print(mqtt_server);
    Serial.print(":");
    Serial.println(mqtt_port);

    const char* clientId = "ESP32_Main_Entrance";
    const char* willTopic = "homing/nodes/esp32_main_entrance/lwt";
    const char* willPayload = "{\"node_id\":\"esp32_main_entrance\",\"device_id\":\"entry-lock\",\"online\":false,\"status\":\"offline\"}";
    if (mqttClient.connect(clientId, willTopic, 1, true, willPayload)) {
      Serial.println("[LAN-MQTT Client] KẾT NỐI BROKER LAN THÀNH CÔNG (ĐÃ ĐĂNG KÝ LWT)!");
      mqttClient.subscribe("homing/devices/entry-lock/command");
      mqttClient.subscribe("homing/broadcast/scan");
      Serial.println(
          "[LAN-MQTT Client] Subscribed: homing/devices/entry-lock/command, homing/broadcast/scan");
      publishLockState(isLocked);
    } else {
      Serial.printf("[LAN-MQTT Error] Thất bại, rc=%d\n", mqttClient.state());
    }
  }
}

void checkRFIDCard() {
  if (!rfid.PICC_IsNewCardPresent())
    return;
  if (!rfid.PICC_ReadCardSerial())
    return;

  soundBuzzerBeep(1, 100);
  Serial.print("[RFID Debug] Phát hiện quẹt thẻ! UID: ");
  String cardUID = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    String hexByte = String(rfid.uid.uidByte[i], HEX);
    if (hexByte.length() < 2)
      hexByte = "0" + hexByte;
    cardUID += hexByte + " ";
  }
  cardUID.toUpperCase();
  cardUID.trim();
  Serial.println(cardUID);

  unlockDoor("RFID_CARD");

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}

void checkKeypadInput() {
  char key = keypad.getKey();
  if (key) {
    soundBuzzerBeep(1, 50);
    Serial.println("[Keypad Realtime] Nhấn phím: '" + String(key) + "'");

    if (key == '#') {
      Serial.println("[Keypad] Xác nhận MK: '" + enteredPassword +
                     "' | MK Đúng: '" + correctPassword + "'");
      if (enteredPassword == correctPassword) {
        wrongAttempts = 0;
        unlockDoor("KEYPAD_PASSWORD");
      } else {
        wrongAttempts++;
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("SAI MK: " + enteredPassword);
        lcd.setCursor(0, 1);
        lcd.print("Lan sai: " + String(wrongAttempts));
        soundBuzzerBeep(3, 200);

        publishAccessLog("KEYPAD_PASSWORD", false, "Wrong Password");

        if (wrongAttempts >= 3) {
          publishAccessLog("SECURITY_ALERT", false,
                           "3 Wrong Password Attempts");
        }

        delay(2000);
        lockDoor();
      }
      enteredPassword = "";
    } else if (key == '*') {
      enteredPassword = "";
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("NHAP MAT KHAU:");
    } else {
      enteredPassword += key;
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("NHAP MAT KHAU:");
      lcd.setCursor(0, 1);
      lcd.print(enteredPassword);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(DOOR_SERVO_PIN, OUTPUT);

  doorServo.attach(DOOR_SERVO_PIN);
  doorServo.write(0);

  lcd.init();
  lcd.backlight();

  SPI.begin();
  rfid.PCD_Init();
  delay(10);
  rfid.PCD_SetAntennaGain(MFRC522::RxGain_max);

  Serial.print("[RFID Check] Trạng thái Firmware Chip RC522: ");
  rfid.PCD_DumpVersionToSerial();

  lockDoor();

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);
  WiFi.setSleep(false); // Tắt Wi-Fi Modem Sleep để loại bỏ độ trễ và mất gói tin
  WiFi.begin(ssid, pass);
  Serial.print("Đang kết nối WiFi: ");
  Serial.println(ssid);
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 8) {
    delay(200);
    Serial.print(".");
    retry++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Connected! IP Address: ");
    Serial.println(WiFi.localIP());
  }

  // Cấu hình MQTT Client
  mqttClient.setServer(mqtt_server, mqtt_port);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(512);
  mqttClient.setKeepAlive(15);

  Serial.println(
      "ESP32 #2 (Main Entrance Security System - LAN TCP MQTT) SẴN SÀNG!");
}

void loop() {
  reconnectWiFi();
  reconnectMQTT();
  if (mqttClient.connected()) {
    mqttClient.loop();
    // Gửi tín hiệu Heartbeat định kỳ 3s (< 5s) để Hub không bao giờ báo mất kết nối giả
    if (millis() - lastHeartbeat >= 3000) {
      lastHeartbeat = millis();
      publishLockState(isLocked);
    }
  }

  handleScanResponse();

  // Gửi heartbeat định kỳ 3s (< 5s) cho toàn bộ node phần cứng
  if (millis() - lastNodeHeartbeat >= 3000) {
    lastNodeHeartbeat = millis();
    publishNodeHeartbeat();
  }

  checkAutoLock();
  checkRFIDCard();
  checkKeypadInput();
}

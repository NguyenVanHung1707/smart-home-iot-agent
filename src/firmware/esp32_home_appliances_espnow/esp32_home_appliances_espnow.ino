/*
 * ============================================================================
 * DỰ ÁN SMART HOME (HOMING SERVERLESS)
 * ESP32 #1: THIẾT BỊ TRONG NHÀ & GIÁM SÁT MÔI TRƯỜNG (ESP-NOW SLAVE)
 * ============================================================================
 * Không cần WiFi Internet - Không cần MQTT Broker - Phản hồi tức thì < 2ms!
 * Nhận lệnh từ ESP32 Xiaozhi Gateway qua sóng vô tuyến 2.4GHz ESP-NOW
 * Gửi dữ liệu cảm biến và cảnh báo khẩn cấp ngược lại cho Xiaozhi Gateway
 * ============================================================================
 */

#include <esp_now.h>
#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>
#include <ESP32Servo.h>
#include <U8g2lib.h>

// --- CẤU HÌNH ĐỊA CHỈ MAC CỦA CON XIAOZHI GATEWAY (MASTER) ---
// Địa chỉ MAC thực tế của con ESP32 Xiaozhi Gateway vừa nạp
uint8_t masterGatewayMac[] = {0x94, 0x54, 0xC5, 0xA9, 0x91, 0xE8};

// Kênh WiFi dùng cho ESP-NOW (phải trùng với kênh WiFi của Router nhà bạn: Kênh 2)
#define WIFI_CHANNEL 2

// --- CẤU TRÚC GÓI TIN ESP-NOW CHUẨN ĐỒNG BỘ 3 CON ESP ---
typedef struct struct_message {
  char msg_type[10];  // "CMD", "STATE", "ALERT", "PING"
  char device_id[32]; // "living-light", "kitchen-gas", v.v.
  char action[16];    // "turn_on", "turn_off", "set_value"
  int value;          // 0 hoặc 1 (on/off) hoặc mức quạt (1-3)
  float float_val;    // Giá trị thực: nhiệt độ, gas ppm
} struct_message;

struct_message incomingCmd;
struct_message outgoingData;
esp_now_peer_info_t peerInfo;

// --- KHAI BÁO CHÂN PHẦN CỨNG ---
#define DHTPIN 14        // Cảm biến DHT11
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

#define MQ2_PIN 34       // Cảm biến Gas (Analog)
#define PIR_PIN 35       // Cảm biến Chuyển động PIR
#define LDR_PIN 33       // Cảm biến Ánh sáng LDR
#define BUZZER_PIN 12    // Còi báo động
#define SERVO_PIN 13     // Servo Cửa sổ thông gió

// Đèn 3 phòng
#define LIGHT_BEDROOM 15
#define LIGHT_KITCHEN 2  // LED Onboard
#define LIGHT_LIVING 4

// Quạt 3 phòng
#define FAN_BEDROOM 16
#define FAN_KITCHEN 17
#define FAN_LIVING 5

// Nút bấm cơ
#define BTN_LIGHT_BEDROOM 18

Servo windowServo;
U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE);

// Biến lưu trạng thái thiết bị
bool stateLightLiving = false;
bool stateLightKitchen = false;
bool stateLightBedroom = false;

int stateFanLiving = 0;    // 0: tắt, 1: bật
int stateFanKitchen = 0;
int stateFanBedroom = 0;

int windowAngle = 0;
float currentTemp = 28.0;
float currentHum = 65.0;
int currentGas = 120;
bool currentMotion = false;

unsigned long lastSensorRead = 0;
unsigned long lastDisplayUpdate = 0;
String statusDisplay = "Ready (ESP-NOW)";

// --- HÀM GỬI DỮ LIỆU SANG XIAOZHI GATEWAY ---
void sendStateToGateway(const char* deviceId, const char* action, int val, float fval = 0.0) {
  strcpy(outgoingData.msg_type, "STATE");
  strncpy(outgoingData.device_id, deviceId, sizeof(outgoingData.device_id));
  strncpy(outgoingData.action, action, sizeof(outgoingData.action));
  outgoingData.value = val;
  outgoingData.float_val = fval;

  esp_now_send(masterGatewayMac, (uint8_t *) &outgoingData, sizeof(outgoingData));
  Serial.printf("[ESP-NOW] Gui STATE: %s -> %s (%d)\n", deviceId, action, val);
}

void sendAlertToGateway(const char* deviceId, const char* alertMsg, float val) {
  strcpy(outgoingData.msg_type, "ALERT");
  strncpy(outgoingData.device_id, deviceId, sizeof(outgoingData.device_id));
  strncpy(outgoingData.action, alertMsg, sizeof(outgoingData.action));
  outgoingData.value = 1;
  outgoingData.float_val = val;

  esp_now_send(masterGatewayMac, (uint8_t *) &outgoingData, sizeof(outgoingData));
  Serial.printf("[ESP-NOW CẢNH BÁO] %s: %s (%.1f)\n", deviceId, alertMsg, val);
}

// --- CALLBACK KHI NHẬN ĐƯỢC GÓI TIN ESP-NOW TỪ GATEWAY ---
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
void OnDataRecv(const esp_now_recv_info *recv_info, const uint8_t *incomingDataBytes, int len) {
  const uint8_t *mac = recv_info->src_addr;
#else
void OnDataRecv(const uint8_t * mac, const uint8_t *incomingDataBytes, int len) {
#endif
  memcpy(&incomingCmd, incomingDataBytes, sizeof(incomingCmd));
  
  Serial.printf("\n[ESP-NOW Nhan] Type: %s | Device: %s | Action: %s | Val: %d\n",
                incomingCmd.msg_type, incomingCmd.device_id, incomingCmd.action, incomingCmd.value);

  String dev = String(incomingCmd.device_id);
  String act = String(incomingCmd.action);

  // 1. Xử lý Đèn
  if (dev == "living-light") {
    stateLightLiving = (act == "turn_on" || incomingCmd.value == 1);
    digitalWrite(LIGHT_LIVING, stateLightLiving ? HIGH : LOW);
    statusDisplay = stateLightLiving ? "Living Light: ON" : "Living Light: OFF";
    sendStateToGateway("living-light", stateLightLiving ? "on" : "off", stateLightLiving ? 1 : 0);
  }
  else if (dev == "kitchen-light") {
    stateLightKitchen = (act == "turn_on" || incomingCmd.value == 1);
    digitalWrite(LIGHT_KITCHEN, stateLightKitchen ? HIGH : LOW);
    statusDisplay = stateLightKitchen ? "Kitchen Light: ON" : "Kitchen Light: OFF";
    sendStateToGateway("kitchen-light", stateLightKitchen ? "on" : "off", stateLightKitchen ? 1 : 0);
  }
  else if (dev == "bedroom-light") {
    stateLightBedroom = (act == "turn_on" || incomingCmd.value == 1);
    digitalWrite(LIGHT_BEDROOM, stateLightBedroom ? HIGH : LOW);
    statusDisplay = stateLightBedroom ? "Bedroom Light: ON" : "Bedroom Light: OFF";
    sendStateToGateway("bedroom-light", stateLightBedroom ? "on" : "off", stateLightBedroom ? 1 : 0);
  }
  // 2. Xử lý Quạt
  else if (dev == "living-fan") {
    stateFanLiving = (act == "turn_on" || incomingCmd.value > 0) ? 1 : 0;
    digitalWrite(FAN_LIVING, stateFanLiving ? HIGH : LOW);
    statusDisplay = stateFanLiving ? "Living Fan: ON" : "Living Fan: OFF";
    sendStateToGateway("living-fan", stateFanLiving ? "on" : "off", stateFanLiving);
  }
  else if (dev == "kitchen-fan") {
    stateFanKitchen = (act == "turn_on" || incomingCmd.value > 0) ? 1 : 0;
    digitalWrite(FAN_KITCHEN, stateFanKitchen ? HIGH : LOW);
    statusDisplay = stateFanKitchen ? "Kitchen Fan: ON" : "Kitchen Fan: OFF";
    sendStateToGateway("kitchen-fan", stateFanKitchen ? "on" : "off", stateFanKitchen);
  }
  else if (dev == "bedroom-fan") {
    stateFanBedroom = (act == "turn_on" || incomingCmd.value > 0) ? 1 : 0;
    digitalWrite(FAN_BEDROOM, stateFanBedroom ? HIGH : LOW);
    statusDisplay = stateFanBedroom ? "Bedroom Fan: ON" : "Bedroom Fan: OFF";
    sendStateToGateway("bedroom-fan", stateFanBedroom ? "on" : "off", stateFanBedroom);
  }
  // 3. Xử lý Cửa sổ / Rèm
  else if (dev == "window-servo" || dev == "living-window") {
    windowAngle = (act == "open" || incomingCmd.value == 1) ? 90 : 0;
    windowServo.write(windowAngle);
    statusDisplay = (windowAngle > 0) ? "Window: OPEN" : "Window: CLOSED";
    sendStateToGateway("window-servo", (windowAngle > 0) ? "open" : "closed", windowAngle);
  }
  // 4. Lệnh chung: Tắt hết đèn / Bật hết đèn
  else if (dev == "all-lights") {
    bool turnOn = (act == "turn_on");
    stateLightLiving = stateLightKitchen = stateLightBedroom = turnOn;
    digitalWrite(LIGHT_LIVING, turnOn ? HIGH : LOW);
    digitalWrite(LIGHT_KITCHEN, turnOn ? HIGH : LOW);
    digitalWrite(LIGHT_BEDROOM, turnOn ? HIGH : LOW);
    statusDisplay = turnOn ? "All Lights: ON" : "All Lights: OFF";
    sendStateToGateway("living-light", turnOn ? "on" : "off", turnOn ? 1 : 0);
    sendStateToGateway("kitchen-light", turnOn ? "on" : "off", turnOn ? 1 : 0);
    sendStateToGateway("bedroom-light", turnOn ? "on" : "off", turnOn ? 1 : 0);
  }
}

// Callback xác nhận đã gửi gói tin đi thành công hay thất bại
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
void OnDataSent(const wifi_tx_info_t *tx_info, esp_now_send_status_t status) {
#else
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
#endif
  // Serial.print("[ESP-NOW] Gui goi tin: ");
  // Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Thanh Cong" : "That Bai");
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println("\n==========================================");
  Serial.println("  ESP32 #1: APPLIANCES (ESP-NOW SLAVE)");
  Serial.println("==========================================");

  // Cấu hình chân Output
  pinMode(LIGHT_LIVING, OUTPUT);
  pinMode(LIGHT_KITCHEN, OUTPUT);
  pinMode(LIGHT_BEDROOM, OUTPUT);
  pinMode(FAN_LIVING, OUTPUT);
  pinMode(FAN_KITCHEN, OUTPUT);
  pinMode(FAN_BEDROOM, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  digitalWrite(LIGHT_LIVING, LOW);
  digitalWrite(LIGHT_KITCHEN, LOW);
  digitalWrite(LIGHT_BEDROOM, LOW);
  digitalWrite(FAN_LIVING, LOW);
  digitalWrite(FAN_KITCHEN, LOW);
  digitalWrite(FAN_BEDROOM, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  // Cấu hình chân Input
  pinMode(MQ2_PIN, INPUT);
  pinMode(PIR_PIN, INPUT);
  pinMode(LDR_PIN, INPUT);
  pinMode(BTN_LIGHT_BEDROOM, INPUT_PULLUP);

  // Khởi tạo Servo
  ESP32PWM::allocateTimer(0);
  windowServo.setPeriodHertz(50);
  windowServo.attach(SERVO_PIN, 500, 2400);
  windowServo.write(0);

  // Khởi tạo Cảm biến & OLED
  dht.begin();
  u8g2.begin();

  // Khởi tạo WiFi Station chế độ không kết nối router
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  Serial.print("Dia chi MAC ESP #1: ");
  Serial.println(WiFi.macAddress());

  // Khởi tạo ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Loi khoi tao ESP-NOW!");
    return;
  }
  Serial.println("ESP-NOW Khoi tao thanh cong!");

  esp_now_register_recv_cb(OnDataRecv);
  esp_now_register_send_cb(OnDataSent);

  // Đăng ký Peer (Con Xiaozhi Master Gateway)
  memcpy(peerInfo.peer_addr, masterGatewayMac, 6);
  peerInfo.channel = WIFI_CHANNEL;  
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Loi dang ky Peer Gateway!");
  } else {
    Serial.println("Dang ky Peer Gateway thanh cong!");
  }
}

void loop() {
  unsigned long now = millis();

  // 1. Kiểm tra nút bấm cơ phòng ngủ
  if (digitalRead(BTN_LIGHT_BEDROOM) == LOW) {
    delay(50); // Chống dội phím
    if (digitalRead(BTN_LIGHT_BEDROOM) == LOW) {
      stateLightBedroom = !stateLightBedroom;
      digitalWrite(LIGHT_BEDROOM, stateLightBedroom ? HIGH : LOW);
      statusDisplay = stateLightBedroom ? "Btn: Bed ON" : "Btn: Bed OFF";
      sendStateToGateway("bedroom-light", stateLightBedroom ? "on" : "off", stateLightBedroom ? 1 : 0);
      while(digitalRead(BTN_LIGHT_BEDROOM) == LOW) delay(10);
    }
  }

  // 2. Đọc cảm biến định kỳ mỗi 3 giây
  if (now - lastSensorRead > 3000) {
    lastSensorRead = now;

    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t)) currentTemp = t;
    if (!isnan(h)) currentHum = h;

    currentGas = analogRead(MQ2_PIN);
    int currentLdr = analogRead(LDR_PIN);
    currentMotion = (digitalRead(PIR_PIN) == HIGH);

    // Gửi telemetry: Nhiệt độ, Độ ẩm & Ánh sáng
    sendStateToGateway("living-temperature", "telemetry", 0, currentTemp);
    sendStateToGateway("living-humidity", "telemetry", 0, currentHum);
    sendStateToGateway("living-ldr", "telemetry", 0, (float)currentLdr);

    // Cảnh báo rò rỉ khí Gas nếu nồng độ cao
    if (currentGas > 1500) {
      digitalWrite(BUZZER_PIN, HIGH);
      sendAlertToGateway("kitchen-gas", "GAS_LEAK", (float)currentGas);
      statusDisplay = "ALERT: GAS LEAK!";
    } else {
      digitalWrite(BUZZER_PIN, LOW);
      sendStateToGateway("kitchen-gas", "normal", 0, (float)currentGas);
    }

    // Cảnh báo chuyển động
    if (currentMotion) {
      sendStateToGateway("living-motion", "detected", 1);
    }
  }

  // 3. Cập nhật màn hình OLED mỗi 500ms
  if (now - lastDisplayUpdate > 500) {
    lastDisplayUpdate = now;
    u8g2.clearBuffer();
    u8g2.setFont(u8g2_font_6x10_tr);
    u8g2.drawStr(0, 10, "HOMING ESP-NOW #1");
    u8g2.drawHLine(0, 13, 128);

    char tempStr[24];
    sprintf(tempStr, "T: %.1fC  H: %.0f%%", currentTemp, currentHum);
    u8g2.drawStr(0, 27, tempStr);

    char gasStr[24];
    sprintf(gasStr, "Gas: %d  PIR: %s", currentGas, currentMotion ? "YES" : "NO");
    u8g2.drawStr(0, 40, gasStr);

    u8g2.drawStr(0, 54, statusDisplay.c_str());
    u8g2.sendBuffer();
  }
}

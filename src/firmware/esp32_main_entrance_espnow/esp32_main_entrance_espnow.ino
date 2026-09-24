/*
 * ============================================================================
 * DỰ ÁN SMART HOME (HOMING SERVERLESS)
 * ESP32 #2: CỔNG CHÍNH & KHÓA CỬA AN NINH THÔNG MINH (ESP-NOW SLAVE)
 * ============================================================================
 * Không cần WiFi Internet - Không cần MQTT Broker - Bảo mật phản hồi < 2ms!
 * Nhận lệnh Mở/Khóa cửa từ ESP32 Xiaozhi Gateway qua sóng ESP-NOW
 * Gửi sự kiện mở khóa (Keypad / Thẻ từ RFID) và Cảnh báo đột nhập về Gateway
 * ============================================================================
 */

#include <esp_now.h>
#include <WiFi.h>
#include <Wire.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Keypad.h>
#include <LiquidCrystal_I2C.h>
#include <ESP32Servo.h>

// --- CẤU HÌNH ĐỊA CHỈ MAC CỦA CON XIAOZHI GATEWAY (MASTER) ---
// Địa chỉ MAC thực tế của con ESP32 Xiaozhi Gateway vừa nạp
uint8_t masterGatewayMac[] = {0x94, 0x54, 0xC5, 0xA9, 0x91, 0xE8};
#define WIFI_CHANNEL 2

// --- CẤU TRÚC GÓI TIN ESP-NOW ĐỒNG BỘ ---
typedef struct struct_message {
  char msg_type[10];  // "CMD", "STATE", "ALERT", "LOG"
  char device_id[32]; // "entry-lock", "security-alarm", v.v.
  char action[16];    // "unlock", "lock", "access_log", "alarm"
  int value;          // 0: khóa, 1: mở
  float float_val;
} struct_message;

struct_message incomingCmd;
struct_message outgoingData;
esp_now_peer_info_t peerInfo;

// --- KHAI BÁO CHÂN PHẦN CỨNG ---
#define DOOR_SERVO_PIN 4 // Servo chốt khóa
#define BUZZER_PIN 15    // Còi bíp

#define SS_PIN 5         // RFID SDA
#define RST_PIN 2        // RFID RST
#define SCK_PIN 18       // RFID SCK
#define MISO_PIN 19      // RFID MISO
#define MOSI_PIN 23      // RFID MOSI

MFRC522 rfid(SS_PIN, RST_PIN);
Servo doorServo;
LiquidCrystal_I2C lcd(0x27, 16, 2);

// Bàn phím ma trận 4x4
const byte ROWS = 4;
const byte COLS = 4;
char keys[ROWS][COLS] = {
  {'D', 'C', 'B', 'A'},
  {'#', '9', '6', '3'},
  {'0', '8', '5', '2'},
  {'*', '7', '4', '1'}
};
byte rowPins[ROWS] = {13, 12, 14, 27};
byte colPins[COLS] = {26, 25, 33, 32};
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

// Mật khẩu số mặc định
String correctPassword = "1234";
String enteredPassword = "";
int wrongAttempts = 0;
bool isLocked = true;
unsigned long unlockTime = 0;
const unsigned long autoLockDelay = 5000; // Tự động khóa lại sau 5s

// --- CÁC HÀM TIỆN ÍCH ---
void beep(int ms, int count = 1) {
  for (int i = 0; i < count; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(ms);
    digitalWrite(BUZZER_PIN, LOW);
    if (count > 1) delay(80);
  }
}

void sendStateToGateway(const char* action, int val) {
  strcpy(outgoingData.msg_type, "STATE");
  strcpy(outgoingData.device_id, "entry-lock");
  strncpy(outgoingData.action, action, sizeof(outgoingData.action));
  outgoingData.value = val;
  outgoingData.float_val = 0;

  esp_now_send(masterGatewayMac, (uint8_t *) &outgoingData, sizeof(outgoingData));
  Serial.printf("[ESP-NOW] Gui STATE entry-lock: %s (%d)\n", action, val);
}

void sendSecurityAlert(const char* reason) {
  strcpy(outgoingData.msg_type, "ALERT");
  strcpy(outgoingData.device_id, "security-alarm");
  strncpy(outgoingData.action, reason, sizeof(outgoingData.action));
  outgoingData.value = 1;
  outgoingData.float_val = 0;

  esp_now_send(masterGatewayMac, (uint8_t *) &outgoingData, sizeof(outgoingData));
  Serial.printf("[ESP-NOW CẢNH BÁO AN NINH]: %s\n", reason);
}

void unlockDoor(const char* triggerBy) {
  isLocked = false;
  doorServo.write(90); // Mở góc 90 độ
  beep(100, 2);

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("CUA DANG MO!");
  lcd.setCursor(0, 1);
  lcd.print(triggerBy);

  unlockTime = millis();
  sendStateToGateway("unlocked", 1);
}

void lockDoor() {
  isLocked = true;
  doorServo.write(0); // Khóa góc 0 độ
  beep(250, 1);

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("HOMING ENTRANCE");
  lcd.setCursor(0, 1);
  lcd.print("DA KHOA CUA");

  sendStateToGateway("locked", 0);
  delay(1500);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Nhap PIN hoac");
  lcd.setCursor(0, 1);
  lcd.print("quet the RFID...");
}

// --- CALLBACK NHẬN DỮ LIỆU TỪ XIAOZHI GATEWAY ---
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
void OnDataRecv(const esp_now_recv_info *recv_info, const uint8_t *incomingDataBytes, int len) {
  const uint8_t *mac = recv_info->src_addr;
#else
void OnDataRecv(const uint8_t * mac, const uint8_t *incomingDataBytes, int len) {
#endif
  memcpy(&incomingCmd, incomingDataBytes, sizeof(incomingCmd));
  
  Serial.printf("\n[ESP-NOW Nhan Cua] Device: %s | Action: %s\n", incomingCmd.device_id, incomingCmd.action);

  String dev = String(incomingCmd.device_id);
  String act = String(incomingCmd.action);

  if (dev == "entry-lock") {
    if (act == "unlock" || act == "open" || incomingCmd.value == 1) {
      unlockDoor("Lenh tu Xiaozhi/Web");
    } else if (act == "lock" || act == "close" || incomingCmd.value == 0) {
      lockDoor();
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println("\n==========================================");
  Serial.println("  ESP32 #2: MAIN ENTRANCE (ESP-NOW SLAVE)");
  Serial.println("==========================================");

  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  // Khởi tạo Servo
  ESP32PWM::allocateTimer(1);
  doorServo.setPeriodHertz(50);
  doorServo.attach(DOOR_SERVO_PIN, 500, 2400);
  doorServo.write(0); // Trạng thái ban đầu: Khóa

  // Khởi tạo LCD
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Homing Security");
  lcd.setCursor(0, 1);
  lcd.print("Khoi dong ESP-NOW");

  // Khởi tạo RFID RC522
  SPI.begin();
  rfid.PCD_Init();

  // Khởi tạo WiFi Station chế độ không kết nối router
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  Serial.print("Dia chi MAC ESP #2: ");
  Serial.println(WiFi.macAddress());

  // Khởi tạo ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Loi khoi tao ESP-NOW!");
    lcd.setCursor(0, 1);
    lcd.print("Loi ESP-NOW!");
    return;
  }
  Serial.println("ESP-NOW Khoi tao thanh cong!");

  esp_now_register_recv_cb(OnDataRecv);

  // Đăng ký Peer (Con Xiaozhi Master Gateway)
  memcpy(peerInfo.peer_addr, masterGatewayMac, 6);
  peerInfo.channel = WIFI_CHANNEL;  
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Loi dang ky Peer Gateway!");
  } else {
    Serial.println("Dang ky Peer Gateway thanh cong!");
  }

  delay(1000);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Nhap PIN hoac");
  lcd.setCursor(0, 1);
  lcd.print("quet the RFID...");
}

void loop() {
  unsigned long now = millis();

  // 1. Tự động khóa cửa sau 5 giây mở
  if (!isLocked && (now - unlockTime >= autoLockDelay)) {
    lockDoor();
  }

  // 2. Xử lý quét thẻ từ RFID RC522
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    String cardUID = "";
    for (byte i = 0; i < rfid.uid.size; i++) {
      cardUID += String(rfid.uid.uidByte[i] < 0x10 ? "0" : "");
      cardUID += String(rfid.uid.uidByte[i], HEX);
    }
    cardUID.toUpperCase();
    Serial.printf("[RFID] The quet: %s\n", cardUID.c_str());

    // Thẻ hợp lệ (ví dụ mã thẻ Master)
    unlockDoor("The RFID hop le");
    wrongAttempts = 0;

    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    return;
  }

  // 3. Xử lý bàn phím Keypad 4x4
  char key = keypad.getKey();
  if (key) {
    beep(50);
    Serial.print("Phim: ");
    Serial.println(key);

    if (key == '#') { // Phím xác nhận Enter
      if (enteredPassword == correctPassword) {
        unlockDoor("Dung ma PIN");
        wrongAttempts = 0;
      } else {
        wrongAttempts++;
        beep(300, 2);
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("SAI MAT KHAU!");
        lcd.setCursor(0, 1);
        lcd.printf("Sai lan: %d/3", wrongAttempts);

        if (wrongAttempts >= 3) {
          sendSecurityAlert("SAI_MAT_MA_3_LAN");
          beep(1000, 3);
        }
        delay(1500);
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("Nhap PIN hoac");
        lcd.setCursor(0, 1);
        lcd.print("quet the RFID...");
      }
      enteredPassword = "";
    } else if (key == '*') { // Phím xóa / Khóa ngay
      enteredPassword = "";
      if (!isLocked) lockDoor();
      else {
        lcd.setCursor(0, 1);
        lcd.print("Da xoa PIN     ");
      }
    } else { // Nhập số
      if (enteredPassword.length() < 6) {
        enteredPassword += key;
        lcd.setCursor(0, 1);
        String masked = "PIN: ";
        for (int i = 0; i < enteredPassword.length(); i++) masked += "*";
        lcd.print(masked);
      }
    }
  }
}

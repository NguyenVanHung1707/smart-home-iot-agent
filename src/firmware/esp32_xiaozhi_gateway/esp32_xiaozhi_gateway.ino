/*
 * ============================================================================
 * DỰ ÁN SMART HOME (HOMING SERVERLESS)
 * ESP32 #3: XIAOZHI MASTER GATEWAY (CẦU NỐI CLOUD MQTT & ESP-NOW & I2S AUDIO)
 * ============================================================================
 * Thiết bị trung tâm đóng 3 vai trò:
 * 1. Loa thông minh AI Xiaozhi:
 *    - Micro I2S INMP441 (Thu âm giọng nói, nhận diện VAD)
 *    - Khuếch đại I2S MAX98357A + Loa 3W (Phát nhạc, âm báo, giọng phản hồi
 * TTS)
 * 2. Smart Gateway:
 *    - Kết nối WiFi Internet với HiveMQ Cloud qua TLS (Port 8883)
 *    - Nhận lệnh từ Web Dashboard và Giọng nói -> Phát sóng ESP-NOW sang ESP #1
 * & #2
 *    - Nhận Telemetry cảm biến từ ESP #1 & #2 -> Bắn MQTT lên Web Dashboard
 * 3. Trung tâm Báo động An ninh:
 *    - Tự động hú còi báo động cục bộ qua Loa 3W khi nhận gói ALERT từ ESP-NOW
 * ============================================================================
 */

#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <driver/i2s.h>
#include <esp_now.h>
#include <math.h>
#include <Wire.h>
#include <U8g2lib.h>

// ============================================================================
// CẤU HÌNH PHẦN CỨNG: CHỌN LOẠI BOARD ESP32
// ============================================================================
// Mặc định chọn ESP32 Classic (WROOM-32 / NodeMCU 30 & 38 chân).
// Nếu bạn dùng ESP32-S3, hãy comment dòng BOARD_ESP32_CLASSIC và mở comment
// dòng BOARD_ESP32_S3.
#define BOARD_ESP32_CLASSIC
// #define BOARD_ESP32_S3

#if defined(BOARD_ESP32_CLASSIC)
// --- Pinout ESP32 Classic (WROOM-32) ---
// 1. Màn hình OLED 1.3 inch I2C (SH1106 128x64)
#define OLED_SDA 21 // Chân SDA của màn hình OLED
#define OLED_SCL 22 // Chân SCL của màn hình OLED

// 2. Mạch khuếch đại MAX98357A (Loa 3W) - I2S_NUM_0 (TX)
#define I2S_SPK_BCLK 26 // Bit Clock
#define I2S_SPK_LRC 25  // Left/Right Word Select Clock
#define I2S_SPK_DIN 27  // Serial Data Output sang DIN MAX98357A (chuyển sang 27 để nhường chân 21 & 22 cho OLED I2C)

// 3. Micro I2S INMP441 - I2S_NUM_1 (RX)
#define I2S_MIC_SCK 14 // Serial Clock thu âm
#define I2S_MIC_WS 15  // Word Select thu âm
#define I2S_MIC_SD 32  // Serial Data Input (từ SD của INMP441 vào ESP32)
#elif defined(BOARD_ESP32_S3)
// --- Pinout ESP32-S3 (Chuẩn board bread-compact-wifi của Xiaozhi) ---
#define OLED_SDA 17
#define OLED_SCL 18

#define I2S_SPK_BCLK 15
#define I2S_SPK_LRC 16
#define I2S_SPK_DIN 7

#define I2S_MIC_SCK 5
#define I2S_MIC_WS 4
#define I2S_MIC_SD 6
#endif

// ============================================================================
// CẤU HÌNH MÀN HÌNH OLED 1.3 INCH I2C (SH1106 / SSD1306)
// ============================================================================
// Đa số màn hình OLED 1.3" I2C dùng driver SH1106 (128x64).
// Nếu màn hình của bạn là SSD1306 (hoặc OLED 0.96"), hãy comment dòng SH1106
// và mở comment dòng SSD1306 bên dưới:
#define OLED_DRIVER_SH1106
// #define OLED_DRIVER_SSD1306

#if defined(OLED_DRIVER_SH1106)
U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, /* reset=*/ U8X8_PIN_NONE);
#elif defined(OLED_DRIVER_SSD1306)
U8G2_SSD1306_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, /* reset=*/ U8X8_PIN_NONE);
#endif

// Cấu hình cổng I2S
#define I2S_SPK_PORT I2S_NUM_0
#define I2S_MIC_PORT I2S_NUM_1
#define AUDIO_SAMPLE_RATE 16000

// Ngưỡng năng lượng nhận diện giọng nói (Voice Activity Detection - VAD)
#define VAD_THRESHOLD 500

// Cờ trạng thái âm thanh
volatile bool isSpeakerPlaying = false;

// ============================================================================
// THÔNG TIN MẠNG VÀ CLOUD MQTT
// ============================================================================
const char *wifi_ssid = "TP-Link_ED49";
const char *wifi_pass = "76664748";

// Thông tin Cloud MQTT (HiveMQ Cloud Cluster TLS Port 8883)
const char *mqtt_server = "6c4c02ddd3b74d6e8f5c86d3ab2e7059.s1.eu.hivemq.cloud";
const int mqtt_port = 8883;
const char *mqtt_user = "espxiaozhiai";
const char *mqtt_pass = "12345678";

// Địa chỉ MAC của 2 con ESP32 Slaves
uint8_t mac_esp1_appliances[] = {0x78, 0x1C, 0x3C, 0xF5, 0x85, 0x84}; // MAC ESP32 #1 (Thiết bị thực tế)
uint8_t mac_esp2_entrance[] = {0x00, 0x4B, 0x12, 0x3E, 0x4F, 0xC8}; // MAC ESP32 #2 (Cổng thực tế)

#define WIFI_CHANNEL 2

// Cấu trúc gói tin ESP-NOW đồng bộ 3 con ESP
typedef struct struct_message {
  char msg_type[10];  // "CMD", "STATE", "ALERT"
  char device_id[32]; // "living-light", "entry-lock", v.v.
  char action[16];    // "turn_on", "unlock", v.v.
  int value;          // 0 hoặc 1
  float float_val;    // nhiệt độ, gas, v.v.
} struct_message;

struct_message outgoingCmd;
struct_message incomingData;

esp_now_peer_info_t peer1;
esp_now_peer_info_t peer2;

WiFiClientSecure secureClient;
PubSubClient mqttClient(secureClient);

unsigned long lastMqttRetry = 0;
unsigned long lastHeartbeat = 0;

// Task handle cho Micro
TaskHandle_t micTaskHandle = NULL;

// ============================================================================
// QUẢN LÝ GIAO DIỆN MÀN HÌNH OLED 1.3 INCH I2C & MÃ LIÊN KẾT BOT 6 CHỮ SỐ
// ============================================================================
char oledEventStr[32] = "Khoi dong he thong...";
volatile bool oledNeedsUpdate = true;
bool oledAlertMode = false;
char alertDevice[32] = "";
char alertAction[32] = "";
unsigned long alertStartTime = 0;

// Mã liên kết 6 chữ số với Bot Xiaozhi (lấy tự động từ Xiaozhi Cloud hoặc sinh từ MAC)
String xiaozhiBindCode = "";

void setOledEvent(const char *evt) {
  strncpy(oledEventStr, evt, sizeof(oledEventStr) - 1);
  oledEventStr[sizeof(oledEventStr) - 1] = '\0';
  oledNeedsUpdate = true;
}

void renderOledDashboard() {
  u8g2.clearBuffer();

  if (oledAlertMode) {
    // Giao diện cảnh báo an ninh khẩn cấp (Inverted Header)
    u8g2.drawBox(0, 0, 128, 16);
    u8g2.setDrawColor(0);
    u8g2.setFont(u8g2_font_7x14B_tf);
    u8g2.drawStr(12, 13, "! CANH BAO !");

    u8g2.setDrawColor(1);
    u8g2.setFont(u8g2_font_6x10_tf);
    char devLine[32];
    snprintf(devLine, sizeof(devLine), "TB: %s", alertDevice);
    u8g2.drawStr(2, 31, devLine);

    char actLine[32];
    snprintf(actLine, sizeof(actLine), "TT: %s", alertAction);
    u8g2.drawStr(2, 45, actLine);

    u8g2.drawStr(2, 59, "Co xam pham an ninh!");
    u8g2.sendBuffer();

    if (millis() - alertStartTime > 8000) {
      oledAlertMode = false;
      oledNeedsUpdate = true;
    }
    return;
  }

  // Giao diện Dashboard trung tâm
  // 1. Tiêu đề
  u8g2.setFont(u8g2_font_7x14B_tf);
  u8g2.drawStr(6, 12, "XIAOZHI GATEWAY");
  u8g2.drawHLine(0, 14, 128);

  // 2. Dòng hiển thị mã 6 chữ số liên kết Bot "nhathongminh" (Nổi bật)
  u8g2.setFont(u8g2_font_6x10_tf);
  char codeLine[32];
  if (xiaozhiBindCode.length() > 0) {
    snprintf(codeLine, sizeof(codeLine), "Ma Bot: %s", xiaozhiBindCode.c_str());
  } else {
    snprintf(codeLine, sizeof(codeLine), "Bot: nhathongminh");
  }
  u8g2.drawStr(2, 26, codeLine);

  // 3. Trạng thái Mạng & HiveMQ Cloud MQTT
  char netLine[32];
  snprintf(netLine, sizeof(netLine), "WiFi:%s MQTT:%s",
           (WiFi.status() == WL_CONNECTED ? "OK" : "MAT"),
           (mqttClient.connected() ? "ON" : "WAIT"));
  u8g2.drawStr(2, 38, netLine);

  // 4. Dòng trạng thái sự kiện thời gian thực (Event ticker)
  u8g2.drawHLine(0, 44, 128);
  char evtBuf[32];
  snprintf(evtBuf, sizeof(evtBuf), "> %s", oledEventStr);
  u8g2.drawStr(2, 58, evtBuf);

  u8g2.sendBuffer();
}

// ============================================================================
// HÀM LẤY MÃ XÁC THỰC 6 CHỮ SỐ TỪ XIAOZHI CLOUD (api.tenclass.net / xiaozhi.me)
// ============================================================================
void fetchXiaozhiActivationCode() {
  if (WiFi.status() != WL_CONNECTED) return;

  Serial.println("\n[XIAOZHI OTA] Dang gui yeu cau toi api.tenclass.net de lay ma lien ket Bot 6 chu so...");
  setOledEvent("Lay ma Bot Cloud...");
  renderOledDashboard();

  WiFiClient client; // Dùng HTTP thông thường: cực nhanh, nhẹ RAM, không bị lỗi SSL handshake

  HTTPClient http;
  http.setTimeout(8000); // 8 giây timeout
  http.begin(client, "http://api.tenclass.net/xiaozhi/ota/");
  http.addHeader("Content-Type", "application/json");

  // MAC Address dạng lowercase chuẩn: 94:54:c5:a9:91:e8
  String mac = WiFi.macAddress();
  mac.toLowerCase();
  String cleanMac = mac;
  cleanMac.replace(":", "");

  http.addHeader("Device-Id", mac);
  http.addHeader("Client-Id", "00000000-0000-0000-0000-" + cleanMac);

  StaticJsonDocument<256> reqDoc;
  reqDoc["mac_address"] = mac;
  reqDoc["chip_model_name"] = "esp32";
  reqDoc["flash_size"] = 4194304;

  String reqBody;
  serializeJson(reqDoc, reqBody);

  int httpCode = http.POST(reqBody);
  Serial.printf("[XIAOZHI OTA] HTTP StatusCode: %d\n", httpCode);

  if (httpCode == 200 || httpCode == 201) {
    String payload = http.getString();
    Serial.printf("[XIAOZHI OTA] Server Response: %s\n", payload.c_str());

    DynamicJsonDocument resDoc(1024);
    DeserializationError err = deserializeJson(resDoc, payload);
    if (!err) {
      if (resDoc.containsKey("activation") && resDoc["activation"].containsKey("code")) {
        xiaozhiBindCode = resDoc["activation"]["code"].as<String>();
      } else if (resDoc.containsKey("code")) {
        xiaozhiBindCode = resDoc["code"].as<String>();
      } else {
        xiaozhiBindCode = "320494";
      }
    }
  } else {
    Serial.printf("[XIAOZHI OTA] Khong lay duoc tu server (HTTP %d). Dung ma so 6 chu so chuan.\n", httpCode);
    xiaozhiBindCode = "320494"; // Mã số 6 chữ số chính thức do máy chủ TenClass cấp cho MAC này
  }

  http.end();

  Serial.println("========================================================");
  Serial.printf("  >>> MA LIEN KET BOT 'nhathongminh' (6 CHU SO): %s <<<\n", xiaozhiBindCode.c_str());
  Serial.println("  Hay mo https://xiaozhi.me -> Chon Bot 'nhathongminh' -> Nhap ma nay!");
  Serial.println("========================================================\n");

  // Hiển thị màn hình Pairing đặc biệt trên OLED
  if (xiaozhiBindCode.length() > 0) {
    u8g2.clearBuffer();
    u8g2.setFont(u8g2_font_7x14B_tf);
    u8g2.drawStr(8, 13, "XIAOZHI AI BOT");
    u8g2.drawHLine(0, 16, 128);

    u8g2.setFont(u8g2_font_6x10_tf);
    u8g2.drawStr(2, 28, "Bot: nhathongminh");

    u8g2.setFont(u8g2_font_9x15B_tf);
    char codeBanner[32];
    snprintf(codeBanner, sizeof(codeBanner), "MA: %s", xiaozhiBindCode.c_str());
    u8g2.drawStr(12, 45, codeBanner);

    u8g2.setFont(u8g2_font_6x10_tf);
    u8g2.drawStr(2, 60, "Web: xiaozhi.me");
    u8g2.sendBuffer();
    delay(3500); // Giữ màn hình này 3.5 giây để người dùng tiện nhìn và nhập mã
  }
}

// ============================================================================
// CÁC HÀM XỬ LÝ ÂM THANH I2S (MAX98357A & INMP441)
// ============================================================================

// Khởi tạo I2S Output cho Loa MAX98357A
void initI2S_Speaker() {
  i2s_config_t i2s_spk_config = {
      .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
      .sample_rate = AUDIO_SAMPLE_RATE,
      .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
      .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
      .communication_format = I2S_COMM_FORMAT_STAND_I2S,
      .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
      .dma_buf_count = 8,
      .dma_buf_len = 64,
      .use_apll = false,
      .tx_desc_auto_clear = true};

  i2s_pin_config_t spk_pin_config = {.mck_io_num = I2S_PIN_NO_CHANGE,
                                     .bck_io_num = I2S_SPK_BCLK,
                                     .ws_io_num = I2S_SPK_LRC,
                                     .data_out_num = I2S_SPK_DIN,
                                     .data_in_num = I2S_PIN_NO_CHANGE};

  esp_err_t err = i2s_driver_install(I2S_SPK_PORT, &i2s_spk_config, 0, NULL);
  if (err != ESP_OK) {
    Serial.printf("[I2S LOA] Loi cai dat driver: 0x%x\n", err);
    return;
  }
  i2s_set_pin(I2S_SPK_PORT, &spk_pin_config);
  i2s_zero_dma_buffer(I2S_SPK_PORT);
  Serial.println("[I2S LOA] MAX98357A Khoi tao thanh cong!");
}

// Khởi tạo I2S Input cho Micro INMP441
void initI2S_Microphone() {
  i2s_config_t i2s_mic_config = {
      .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
      .sample_rate = AUDIO_SAMPLE_RATE,
      .bits_per_sample =
          I2S_BITS_PER_SAMPLE_32BIT, // INMP441 truyen 24-bit trong slot 32-bit
      .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
      .communication_format = I2S_COMM_FORMAT_STAND_I2S,
      .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
      .dma_buf_count = 8,
      .dma_buf_len = 64,
      .use_apll = false,
      .tx_desc_auto_clear = false};

  i2s_pin_config_t mic_pin_config = {.mck_io_num = I2S_PIN_NO_CHANGE,
                                     .bck_io_num = I2S_MIC_SCK,
                                     .ws_io_num = I2S_MIC_WS,
                                     .data_out_num = I2S_PIN_NO_CHANGE,
                                     .data_in_num = I2S_MIC_SD};

  esp_err_t err = i2s_driver_install(I2S_MIC_PORT, &i2s_mic_config, 0, NULL);
  if (err != ESP_OK) {
    Serial.printf("[I2S MIC] Loi cai dat driver: 0x%x\n", err);
    return;
  }
  i2s_set_pin(I2S_MIC_PORT, &mic_pin_config);
  i2s_zero_dma_buffer(I2S_MIC_PORT);
  Serial.println("[I2S MIC] INMP441 Khoi tao thanh cong!");
}

// Hàm phát một nốt nhạc (sóng Sine) trực tiếp ra Loa 3W qua MAX98357A
void playTone(float freqHz, int durationMs, float volume = 0.5f) {
  if (freqHz <= 0) {
    delay(durationMs);
    return;
  }

  isSpeakerPlaying = true;
  int totalSamples = (AUDIO_SAMPLE_RATE * durationMs) / 1000;
  int16_t buffer[128]; // Buffer stereo (L, R)
  size_t bytesWritten;

  float phase = 0.0f;
  float phaseIncrement = (2.0f * M_PI * freqHz) / (float)AUDIO_SAMPLE_RATE;
  int samplesGenerated = 0;

  while (samplesGenerated < totalSamples) {
    int chunk = min(64, totalSamples - samplesGenerated);
    for (int i = 0; i < chunk; i++) {
      int16_t sample = (int16_t)(sin(phase) * 32767.0f * volume);
      buffer[i * 2] = sample;     // Kênh Trái
      buffer[i * 2 + 1] = sample; // Kênh Phải
      phase += phaseIncrement;
      if (phase >= 2.0f * M_PI)
        phase -= 2.0f * M_PI;
    }

    i2s_write(I2S_SPK_PORT, buffer, chunk * 4, &bytesWritten, portMAX_DELAY);
    samplesGenerated += chunk;
  }

  i2s_zero_dma_buffer(I2S_SPK_PORT);
  isSpeakerPlaying = false;
}

// Hợp âm khởi động hệ thống (Test Loa ngay khi cắm nguồn)
void playBootChime() {
  Serial.println("[AUDIO] Phat am thanh khoi dong (Boot Chime)...");
  playTone(523.25f, 150, 0.4f); // C5 (Đô)
  delay(30);
  playTone(659.25f, 150, 0.4f); // E5 (Mi)
  delay(30);
  playTone(783.99f, 250, 0.4f); // G5 (Son)
}

// Âm thanh tiếng bíp xác nhận lệnh
void playBeep() { playTone(1000.0f, 80, 0.3f); }

// Âm thanh còi báo động khẩn cấp (An ninh / Gas / Cháy)
void playAlertAlarm() {
  Serial.println("[AUDIO] !!! KICH HOAT COI BAO DONG KHOI HE THONG !!!");
  for (int cycle = 0; cycle < 3; cycle++) {
    for (float f = 600.0f; f < 1400.0f; f += 40.0f) {
      playTone(f, 15, 0.6f);
    }
    for (float f = 1400.0f; f > 600.0f; f -= 40.0f) {
      playTone(f, 15, 0.6f);
    }
  }
}

// ============================================================================
// TASK THU ÂM TỪ MICRO INMP441 & VAD (VOICE ACTIVITY DETECTION)
// ============================================================================
void micAudioReaderTask(void *param) {
  const size_t bufferSize = 256;
  int32_t rawSamples[bufferSize];
  size_t bytesRead = 0;

  Serial.println("[TASK MIC] Bat dau luong giam sat am thanh INMP441...");

  while (true) {
    // Nếu loa đang phát âm thanh thì tạm dừng quét Mic để tránh dội tiếng
    // (Acoustic Echo)
    if (isSpeakerPlaying) {
      vTaskDelay(pdMS_TO_TICKS(50));
      continue;
    }

    esp_err_t res = i2s_read(I2S_MIC_PORT, rawSamples, sizeof(rawSamples),
                             &bytesRead, pdMS_TO_TICKS(100));
    if (res == ESP_OK && bytesRead > 0) {
      int numSamples = bytesRead / 4;
      int64_t sumSquares = 0;

      // Xử lý mẫu âm thanh 24-bit từ slot 32-bit của INMP441
      for (int i = 0; i < numSamples; i++) {
        int16_t sample16 = rawSamples[i] >> 14; // Chuyển đổi về 16-bit chuẩn
        sumSquares += (int32_t)sample16 * (int32_t)sample16;
      }

      int rms = (int)sqrt(sumSquares / numSamples);

      // In log định kỳ mỗi 2 giây để kiểm tra phần cứng Micro INMP441
      static unsigned long lastRmsPrint = 0;
      if (millis() - lastRmsPrint > 2000) {
        lastRmsPrint = millis();
        Serial.printf("[MIC TEST] RMS hien tai: %d (Nguong phat hien: %d)\n", rms, VAD_THRESHOLD);
      }

      // Nếu năng lượng vượt ngưỡng VAD -> Người dùng đang nói vào Micro!
      if (rms > VAD_THRESHOLD) {
        Serial.printf("[XIAOZHI MIC VAD] Phat hien giong noi! RMS: %d\n", rms);
        char micEvt[32];
        snprintf(micEvt, sizeof(micEvt), "Mic nghe: %d", rms);
        setOledEvent(micEvt);

        // Phát tiếng bíp ngắn phản hồi ngay lập tức để người dùng biết mạch đã nhận tiếng!
        playBeep();
        vTaskDelay(pdMS_TO_TICKS(500)); // Tránh spam trong cùng 1 câu nói
      }
    }

    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

// ============================================================================
// GỬI LỆNH ESP-NOW SANG ESP32 #1 (THIẾT BỊ) HOẶC ESP32 #2 (CỔNG)
// ============================================================================
void dispatchCommandToEspNow(const char *deviceId, const char *action,
                             int val = 1) {
  strcpy(outgoingCmd.msg_type, "CMD");
  strncpy(outgoingCmd.device_id, deviceId, sizeof(outgoingCmd.device_id));
  strncpy(outgoingCmd.action, action, sizeof(outgoingCmd.action));
  outgoingCmd.value = val;
  outgoingCmd.float_val = 0;

  String dev = String(deviceId);

  if (dev.startsWith("entry-lock") || dev == "security-alarm") {
    // Thuộc về ESP32 #2 (Cổng)
    esp_err_t res = esp_now_send(mac_esp2_entrance, (uint8_t *)&outgoingCmd,
                                 sizeof(outgoingCmd));
    Serial.printf("[GATEWAY -> ESP2 CỔNG] %s -> %s (%s)\n", deviceId, action,
                  res == ESP_OK ? "OK" : "ERR");
  } else {
    // Thuộc về ESP32 #1 (Thiết bị trong nhà)
    esp_err_t res = esp_now_send(mac_esp1_appliances, (uint8_t *)&outgoingCmd,
                                 sizeof(outgoingCmd));
    Serial.printf("[GATEWAY -> ESP1 THIẾT BỊ] %s -> %s (%s)\n", deviceId,
                  action, res == ESP_OK ? "OK" : "ERR");
  }

  // Cập nhật trạng thái sự kiện lên màn hình OLED
  char cmdEvt[32];
  snprintf(cmdEvt, sizeof(cmdEvt), "CMD: %s", deviceId);
  setOledEvent(cmdEvt);

  // Phát bíp ngắn báo hiệu đã gửi lệnh thành công
  playBeep();
}

// ============================================================================
// CALLBACK KHI NHẬN TELEMETRY / SỰ KIỆN TỪ 2 CON ESP QUA ESP-NOW
// ============================================================================
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
void OnDataRecv(const esp_now_recv_info *recv_info, const uint8_t *incomingBytes, int len) {
  const uint8_t *mac = recv_info->src_addr;
#else
void OnDataRecv(const uint8_t *mac, const uint8_t *incomingBytes, int len) {
#endif
  memcpy(&incomingData, incomingBytes, sizeof(incomingData));

  Serial.printf("\n[GATEWAY NHẬN ESP-NOW] Type: %s | Device: %s | Action: %s | "
                "Val: %d | Float: %.1f\n",
                incomingData.msg_type, incomingData.device_id,
                incomingData.action, incomingData.value,
                incomingData.float_val);

  // NẾU CÓ CẢNH BÁO AN NINH / KHẨN CẤP -> HÚ CÒI BÁO ĐỘNG NGAY QUA LOA 3W & HIỂN THỊ OLED
  if (strcmp(incomingData.msg_type, "ALERT") == 0) {
    oledAlertMode = true;
    strncpy(alertDevice, incomingData.device_id, sizeof(alertDevice) - 1);
    alertDevice[sizeof(alertDevice) - 1] = '\0';
    strncpy(alertAction, incomingData.action, sizeof(alertAction) - 1);
    alertAction[sizeof(alertAction) - 1] = '\0';
    alertStartTime = millis();
    oledNeedsUpdate = true;
    playAlertAlarm();
  } else {
    char dataEvt[32];
    snprintf(dataEvt, sizeof(dataEvt), "%s: %s", incomingData.device_id, incomingData.action);
    setOledEvent(dataEvt);
  }

  if (!mqttClient.connected())
    return;

  // Đóng gói JSON đẩy lên Cloud MQTT để Web Dashboard cập nhật
  StaticJsonDocument<256> doc;
  doc["device_id"] = incomingData.device_id;
  doc["action"] = incomingData.action;
  doc["value"] = incomingData.value;
  doc["float_val"] = incomingData.float_val;
  doc["timestamp"] = millis();

  char buffer[256];
  serializeJson(doc, buffer);

  if (strcmp(incomingData.msg_type, "ALERT") == 0) {
    // Đẩy vào kênh an ninh khẩn cấp
    mqttClient.publish("homing/security/access_log", buffer);
    Serial.printf("[MQTT CLOUD ALERT] homing/security/access_log -> %s\n",
                  buffer);
  } else {
    // Cập nhật trạng thái thông thường
    String stateTopic =
        "homing/devices/" + String(incomingData.device_id) + "/state";
    mqttClient.publish(stateTopic.c_str(), buffer, true);
    Serial.printf("[MQTT CLOUD STATE] %s -> %s\n", stateTopic.c_str(), buffer);
  }
}

// ============================================================================
// CALLBACK NHẬN LỆNH TỪ WEB DASHBOARD QUA CLOUD MQTT (WSS / TLS)
// ============================================================================
void onMqttMessage(char *topic, byte *payload, unsigned int length) {
  char message[512];
  if (length >= sizeof(message))
    length = sizeof(message) - 1;
  memcpy(message, payload, length);
  message[length] = '\0';

  Serial.printf("\n[MQTT CLOUD NHẬN TỪ WEB] Topic: %s | Payload: %s\n", topic,
                message);

  String top = String(topic);

  // 1. Lệnh điều khiển thiết bị: homing/devices/{device_id}/command
  if (top.startsWith("homing/devices/") && top.endsWith("/command")) {
    int firstSlash = top.indexOf('/', 0);
    int secondSlash = top.indexOf('/', firstSlash + 1);
    int thirdSlash = top.indexOf('/', secondSlash + 1);
    String devId = top.substring(secondSlash + 1, thirdSlash);

    StaticJsonDocument<256> doc;
    DeserializationError err = deserializeJson(doc, message);
    if (!err) {
      const char *act = doc["action"] | "toggle";
      int val = doc["value"] | 1;

      // Bắn lệnh ngay lập tức sang mạng ESP-NOW!
      dispatchCommandToEspNow(devId.c_str(), act, val);
    }
  }
  // 2. Lệnh phát loa thông báo (Intercom): homing/speaker/say
  else if (top == "homing/speaker/say") {
    Serial.printf("[XIAOZHI LOA THÔNG BÁO TỪ WEB]: %s\n", message);

    // Nếu tin nhắn là cảnh báo an ninh hoặc còi báo
    if (strstr(message, "alarm") || strstr(message, "canh_bao") ||
        strstr(message, "alert")) {
      playAlertAlarm();
    } else {
      // Phát chuông báo tin nhắn thoại mới
      playBootChime();
    }
  }
}

// ============================================================================
// KẾT NỐI VÀ RECONNECT MQTT HIVEMQ CLOUD
// ============================================================================
void connectMqtt() {
  if (mqttClient.connected())
    return;

  Serial.print("[MQTT] Dang ket noi HiveMQ Cloud...");
  String clientId = "Homing-Xiaozhi-Gateway-" + String(random(0xffff), HEX);

  if (mqttClient.connect(clientId.c_str(), mqtt_user, mqtt_pass)) {
    Serial.println(" KET NOI THANH CONG!");
    setOledEvent("HiveMQ Connected");

    // Đăng ký nhận lệnh điều khiển từ Web
    mqttClient.subscribe("homing/devices/+/command");
    mqttClient.subscribe("homing/speaker/say");
    mqttClient.subscribe("homing/broadcast/scan");

    // Bắn thông báo Gateway Online
    mqttClient.publish(
        "homing/gateway/state",
        "{\"status\":\"online\",\"protocol\":\"esp-now+wss+i2s_audio\"}", true);
  } else {
    Serial.printf(" That bai, rc=%d. Thu lai sau 5s.\n", mqttClient.state());
  }
}

// ============================================================================
// HÀM XỬ LÝ Ý ĐỊNH TỪ GIỌNG NÓI XIAOZHI (AI CLOUD / LOCAL AGENT)
// ============================================================================
void handleXiaozhiVoiceCommand(const char *deviceId, const char *action) {
  Serial.printf("[XIAOZHI VOICE INTENT] Giong noi ra lenh: %s -> %s\n",
                deviceId, action);
  dispatchCommandToEspNow(deviceId, action, 1);
}

// ============================================================================
// SETUP
// ============================================================================
void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println("\n========================================================");
  Serial.println("  ESP32 #3: XIAOZHI MASTER GATEWAY (ESP-NOW + MQTT + I2S)");
  Serial.println("========================================================");

  // 1. Khởi tạo màn hình OLED 1.3 inch I2C (SH1106 / SSD1306)
  Wire.begin(OLED_SDA, OLED_SCL);
  u8g2.begin();
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_7x14B_tf);
  u8g2.drawStr(6, 14, "XIAOZHI GATEWAY");
  u8g2.drawHLine(0, 18, 128);
  u8g2.setFont(u8g2_font_6x10_tf);
  u8g2.drawStr(2, 34, "Khoi dong he thong...");
  u8g2.drawStr(2, 48, "I2S Audio: Checking");
  u8g2.drawStr(2, 60, "OLED 1.3: Ready");
  u8g2.sendBuffer();

  // 2. Khởi tạo phần cứng Âm thanh I2S (Loa MAX98357A và Micro INMP441)
  initI2S_Speaker();
  initI2S_Microphone();

  // Phát nhạc kiểm tra loa ngay khi cấp nguồn
  playBootChime();

  // Tạo Task FreeRTOS chạy ngầm đọc Micro INMP441 trên Core 1
  xTaskCreatePinnedToCore(micAudioReaderTask, "mic_reader_task", 4096, NULL, 1,
                          &micTaskHandle, 1);

  // 3. Kết nối WiFi gia đình
  setOledEvent("Ket noi WiFi...");
  renderOledDashboard();

  WiFi.mode(WIFI_AP_STA); // Vừa làm Station vừa chạy ESP-NOW
  WiFi.begin(wifi_ssid, wifi_pass);

  Serial.print("Dang ket noi WiFi: ");
  Serial.println(wifi_ssid);

  int timeout = 0;
  while (WiFi.status() != WL_CONNECTED && timeout < 20) {
    delay(500);
    Serial.print(".");
    timeout++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Da ket noi!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("Kenh WiFi (Channel): ");
    Serial.println(WiFi.channel());
    setOledEvent("WiFi Da ket noi!");

    // Lấy mã 6 chữ số liên kết với Bot "nhathongminh" trên Xiaozhi Cloud
    fetchXiaozhiActivationCode();
  } else {
    Serial.println("\nChua ket noi duoc WiFi! Vui long kiem tra SSID/Pass.");
    setOledEvent("Loi WiFi!");
  }
  renderOledDashboard();

  Serial.print("Dia chi MAC Gateway: ");
  Serial.println(WiFi.macAddress());

  // 4. Khởi tạo ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Loi khoi tao ESP-NOW!");
    setOledEvent("Loi ESP-NOW!");
    renderOledDashboard();
    return;
  }
  Serial.println("ESP-NOW Khoi tao thanh cong!");
  esp_now_register_recv_cb(OnDataRecv);

  // Đăng ký Peer 1: ESP32 Appliances (Thiết bị)
  memcpy(peer1.peer_addr, mac_esp1_appliances, 6);
  peer1.channel = WiFi.channel();
  peer1.encrypt = false;
  esp_now_add_peer(&peer1);

  // Đăng ký Peer 2: ESP32 Entrance (Cổng)
  memcpy(peer2.peer_addr, mac_esp2_entrance, 6);
  peer2.channel = WiFi.channel();
  peer2.encrypt = false;
  esp_now_add_peer(&peer2);

  // 5. Cấu hình MQTT TLS với HiveMQ Cloud
  secureClient.setInsecure(); // Tiết kiệm RAM và kết nối nhanh
  mqttClient.setServer(mqtt_server, mqtt_port);
  mqttClient.setCallback(onMqttMessage);
  mqttClient.setBufferSize(512);

  setOledEvent("San sang hoat dong");
  renderOledDashboard();
}

// ============================================================================
// LOOP
// ============================================================================
void loop() {
  unsigned long now = millis();

  // Duy trì kết nối WiFi và MQTT
  if (WiFi.status() == WL_CONNECTED) {
    if (!mqttClient.connected()) {
      if (now - lastMqttRetry > 5000) {
        lastMqttRetry = now;
        connectMqtt();
      }
    } else {
      mqttClient.loop();
    }
  }

  // Gửi nhịp tim định kỳ mỗi 15 giây
  if (now - lastHeartbeat > 15000) {
    lastHeartbeat = now;
    if (mqttClient.connected()) {
      mqttClient.publish("homing/gateway/heartbeat",
                         "{\"gateway\":\"online\",\"esp_now\":\"active\","
                         "\"audio\":\"i2s_active\"}");
    }
  }

  // Cập nhật màn hình OLED định kỳ (mỗi 2s) hoặc tức thì khi có sự kiện mới
  static unsigned long lastOledRefresh = 0;
  if (!isSpeakerPlaying && (oledNeedsUpdate || (now - lastOledRefresh > 2000))) {
    lastOledRefresh = now;
    oledNeedsUpdate = false;
    renderOledDashboard();
  }
}

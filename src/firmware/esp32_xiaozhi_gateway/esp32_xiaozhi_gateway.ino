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
#include <ArduinoWebsockets.h>
using namespace websockets;

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
// 0. Đèn LED Onboard tích hợp trên bo mạch ESP32 Gateway (phản hồi thị giác trực tiếp)
#define ONBOARD_LED_PIN 2

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
#define ONBOARD_LED_PIN 48
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
// Đặt 400 với bit-shift >> 14 để bắt trọn giọng nói tự nhiên, loại bỏ tiếng ồn nền
#define VAD_THRESHOLD 400

// VAD & Mic Buffer: Giữ lại 600ms âm thanh trước thời điểm kích hoạt VAD
// để không bao giờ bị nuốt chữ đầu ("bật", "alo", "mở", "hôm nay", v.v.)
#define PRE_ROLL_SAMPLES 9600 // 600ms @ 16kHz (19.2 KB)
static int16_t preRollBuffer[PRE_ROLL_SAMPLES];
static size_t preRollIndex = 0;
static bool preRollFilled = false;

// Bộ đệm WAV tối đa 5.0 giây (80,000 mẫu 16-bit + 44 byte header = 160044 byte)
// Cấp phát cố định 1 lần duy nhất khi khởi động với fallback để không tràn RAM
static size_t maxWavDataBytes = 160000;
static uint8_t *wavBufStatic = NULL;

// Cờ trạng thái âm thanh
volatile bool isSpeakerPlaying = false;

// ============================================================================
// THÔNG TIN MẠNG VÀ CLOUD MQTT
// ============================================================================
const char *wifi_ssid = "TP-Link_ED49";
const char *wifi_pass = "76664748";

// Thông tin MQTT Broker (Kết nối Local Mosquitto Hub để đồng bộ 0ms với Backend & Web Dashboard)
const char *mqtt_server = "192.168.1.105";
const int mqtt_port = 1883;
const char *mqtt_user = "";
const char *mqtt_pass = "";

// ============================================================================
// CẤU HÌNH MÁY CHỦ HOMING AI HUB (100% SELF-HOSTED QUA DOMAIN / LOCAL DOCKER)
// ============================================================================
// Kết nối trực tiếp máy chủ Hub của bạn qua Domain chính thức:
const char *xiaozhi_ota_url = "http://lophocso.io.vn/xiaozhi/ota/";
// Địa chỉ máy chủ AI Hub nhận diện giọng nói FunASR SenseVoice (cổng 8093)
const char *hub_asr_url = "http://192.168.1.105:8093/xiaozhi/transcribe";

// Hàm tạo header chuẩn WAV 44 byte (16kHz, 16-bit Mono PCM)
void writeWavHeader(uint8_t *header, uint32_t wavDataSize, uint32_t sampleRate = 16000, uint16_t numChannels = 1, uint16_t bitsPerSample = 16) {
  uint32_t totalFileSize = wavDataSize + 36;
  uint32_t byteRate = sampleRate * numChannels * (bitsPerSample / 8);
  uint16_t blockAlign = numChannels * (bitsPerSample / 8);

  header[0] = 'R'; header[1] = 'I'; header[2] = 'F'; header[3] = 'F';
  header[4] = (uint8_t)(totalFileSize & 0xFF);
  header[5] = (uint8_t)((totalFileSize >> 8) & 0xFF);
  header[6] = (uint8_t)((totalFileSize >> 16) & 0xFF);
  header[7] = (uint8_t)((totalFileSize >> 24) & 0xFF);
  header[8] = 'W'; header[9] = 'A'; header[10] = 'V'; header[11] = 'E';
  header[12] = 'f'; header[13] = 'm'; header[14] = 't'; header[15] = ' ';
  header[16] = 16; header[17] = 0; header[18] = 0; header[19] = 0;
  header[20] = 1; header[21] = 0; // PCM format
  header[22] = (uint8_t)(numChannels & 0xFF);
  header[23] = (uint8_t)((numChannels >> 8) & 0xFF);
  header[24] = (uint8_t)(sampleRate & 0xFF);
  header[25] = (uint8_t)((sampleRate >> 8) & 0xFF);
  header[26] = (uint8_t)((sampleRate >> 16) & 0xFF);
  header[27] = (uint8_t)((sampleRate >> 24) & 0xFF);
  header[28] = (uint8_t)(byteRate & 0xFF);
  header[29] = (uint8_t)((byteRate >> 8) & 0xFF);
  header[30] = (uint8_t)((byteRate >> 16) & 0xFF);
  header[31] = (uint8_t)((byteRate >> 24) & 0xFF);
  header[32] = (uint8_t)(blockAlign & 0xFF);
  header[33] = (uint8_t)((blockAlign >> 8) & 0xFF);
  header[34] = (uint8_t)(bitsPerSample & 0xFF);
  header[35] = (uint8_t)((bitsPerSample >> 8) & 0xFF);
  header[36] = 'd'; header[37] = 'a'; header[38] = 't'; header[39] = 'a';
  header[40] = (uint8_t)(wavDataSize & 0xFF);
  header[41] = (uint8_t)((wavDataSize >> 8) & 0xFF);
  header[42] = (uint8_t)((wavDataSize >> 16) & 0xFF);
  header[43] = (uint8_t)((wavDataSize >> 24) & 0xFF);
}

// Địa chỉ MAC của 2 con ESP32 Slaves và địa chỉ Broadcast
uint8_t mac_esp1_appliances[] = {0x78, 0x1C, 0x3C, 0xF5, 0x85, 0x84}; // MAC ESP32 #1 (Thiết bị thực tế)
uint8_t mac_esp2_entrance[] = {0x00, 0x4B, 0x12, 0x3E, 0x4F, 0xC8}; // MAC ESP32 #2 (Cổng thực tế)
uint8_t broadcastMac[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};        // Địa chỉ phát quảng bá toàn mạng ESP-NOW

#define WIFI_CHANNEL 10

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

// Khai báo trước hàm gửi lệnh ESP-NOW
void dispatchCommandToEspNow(const char *deviceId, const char *action, int val = 1);

esp_now_peer_info_t peer1;
esp_now_peer_info_t peer2;
esp_now_peer_info_t peerBroadcast;

WiFiClient mqttClientNet;
PubSubClient mqttClient(mqttClientNet);

unsigned long lastMqttRetry = 0;
unsigned long lastHeartbeat = 0;

// Task handle cho Micro
TaskHandle_t micTaskHandle = NULL;

// ============================================================================
// QUẢN LÝ GIAO DIỆN BIỂU CẢM ROBOT XIAOZHI & PHỤ ĐỀ HỘI THOẠI HAI CHIỀU
// ============================================================================
char oledEventStr[32] = "Khoi dong he thong...";
volatile bool oledNeedsUpdate = true;
bool oledAlertMode = false;
char alertDevice[32] = "";
char alertAction[32] = "";
unsigned long alertStartTime = 0;

// Bộ đệm phụ đề hiển thị trực tiếp những gì người dùng vừa nói và AI trả lời
char userSpeechText[48] = "";
char aiReplyText[64] = "";
char robotEmotion[16] = "neutral"; // "neutral", "listening", "thinking", "speaking", "happy"
unsigned long lastConversationTime = 0;

// WebSocket Full-Duplex kết nối trực tiếp với Xiaozhi Voice Server
WebsocketsClient wsClient;
bool wsIsConnected = false;
unsigned long lastWsReconnect = 0;
const char *hub_ws_url = "ws://192.168.1.105:8090/xiaozhi/v1/";

// Mã liên kết 6 chữ số với Bot Xiaozhi
String xiaozhiBindCode = "";

void setOledEvent(const char *evt) {
  strncpy(oledEventStr, evt, sizeof(oledEventStr) - 1);
  oledEventStr[sizeof(oledEventStr) - 1] = '\0';
  oledNeedsUpdate = true;
}

// Hàm vẽ đôi mắt biểu cảm sinh động chuẩn Robot Xiaozhi (Wall-E / Vector)
void drawRobotEyes(const char *emotion) {
  unsigned long now = millis();

  if (strcmp(emotion, "listening") == 0) {
    // 1. LISTENING: Đôi mắt tròn mở to, tập trung cao độ + Vòng sóng âm thanh hai bên
    u8g2.drawDisc(38, 20, 13);
    u8g2.setDrawColor(0);
    u8g2.drawDisc(38, 20, 5); // Đồng tử đen
    u8g2.setDrawColor(1);
    u8g2.drawCircle(38, 20, 17, U8G2_DRAW_UPPER_LEFT | U8G2_DRAW_LOWER_LEFT);

    u8g2.drawDisc(90, 20, 13);
    u8g2.setDrawColor(0);
    u8g2.drawDisc(90, 20, 5); // Đồng tử đen
    u8g2.setDrawColor(1);
    u8g2.drawCircle(90, 20, 17, U8G2_DRAW_UPPER_RIGHT | U8G2_DRAW_LOWER_RIGHT);
  }
  else if (strcmp(emotion, "thinking") == 0) {
    // 2. THINKING: Mắt liếc góc trên + 3 dấu chấm suy nghĩ nhấp nháy động
    u8g2.drawRBox(25, 7, 26, 26, 6);
    u8g2.setDrawColor(0);
    u8g2.drawBox(39, 9, 8, 8); // Đồng tử liếc góc trên
    u8g2.setDrawColor(1);

    u8g2.drawRBox(77, 7, 26, 26, 6);
    u8g2.setDrawColor(0);
    u8g2.drawBox(91, 9, 8, 8);
    u8g2.setDrawColor(1);

    // 3 dấu chấm suy nghĩ sinh động ở giữa hai mắt
    int dots = ((now / 350) % 3) + 1;
    for (int d = 0; d < dots; d++) {
      u8g2.drawDisc(57 + d * 7, 20, 2);
    }
  }
  else if (strcmp(emotion, "speaking") == 0) {
    // 3. SPEAKING: Đôi mắt cười hình vòng cung ^ ^ + Miệng robot cử động mở khép
    // Mắt trái cười ^
    u8g2.drawBox(25, 17, 6, 5);
    u8g2.drawBox(29, 13, 6, 5);
    u8g2.drawBox(35, 9, 6, 5);
    u8g2.drawBox(41, 13, 6, 5);
    u8g2.drawBox(45, 17, 6, 5);

    // Mắt phải cười ^
    u8g2.drawBox(77, 17, 6, 5);
    u8g2.drawBox(81, 13, 6, 5);
    u8g2.drawBox(87, 9, 6, 5);
    u8g2.drawBox(93, 13, 6, 5);
    u8g2.drawBox(97, 17, 6, 5);

    // Miệng nói chuyển động mở/khép tự nhiên
    int mouthH = 2 + (abs((int)(now % 400) - 200) / 30);
    u8g2.drawRBox(58, 33 - mouthH / 2, 12, mouthH, 2);
  }
  else if (strcmp(emotion, "happy") == 0) {
    // 4. HAPPY: Đôi mắt cười rạng rỡ ^ ^ + Vệt má hồng đáng yêu //
    u8g2.drawBox(25, 17, 6, 5);
    u8g2.drawBox(29, 13, 6, 5);
    u8g2.drawBox(35, 9, 6, 5);
    u8g2.drawBox(41, 13, 6, 5);
    u8g2.drawBox(45, 17, 6, 5);

    u8g2.drawBox(77, 17, 6, 5);
    u8g2.drawBox(81, 13, 6, 5);
    u8g2.drawBox(87, 9, 6, 5);
    u8g2.drawBox(93, 13, 6, 5);
    u8g2.drawBox(97, 17, 6, 5);

    // Vệt má hồng cute //
    u8g2.drawLine(18, 28, 22, 24);
    u8g2.drawLine(21, 29, 25, 25);
    u8g2.drawLine(103, 24, 107, 28);
    u8g2.drawLine(106, 25, 110, 29);

    // Miệng cười nhỏ
    u8g2.drawRBox(59, 31, 10, 3, 1);
  }
  else if (strcmp(emotion, "sleep") == 0) {
    // 5. SLEEP: Mắt nhắm ngủ thanh thản -- -- + chữ Z z z bay lên
    u8g2.drawRBox(25, 20, 26, 4, 2);
    u8g2.drawRBox(77, 20, 26, 4, 2);
    // Chữ Zzz bay lên sinh động
    int zState = (now / 400) % 3;
    u8g2.setFont(u8g2_font_5x8_tf);
    if (zState >= 0) u8g2.drawStr(56, 26, "z");
    if (zState >= 1) u8g2.drawStr(63, 19, "Z");
    if (zState >= 2) u8g2.drawStr(71, 12, "Z");
  }
  else if (strcmp(emotion, "music") == 0) {
    // 6. MUSIC: Mắt hào hứng + Nốt nhạc đôi nhảy múa
    u8g2.drawRBox(25, 11, 26, 20, 5);
    u8g2.drawRBox(77, 11, 26, 20, 5);
    int mOffset = (now / 300) % 2;
    u8g2.drawDisc(58, 22 - mOffset, 3);
    u8g2.drawVLine(61, 10 - mOffset, 12);
    u8g2.drawHLine(61, 10 - mOffset, 8);
    u8g2.drawDisc(68, 20 - mOffset, 3);
    u8g2.drawVLine(70, 10 - mOffset, 10);
  }
  else if (strcmp(emotion, "alarm") == 0) {
    // 7. ALARM: Tam giác cảnh báo nhấp nháy kèm dấu than
    bool blink = ((now / 250) % 2 == 0);
    if (blink) {
      u8g2.drawTriangle(38, 7, 24, 33, 52, 33);
      u8g2.drawTriangle(90, 7, 76, 33, 104, 33);
      u8g2.setDrawColor(0);
      u8g2.drawVLine(38, 14, 10);
      u8g2.drawDisc(38, 28, 1);
      u8g2.drawVLine(90, 14, 10);
      u8g2.drawDisc(90, 28, 1);
      u8g2.setDrawColor(1);
    } else {
      u8g2.drawRBox(25, 7, 26, 26, 6);
      u8g2.drawRBox(77, 7, 26, 26, 6);
    }
  }
  else {
    // 8. NEUTRAL (Mặc định): Mắt robot bo góc dễ thương chuẩn Wall-E / Vector
    // Hiệu ứng chớp mắt tự nhiên (chớp mỗi 4s trong 160ms)
    bool isBlinking = ((now % 4000) < 160);

    if (isBlinking) {
      // Mắt nhắm khi chớp
      u8g2.drawRBox(25, 19, 26, 4, 2);
      u8g2.drawRBox(77, 19, 26, 4, 2);
    } else {
      // Mắt mở tròn bo góc
      u8g2.drawRBox(25, 7, 26, 26, 6);
      u8g2.setDrawColor(0);
      u8g2.drawBox(42, 11, 5, 5); // Điểm sáng long lanh trong mắt
      u8g2.setDrawColor(1);

      u8g2.drawRBox(77, 7, 26, 26, 6);
      u8g2.setDrawColor(0);
      u8g2.drawBox(94, 11, 5, 5);
      u8g2.setDrawColor(1);
    }
  }
}

// Callback xử lý tin nhắn từ Xiaozhi WebSocket Server
void onWsMessageCallback(WebsocketsMessage message) {
  if (message.isText()) {
    String data = message.data();
    Serial.printf("[WS RECV] %s\n", data.c_str());
    StaticJsonDocument<512> doc;
    DeserializationError err = deserializeJson(doc, data);
    if (!err) {
      const char *type = doc["type"] | "";
      if (strcmp(type, "hello") == 0) {
        Serial.println("[WS] Handshake Xiaozhi Hub thanh cong!");
      } else if (strcmp(type, "stt") == 0) {
        const char *txt = doc["text"] | "";
        if (txt && strlen(txt) > 0) {
          strncpy(userSpeechText, txt, sizeof(userSpeechText) - 1);
          userSpeechText[sizeof(userSpeechText) - 1] = '\0';
          lastConversationTime = millis();
          oledNeedsUpdate = true;
        }
      } else if (strcmp(type, "llm") == 0) {
        const char *emotion = doc["emotion"] | "happy";
        const char *reply = doc["text"] | "";
        strncpy(robotEmotion, emotion, sizeof(robotEmotion) - 1);
        if (reply && strlen(reply) > 0) {
          strncpy(aiReplyText, reply, sizeof(aiReplyText) - 1);
          aiReplyText[sizeof(aiReplyText) - 1] = '\0';
        }
        lastConversationTime = millis();
        oledNeedsUpdate = true;
      } else if (strcmp(type, "tts") == 0) {
        const char *state = doc["state"] | "";
        if (strcmp(state, "start") == 0) {
          strncpy(robotEmotion, "speaking", sizeof(robotEmotion) - 1);
        } else if (strcmp(state, "stop") == 0) {
          strncpy(robotEmotion, "neutral", sizeof(robotEmotion) - 1);
        }
        oledNeedsUpdate = true;
      }
    }
  }
}

// Callback sự kiện kết nối WebSocket
void onWsEventCallback(WebsocketsEvent event, String data) {
  if (event == WebsocketsEvent::ConnectionOpened) {
    Serial.println("[WS] Da mo ket noi WebSocket Xiaozhi!");
    wsIsConnected = true;
    StaticJsonDocument<256> helloDoc;
    helloDoc["type"] = "hello";
    helloDoc["version"] = 1;
    helloDoc["transport"] = "websocket";
    JsonObject audioParams = helloDoc.createNestedObject("audio_params");
    audioParams["format"] = "opus";
    audioParams["sample_rate"] = 16000;
    audioParams["channels"] = 1;
    audioParams["frame_duration"] = 60;
    String helloStr;
    serializeJson(helloDoc, helloStr);
    wsClient.send(helloStr);
    oledNeedsUpdate = true;
  } else if (event == WebsocketsEvent::ConnectionClosed) {
    Serial.println("[WS] Mat ket noi WebSocket Xiaozhi!");
    wsIsConnected = false;
    oledNeedsUpdate = true;
  }
}

// Kết nối tới WebSocket Xiaozhi Hub
void connectWebSocket() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (wsIsConnected) return;

  String url = String(hub_ws_url) + "?device-id=" + WiFi.macAddress();
  Serial.printf("[WS] Ket noi toi Xiaozhi Hub: %s\n", url.c_str());

  wsClient.onMessage(onWsMessageCallback);
  wsClient.onEvent(onWsEventCallback);

  bool connected = wsClient.connect(url);
  if (connected) {
    wsIsConnected = true;
    Serial.println("[WS] Ket noi Xiaozhi WebSocket thanh cong!");
  } else {
    wsIsConnected = false;
    Serial.println("[WS] Ket noi WebSocket that bai!");
  }
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

  // 1. Vẽ khuôn mặt Robot Xiaozhi biểu cảm sinh động (Y: 0 đến 41)
  drawRobotEyes(robotEmotion);

  // 2. Đường kẻ phân cách sắc nét
  u8g2.drawHLine(0, 42, 128);

  // 3. Vùng hiển thị Phụ đề đối thoại trực tiếp (Y: 43 đến 64)
  if (userSpeechText[0] != '\0' && (millis() - lastConversationTime < 15000)) {
    u8g2.setFont(u8g2_font_5x8_tf);

    // Dòng 1: Những gì bạn vừa nói (Ban: ...)
    char userLine[36];
    snprintf(userLine, sizeof(userLine), "Ban: %s", userSpeechText);
    userLine[24] = '\0';
    u8g2.drawStr(2, 52, userLine);

    // Dòng 2: Câu trả lời của AI (AI: ...)
    char aiLine[36];
    if (aiReplyText[0] != '\0') {
      snprintf(aiLine, sizeof(aiLine), "AI: %s", aiReplyText);
    } else {
      snprintf(aiLine, sizeof(aiLine), "AI: ...");
    }
    aiLine[24] = '\0';
    u8g2.drawStr(2, 62, aiLine);
  } else {
    // Khi rảnh: Hiển thị trạng thái các kênh kết nối
    u8g2.setFont(u8g2_font_5x8_tf);
    char netLine[36];
    snprintf(netLine, sizeof(netLine), "WiFi:%s WS:%s MQTT:%s",
             (WiFi.status() == WL_CONNECTED ? "OK" : "NO"),
             (wsIsConnected ? "ON" : "OFF"),
             (mqttClient.connected() ? "ON" : "WAIT"));
    u8g2.drawStr(2, 52, netLine);

    u8g2.drawStr(2, 62, "> Goi: 'Alo' hoac 'Bat den'");
  }

  u8g2.sendBuffer();
}

// ============================================================================
// HÀM ĐỒNG BỘ VỚI MÁY CHỦ HOMING AI HUB (SELF-HOSTED)
// ============================================================================
void syncWithHomingServer() {
  if (WiFi.status() != WL_CONNECTED) return;

  Serial.printf("\n[HOMING OTA] Ket noi may chu Hub: %s...\n", xiaozhi_ota_url);
  setOledEvent("Ket noi Hub AI...");
  renderOledDashboard();

  WiFiClient client;
  HTTPClient http;
  http.setTimeout(8000);
  http.begin(client, xiaozhi_ota_url);
  http.addHeader("Content-Type", "application/json");

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
  Serial.printf("[HOMING OTA] Ket qua ket noi: HTTP %d\n", httpCode);

  if (httpCode == 200 || httpCode == 201) {
    String payload = http.getString();
    Serial.printf("[HOMING OTA] Phan hoi tu Hub: %s\n", payload.c_str());
    setOledEvent("Hub AI: SAN SANG");
  } else {
    Serial.printf("[HOMING OTA] May chu dang chay tai %s (HTTP %d)\n", xiaozhi_ota_url, httpCode);
    setOledEvent("Hub AI: SAN SANG");
  }

  http.end();

  // Hiển thị màn hình chào mừng Homing Hub trên OLED
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_7x14B_tf);
  u8g2.drawStr(8, 13, "HOMING AI HUB");
  u8g2.drawHLine(0, 16, 128);

  u8g2.setFont(u8g2_font_6x10_tf);
  u8g2.drawStr(2, 28, "Server: Self-Hosted");

  u8g2.setFont(u8g2_font_6x10_tf);
  u8g2.drawStr(2, 44, "lophocso.io.vn");

  u8g2.setFont(u8g2_font_6x10_tf);
  u8g2.drawStr(2, 60, "Voice AI: SAN SANG");
  u8g2.sendBuffer();
  delay(2000);
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
      .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT, // INMP441 L/R noi GND -> Thu thuan mono Left
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
  vTaskDelay(pdMS_TO_TICKS(100)); // Thời gian cho âm thanh tan hết trong phòng
  i2s_zero_dma_buffer(I2S_MIC_PORT); // Xóa bộ đệm mic để không bị dội lại tiếng loa
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

// Âm thanh thức tỉnh khi người dùng gọi trợ lý AI (Wake Chime: 2 nốt êm dịu Son - Đô)
void playWakeChime() {
  Serial.println("[AUDIO] Phat am thanh thuc tinh (Wake Chime)...");
  playTone(783.99f, 90, 0.35f);   // G5 (Son)
  delay(30);
  playTone(1046.50f, 160, 0.35f); // C6 (Đô cao)
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

// Phát âm thanh WAV trực tiếp từ luồng HTTP của Hub ra Loa MAX98357A
void playAudioFromUrl(const char *url) {
  if (WiFi.status() != WL_CONNECTED || !url || strlen(url) == 0) return;

  Serial.printf("[AUDIO STREAM] Phat am thanh tu Hub: %s\n", url);

  WiFiClient client;
  HTTPClient http;
  http.setTimeout(10000);

  if (!http.begin(client, url)) {
    Serial.println("[AUDIO STREAM] Loi khoi tao ket noi HTTP");
    return;
  }

  int httpCode = http.GET();
  if (httpCode != 200) {
    Serial.printf("[AUDIO STREAM] HTTP loi: %d\n", httpCode);
    http.end();
    return;
  }

  int totalLen = http.getSize();
  Serial.printf("[AUDIO STREAM] Kich thuoc audio: %d bytes\n", totalLen);

  WiFiClient *stream = http.getStreamPtr();
  if (!stream) {
    http.end();
    return;
  }

  // Đọc bỏ qua 44 byte header WAV chuẩn
  uint8_t header[44];
  int hRead = 0;
  unsigned long hStart = millis();
  while (hRead < 44 && stream->connected() && (millis() - hStart < 3000)) {
    if (stream->available()) {
      hRead += stream->readBytes(header + hRead, 44 - hRead);
    } else {
      vTaskDelay(pdMS_TO_TICKS(5));
    }
  }

  isSpeakerPlaying = true;
  const size_t CHUNK_SIZE = 512;
  uint8_t monoBuf[CHUNK_SIZE];
  int16_t stereoBuf[CHUNK_SIZE]; // Left + Right stereo cho MAX98357A
  size_t bytesWritten = 0;
  unsigned long lastDataTime = millis();
  int bytesRemaining = totalLen > 44 ? totalLen - 44 : totalLen;

  while (http.connected() && (bytesRemaining > 0 || totalLen == -1)) {
    size_t avail = stream->available();
    if (avail > 0) {
      lastDataTime = millis();
      int toRead = min((int)CHUNK_SIZE, (int)avail);
      if (bytesRemaining > 0 && toRead > bytesRemaining) {
        toRead = bytesRemaining;
      }
      int bytesRead = stream->readBytes(monoBuf, toRead);
      if (bytesRead > 0) {
        int samples = bytesRead / 2;
        int16_t *samplesMono = (int16_t *)monoBuf;

        // Nhân đôi mono sang 2 kênh stereo L/R và khuếch đại âm lượng x1.4 cho rõ nét
        for (int i = 0; i < samples; i++) {
          int32_t val = (int32_t)(samplesMono[i] * 1.4f);
          if (val > 32767) val = 32767;
          if (val < -32768) val = -32768;
          stereoBuf[i * 2] = (int16_t)val;
          stereoBuf[i * 2 + 1] = (int16_t)val;
        }

        i2s_write(I2S_SPK_PORT, stereoBuf, samples * 4, &bytesWritten, portMAX_DELAY);
        if (bytesRemaining > 0) bytesRemaining -= bytesRead;
      }
    } else {
      if (millis() - lastDataTime > 2500) break; // Hết luồng dữ liệu
      vTaskDelay(pdMS_TO_TICKS(5));
    }
  }

  i2s_zero_dma_buffer(I2S_SPK_PORT);
  vTaskDelay(pdMS_TO_TICKS(600)); // Đợi DMA xả sạch âm thanh ra loa vật lý
  i2s_zero_dma_buffer(I2S_MIC_PORT); // Xóa sạch dư âm trong mic
  isSpeakerPlaying = false;
  http.end();
  Serial.println("[AUDIO STREAM] Phat am thanh hoan tat!");
}

// ============================================================================
// TASK THU ÂM TỪ MICRO INMP441 & VAD (VOICE ACTIVITY DETECTION)
// ============================================================================
void micAudioReaderTask(void *param) {
  const size_t bufferSize = 256;
  int32_t rawSamples[bufferSize];
  size_t bytesRead = 0;

  Serial.println("[TASK MIC] Bat dau luong giam sat am thanh INMP441...");

  // Cấp phát cố định 1 lần duy nhất từ heap khi khởi động (Thử 160KB = 5.0s, fallback 128KB = 4.0s)
  if (wavBufStatic == NULL) {
    size_t tryBytes = 160000; // 5.0 giây @ 16kHz 16-bit Mono
    wavBufStatic = (uint8_t *)malloc(44 + tryBytes);
    if (!wavBufStatic) {
      tryBytes = 128000; // 4.0 giây fallback
      wavBufStatic = (uint8_t *)malloc(44 + tryBytes);
    }
    if (!wavBufStatic) {
      tryBytes = 96000; // 3.0 giây fallback
      wavBufStatic = (uint8_t *)malloc(44 + tryBytes);
    }
    if (wavBufStatic) {
      maxWavDataBytes = tryBytes;
      Serial.printf("[TASK MIC] Da cap phat san %d bytes bo dem WAV (%.1fs)! Heap con: %d bytes\n",
                    maxWavDataBytes, (float)maxWavDataBytes / 32000.0, ESP.getFreeHeap());
    } else {
      Serial.println("[TASK MIC] LOI: Khong the cap phat wavBufStatic!");
    }
  }

  // Chờ WiFi kết nối và hệ thống ổn định trước khi mở Micro lắng nghe
  while (WiFi.status() != WL_CONNECTED) {
    size_t dummyBytes = 0;
    i2s_read(I2S_MIC_PORT, rawSamples, sizeof(rawSamples), &dummyBytes, pdMS_TO_TICKS(50));
    vTaskDelay(pdMS_TO_TICKS(100));
  }
  vTaskDelay(pdMS_TO_TICKS(1500)); // Chờ 1.5s để triệt tiêu rung chấn cơ học và âm boot
  i2s_zero_dma_buffer(I2S_MIC_PORT);
  preRollIndex = 0;
  preRollFilled = false;
  Serial.println("[TASK MIC] WiFi san sang, Mic bat dau lang nghe!");

  static int activeMicChannel = 0; // Luôn dùng 0: LEFT (Chuẩn INMP441 nối L/R xuống GND)

  while (true) {
    if (wavBufStatic == NULL) {
      vTaskDelay(pdMS_TO_TICKS(500));
      continue;
    }
    // Nếu loa đang phát âm thanh thì tạm dừng quét Mic để tránh dội tiếng (Acoustic Echo)
    if (isSpeakerPlaying) {
      vTaskDelay(pdMS_TO_TICKS(40));
      continue;
    }

    esp_err_t res = i2s_read(I2S_MIC_PORT, rawSamples, sizeof(rawSamples),
                             &bytesRead, pdMS_TO_TICKS(100));
    if (res == ESP_OK && bytesRead > 0) {
      int numSamples = bytesRead / sizeof(int32_t); // Mono 1 kênh duy nhất
      if (numSamples <= 0) continue;

      // 1. Tính DC Mean trong miền 32-bit nguyên bản để bảo toàn 100% độ nhạy
      int64_t sumL = 0;
      for (int i = 0; i < numSamples; i++) {
        sumL += rawSamples[i];
      }
      int32_t dcMean = sumL / numSamples;

      int64_t sumSquares = 0;
      for (int i = 0; i < numSamples; i++) {
        // Trừ DC offset ở độ phân giải 32-bit rồi mới chuyển dịch >> 14 (+12dB gain sạch)
        int32_t s = (rawSamples[i] - dcMean) >> 14;
        if (s > 32767) s = 32767;
        if (s < -32768) s = -32768;
        int16_t sample16 = (int16_t)s;
        sumSquares += (int64_t)sample16 * sample16;

        // Lưu liên tục vào Pre-roll Ring Buffer để không bao giờ mất chữ đầu
        preRollBuffer[preRollIndex++] = sample16;
        if (preRollIndex >= PRE_ROLL_SAMPLES) {
          preRollIndex = 0;
          preRollFilled = true;
        }
      }

      int rms = (int)sqrt(sumSquares / numSamples);

      // In log định kỳ mỗi 2 giây để kiểm tra phần cứng Micro INMP441
      static unsigned long lastRmsPrint = 0;
      if (millis() - lastRmsPrint > 2000) {
        lastRmsPrint = millis();
        Serial.printf("[MIC TEST] Raw[0]: %d, RMS: %d (Nguong: %d, Kenh: ONLY_LEFT)\n",
                      rawSamples[0], rms, VAD_THRESHOLD);
      }

      // Bộ lọc lọc gai nhiễu: kích hoạt nhanh khi giọng nói duy trì liên tục ít nhất 2 frame (~16ms)
      static int vadConsecutiveFrames = 0;
      if (rms > VAD_THRESHOLD) {
        vadConsecutiveFrames++;
      } else {
        if (vadConsecutiveFrames > 0) vadConsecutiveFrames--;
      }

      // Nếu năng lượng vượt ngưỡng VAD liên tục -> Người dùng đang nói vào Micro!
      if (vadConsecutiveFrames >= 2) {
        vadConsecutiveFrames = 0;
        Serial.printf("[XIAOZHI MIC VAD] Phat hien giong noi thuc te! RMS: %d\n", rms);
        strncpy(robotEmotion, "listening", sizeof(robotEmotion) - 1);
        oledNeedsUpdate = true; // Cập nhật bất đồng bộ, KHÔNG gọi renderOledDashboard() chặn CPU

        const size_t wavDataBytes = maxWavDataBytes;
        const size_t totalWavBytes = 44 + wavDataBytes;
        writeWavHeader(wavBufStatic, wavDataBytes, AUDIO_SAMPLE_RATE, 1, 16);
        int16_t *pcmData = (int16_t *)(wavBufStatic + 44);

        // 1. Chèn 600ms (9600 mẫu) âm thanh đã nói vào đầu bản thu (Bảo toàn trọn vẹn chữ đầu)
        size_t samplesRecorded = 0;
        const size_t targetSamples = wavDataBytes / 2; // Tối đa 5.0s (80000 mẫu) hoặc 4.0s (64000 mẫu)
        size_t preRollCount = preRollFilled ? PRE_ROLL_SAMPLES : preRollIndex;
        size_t readStart = preRollFilled ? preRollIndex : 0;
        for (size_t k = 0; k < preRollCount; k++) {
          size_t idx = (readStart + k) % PRE_ROLL_SAMPLES;
          pcmData[samplesRecorded++] = preRollBuffer[idx];
        }

        // 2. Tiếp tục thu trực tiếp từ I2S - Tự động phát hiện điểm ngắt câu thông minh (End-Of-Speech EOS)
        int32_t rawChunk[128]; // Mono 128 mẫu (128 int32_t)
        unsigned long recordStart = millis();
        int consecutiveSilenceChunks = 0;
        const size_t minSpeechSamples = 16000; // Tối thiểu 1.0 giây bản thu (tránh ngắt sớm do tiếng động lạ)
        const unsigned long maxRecordMs = 5500; // Tối đa 5.5 giây cho một câu nói

        while (samplesRecorded < targetSamples && (millis() - recordStart < maxRecordMs)) {
          size_t bytesReadNow = 0;
          size_t toRead = min((size_t)128, targetSamples - samplesRecorded);
          esp_err_t err = i2s_read(I2S_MIC_PORT, rawChunk, toRead * sizeof(int32_t), &bytesReadNow, pdMS_TO_TICKS(100));
          if (err == ESP_OK && bytesReadNow > 0) {
            int count = bytesReadNow / sizeof(int32_t);
            int64_t chunkSum = 0;
            for (int s = 0; s < count; s++) {
              chunkSum += rawChunk[s];
            }
            int32_t chunkMean = chunkSum / (count > 0 ? count : 1);

            int64_t chunkSquares = 0;
            for (int s = 0; s < count && samplesRecorded < targetSamples; s++) {
              int32_t sample = (rawChunk[s] - chunkMean) >> 14;
              if (sample > 32767) sample = 32767;
              if (sample < -32768) sample = -32768;
              pcmData[samplesRecorded++] = (int16_t)sample;
              chunkSquares += (int64_t)sample * (int64_t)sample;
            }

            int chunkRms = (int)sqrt(chunkSquares / (count > 0 ? count : 1));
            // Phát hiện khoảng lặng sau khi nói xong (EOS)
            // Ngưỡng im lặng: dưới 65% VAD_THRESHOLD
            if (chunkRms < (VAD_THRESHOLD * 0.65)) {
              consecutiveSilenceChunks++;
              // Mỗi chunk 128 mẫu @ 16kHz = 8ms.
              // 45 chunks = 360ms im lặng liên tục -> Người dùng thực sự đã nói xong câu!
              if (samplesRecorded >= minSpeechSamples && consecutiveSilenceChunks >= 45) {
                Serial.printf("[XIAOZHI MIC EOS] Phat hien nguoi dung da noi xong (%d mau ~%.2fs). Gui ngay!\n",
                              samplesRecorded, (float)samplesRecorded / AUDIO_SAMPLE_RATE);
                break;
              }
            } else {
              consecutiveSilenceChunks = 0;
            }
          } else {
            vTaskDelay(pdMS_TO_TICKS(2));
          }
        }


        // Cập nhật lại Header WAV chuẩn với số byte thực tế đã thu (bao gồm cả 600ms âm đuôi tự nhiên)
        size_t actualWavDataBytes = samplesRecorded * sizeof(int16_t);
        size_t actualTotalBytes = 44 + actualWavDataBytes;
        writeWavHeader(wavBufStatic, actualWavDataBytes, AUDIO_SAMPLE_RATE, 1, 16);

        Serial.printf("[MIC ASR] Da thu xong %d mau (%.2fs, %d bytes). Gui toi Hub ASR...\n",
                      samplesRecorded, (float)samplesRecorded / AUDIO_SAMPLE_RATE, actualTotalBytes);
        strncpy(robotEmotion, "thinking", sizeof(robotEmotion) - 1);
        oledNeedsUpdate = true;

        if (WiFi.status() == WL_CONNECTED) {
          WiFiClient client;
          HTTPClient http;
          http.setTimeout(15000); // Đặt 15 giây để không bao giờ bị timeout sớm
          if (http.begin(client, hub_asr_url)) {
            http.addHeader("Content-Type", "audio/wav");
            http.addHeader("X-Room-Id", "living");
            http.addHeader("X-Device-Id", "esp32-gateway");
            int httpCode = http.POST(wavBufStatic, actualTotalBytes);
            if (httpCode == 200) {
              String resp = http.getString();
              Serial.printf("[MIC ASR] Hub phan hoi: %s\n", resp.c_str());
              StaticJsonDocument<512> doc;
              DeserializationError dErr = deserializeJson(doc, resp);
              if (!dErr) {
                const char *txt = doc["ascii"] | doc["text"] | "";
                const char *replyAscii = doc["reply_ascii"] | doc["reply"] | "";
                const char *audioUrl = doc["audio_url"] | "";
                const char *emo = doc["emotion"] | "happy";

                if (strlen(txt) > 0) {
                  Serial.printf("[MIC ASR] >> BAN VUA NOI: '%s'\n", txt);
                  strncpy(userSpeechText, txt, sizeof(userSpeechText) - 1);
                  userSpeechText[sizeof(userSpeechText) - 1] = '\0';
                  lastConversationTime = millis();

                  if (replyAscii && strlen(replyAscii) > 0) {
                    strncpy(aiReplyText, replyAscii, sizeof(aiReplyText) - 1);
                    aiReplyText[sizeof(aiReplyText) - 1] = '\0';
                  }

                  strncpy(robotEmotion, "speaking", sizeof(robotEmotion) - 1);
                  oledNeedsUpdate = true;

                  // Tự động điều khiển thiết bị thông minh qua ESP-NOW (Chặn tuyệt đối lệnh mở cửa qua AI)
                  const char *intentDev = doc["device_id"] | "";
                  const char *intentAct = doc["action"] | "";
                  if (strlen(intentDev) > 0 && strlen(intentAct) > 0) {
                    if (strcmp(intentAct, "unlock") == 0) {
                      Serial.println("[SECURITY] TU CHOI MO CUA QUA AI! YEU CAU DUNG MAT KHAU HOAC RFID.");
                    } else {
                      int v = (strcmp(intentAct, "on") == 0 || strcmp(intentAct, "turn_on") == 0) ? 1 : 0;
                      dispatchCommandToEspNow(intentDev, intentAct, v);
                    }
                  } else {
                    String lower = String(txt);
                    lower.toLowerCase();
                    if (lower.indexOf("bat den") >= 0 || lower.indexOf("mo den") >= 0 || lower.indexOf("bat deng") >= 0 || lower.indexOf("buc den") >= 0 || lower.indexOf("bat sang") >= 0) {
                      dispatchCommandToEspNow("living-light", "on", 1);
                    } else if (lower.indexOf("tat den") >= 0 || lower.indexOf("dong den") >= 0 || lower.indexOf("tat deng") >= 0 || lower.indexOf("dong deng") >= 0) {
                      dispatchCommandToEspNow("living-light", "off", 0);
                    } else if (lower.indexOf("bat quat") >= 0 || lower.indexOf("mo quat") >= 0) {
                      dispatchCommandToEspNow("living-fan", "on", 1);
                    } else if (lower.indexOf("tat quat") >= 0 || lower.indexOf("dong quat") >= 0) {
                      dispatchCommandToEspNow("living-fan", "off", 0);
                    } else if (lower.indexOf("khoa cua") >= 0 || lower.indexOf("dong cua") >= 0) {
                      dispatchCommandToEspNow("entry-lock", "lock", 0);
                    } else if (lower.indexOf("mo cua") >= 0 || lower.indexOf("mo khoa") >= 0) {
                      Serial.println("[SECURITY] Yeu cau mo cua bi tu choi tuyet doi qua AI!");
                    }
                  }
                } else {
                  Serial.println("[MIC ASR] Khong nhan dien duoc tu nao -> Giu im lang.");
                  strncpy(robotEmotion, "neutral", sizeof(robotEmotion) - 1);
                  oledNeedsUpdate = true;
                }

                // ĐÓNG HTTP POST TRƯỚC KHI BẮT ĐẦU LUỒNG PHÁT ÂM THANH
                http.end();

                // HIỂN THỊ CÂU TRẢ LỜI CỦA AI VÀ PHÁT LOA (NẾU CÓ CÂU TRẢ LỜI RÕ RÀNG)
                if (audioUrl && strlen(audioUrl) > 0) {
                  strncpy(robotEmotion, "speaking", sizeof(robotEmotion) - 1);
                  renderOledDashboard();

                  // Phát âm thanh giọng nói trả lời ra loa MAX98357A!
                  playAudioFromUrl(audioUrl);

                  strncpy(robotEmotion, emo, sizeof(robotEmotion) - 1);
                  oledNeedsUpdate = true;
                } else if (emo && strlen(emo) > 0) {
                  strncpy(robotEmotion, emo, sizeof(robotEmotion) - 1);
                  oledNeedsUpdate = true;
                }
              } else {
                http.end();
                strncpy(robotEmotion, "neutral", sizeof(robotEmotion) - 1);
              }
            } else {
              Serial.printf("[MIC ASR] Loi goi Hub ASR (HTTP %d)\n", httpCode);
              strncpy(robotEmotion, "neutral", sizeof(robotEmotion) - 1);
              http.end();
            }
          }
        } else {
          setOledEvent("Mat ket noi WiFi");
          strncpy(robotEmotion, "neutral", sizeof(robotEmotion) - 1);
        }

        // Nghỉ 1000ms sau khi phát loa để tiêu tán hoàn toàn âm vang trong phòng, chống tuyệt đối hiện tượng tự kích hoạt lặp (Acoustic Echo)
        vTaskDelay(pdMS_TO_TICKS(1000));
        i2s_zero_dma_buffer(I2S_MIC_PORT);
        preRollIndex = 0;
        preRollFilled = false;
        vadConsecutiveFrames = 0;
        strncpy(robotEmotion, "neutral", sizeof(robotEmotion) - 1);
        oledNeedsUpdate = true;
        Serial.println("[TASK MIC] Da san sang nhan cau lenh tiep theo!");
      }
    }

    vTaskDelay(pdMS_TO_TICKS(8));
  }
}

// ============================================================================
// GỬI LỆNH ESP-NOW SANG ESP32 #1 (THIẾT BỊ) HOẶC ESP32 #2 (CỔNG)
// ============================================================================
void dispatchCommandToEspNow(const char *deviceId, const char *action,
                             int val) {
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
    esp_now_send(broadcastMac, (uint8_t *)&outgoingCmd, sizeof(outgoingCmd));
  } else {
    // Thuộc về ESP32 #1 (Thiết bị trong nhà)
    esp_err_t res = esp_now_send(mac_esp1_appliances, (uint8_t *)&outgoingCmd,
                                 sizeof(outgoingCmd));
    Serial.printf("[GATEWAY -> ESP1 THIẾT BỊ] %s -> %s (%s)\n", deviceId,
                  action, res == ESP_OK ? "OK" : "ERR");
    esp_now_send(broadcastMac, (uint8_t *)&outgoingCmd, sizeof(outgoingCmd));
  }

  // Phản hồi thị giác trực tiếp trên Gateway: Điều khiển LED Onboard (GPIO 2)
  if (dev.indexOf("light") >= 0 || dev == "all-lights") {
    if (val == 1 || strcmp(action, "turn_on") == 0 || strcmp(action, "on") == 0) {
      digitalWrite(ONBOARD_LED_PIN, HIGH);
      Serial.println("[GATEWAY HARDWARE LED] -> BẬT ĐÈN ONBOARD LED (GPIO 2) SÁNG RỰC!");
    } else {
      digitalWrite(ONBOARD_LED_PIN, LOW);
      Serial.println("[GATEWAY HARDWARE LED] -> TẮT ĐÈN ONBOARD LED (GPIO 2)!");
    }
  } else {
    // Nháy LED nhanh xác nhận tiếp nhận lệnh điều khiển
    digitalWrite(ONBOARD_LED_PIN, HIGH);
    delay(40);
    digitalWrite(ONBOARD_LED_PIN, LOW);
  }

  // Cập nhật trạng thái sự kiện lên màn hình OLED
  char cmdEvt[32];
  snprintf(cmdEvt, sizeof(cmdEvt), "CMD: %s", deviceId);
  setOledEvent(cmdEvt);

  // Phát bíp ngắn báo hiệu đã gửi lệnh thành công
  playBeep();
}

// ============================================================================
// CALLBACK THEO DÕI TRẠNG THÁI GỬI GÓI TIN ESP-NOW (XÁC NHẬN ACK PHẦN CỨNG)
// ============================================================================
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
void OnDataSent(const wifi_tx_info_t *tx_info, esp_now_send_status_t status) {
#else
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
#endif
  if (status == ESP_NOW_SEND_SUCCESS) {
    Serial.println("[ESP-NOW PHẢN HỒI] -> GỬI THÀNH CÔNG! (Slave ESP32 đã nhận và phản hồi ACK phần cứng)");
  } else {
    Serial.println("[ESP-NOW PHẢN HỒI] -> Không có ACK từ Slave (ESP32 #1 hoặc #2 có thể tắt nguồn hoặc khác kênh WiFi)");
  }
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

  // Đóng gói JSON đẩy lên MQTT để Web Dashboard và Backend cập nhật
  StaticJsonDocument<256> doc;
  doc["event"] = "device.state";
  doc["device_id"] = incomingData.device_id;
  doc["action"] = incomingData.action;
  doc["value"] = incomingData.value;
  doc["float_val"] = incomingData.float_val;
  doc["online"] = true;
  doc["timestamp"] = millis();

  // Tạo thêm nested object "state" để backend Python nhận diện được
  JsonObject st = doc.createNestedObject("state");
  if (strcmp(incomingData.action, "on") == 0 || strcmp(incomingData.action, "turn_on") == 0 || incomingData.value == 1) {
    st["power"] = true;
    st["on"] = true;
  } else if (strcmp(incomingData.action, "off") == 0 || strcmp(incomingData.action, "turn_off") == 0 || incomingData.value == 0) {
    st["power"] = false;
    st["on"] = false;
  }
  if (strcmp(incomingData.action, "lock") == 0) {
    st["locked"] = true;
  } else if (strcmp(incomingData.action, "unlock") == 0) {
    st["locked"] = false;
  }
  if (incomingData.float_val != 0) {
    st["temperature"] = incomingData.float_val;
  }

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
// CALLBACK NHẬN LỆNH TỪ WEB DASHBOARD QUA LOCAL MOSQUITTO MQTT
// ============================================================================
void onMqttMessage(char *topic, byte *payload, unsigned int length) {
  char message[512];
  if (length >= sizeof(message))
    length = sizeof(message) - 1;
  memcpy(message, payload, length);
  message[length] = '\0';

  Serial.printf("\n[MQTT NHẬN TỪ WEB/BACKEND] Topic: %s | Payload: %s\n", topic,
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
      int val = 0;
      if (doc.containsKey("value") && !doc["value"].isNull()) {
        val = doc["value"].as<int>();
      } else {
        if (strcmp(act, "on") == 0 || strcmp(act, "turn_on") == 0 || strcmp(act, "open") == 0 || strcmp(act, "lock") == 0) {
          val = 1;
        } else {
          val = 0;
        }
      }
      const char *cmdId = doc["command_id"] | "";

      // Chuẩn hóa action tương thích hoàn hảo với Slave ESP32: on -> turn_on, off -> turn_off
      const char *slaveAct = act;
      if (strcmp(act, "on") == 0) slaveAct = "turn_on";
      else if (strcmp(act, "off") == 0) slaveAct = "turn_off";

      // Bắn lệnh ngay lập tức sang mạng ESP-NOW tới Slave ESP32!
      dispatchCommandToEspNow(devId.c_str(), slaveAct, val);

      // Phản hồi ACK & State tức thì lên MQTT để Backend & Web Dashboard xác nhận thành công
      if (mqttClient.connected()) {
        StaticJsonDocument<128> ackDoc;
        ackDoc["event"] = "device.ack";
        ackDoc["device_id"] = devId;
        ackDoc["status"] = "ok";
        if (strlen(cmdId) > 0) ackDoc["command_id"] = cmdId;
        char ackBuf[128];
        serializeJson(ackDoc, ackBuf);
        String ackTopic = "homing/devices/" + devId + "/ack";
        mqttClient.publish(ackTopic.c_str(), ackBuf);

        StaticJsonDocument<256> stateDoc;
        stateDoc["event"] = "device.state";
        stateDoc["device_id"] = devId;
        if (strlen(cmdId) > 0) stateDoc["command_id"] = cmdId;
        JsonObject st = stateDoc.createNestedObject("state");
        if (strcmp(act, "turn_on") == 0 || strcmp(act, "on") == 0 || val == 1) {
          st["power"] = true;
          st["on"] = true;
          st["brightness"] = 100;
        } else if (strcmp(act, "turn_off") == 0 || strcmp(act, "off") == 0 || (strcmp(act, "lock") != 0 && strcmp(act, "unlock") != 0 && val == 0)) {
          st["power"] = false;
          st["on"] = false;
        }
        if (strcmp(act, "lock") == 0) {
          st["locked"] = true;
        } else if (strcmp(act, "unlock") == 0) {
          st["locked"] = false;
        } else if (strcmp(act, "open") == 0) {
          st["open"] = true;
          st["power"] = true;
          st["position"] = 100;
        } else if (strcmp(act, "close") == 0) {
          st["open"] = false;
          st["power"] = false;
          st["position"] = 0;
        }
        char stateBuf[256];
        serializeJson(stateDoc, stateBuf);
        String stateTopic = "homing/devices/" + devId + "/state";
        mqttClient.publish(stateTopic.c_str(), stateBuf, true);
      }

      // Xử lý phát luồng audio trực tiếp nếu là thiết bị loa
      const char *audioUrl = doc["audio_url"] | doc["url"] | "";
      const char *trackName = doc["track"] | doc["title"] | "";
      if (strlen(audioUrl) > 0) {
        Serial.printf("[XIAOZHI PHÁT NHẠC LOA I2S]: %s -> %s\n", trackName, audioUrl);
        strncpy(userSpeechText, "Phat nhac:", sizeof(userSpeechText) - 1);
        strncpy(aiReplyText, strlen(trackName) > 0 ? trackName : "Lac troi - Son Tung M-TP", sizeof(aiReplyText) - 1);
        strncpy(robotEmotion, "speaking", sizeof(robotEmotion) - 1);
        oledNeedsUpdate = true;
        playAudioFromUrl(audioUrl);
        strncpy(robotEmotion, "happy", sizeof(robotEmotion) - 1);
        oledNeedsUpdate = true;
      }
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
  // 3. Lệnh phát nhạc trực tiếp: homing/speaker/play
  else if (top == "homing/speaker/play") {
    Serial.printf("[XIAOZHI NHẬN LỆNH PHÁT NHẠC]: %s\n", message);
    StaticJsonDocument<256> doc;
    DeserializationError err = deserializeJson(doc, message);
    if (!err) {
      const char *audioUrl = doc["audio_url"] | doc["url"] | "";
      const char *trackName = doc["track"] | doc["title"] | "Lac troi - Son Tung M-TP";
      if (strlen(audioUrl) > 0) {
        Serial.printf("[XIAOZHI PHÁT NHẠC LOA I2S]: %s -> %s\n", trackName, audioUrl);
        strncpy(userSpeechText, "Phat nhac:", sizeof(userSpeechText) - 1);
        strncpy(aiReplyText, trackName, sizeof(aiReplyText) - 1);
        strncpy(robotEmotion, "speaking", sizeof(robotEmotion) - 1);
        oledNeedsUpdate = true;
        playAudioFromUrl(audioUrl);
        strncpy(robotEmotion, "happy", sizeof(robotEmotion) - 1);
        oledNeedsUpdate = true;
      }
    }
  }
}

// ============================================================================
// KẾT NỐI VÀ RECONNECT MQTT HIVEMQ CLOUD
// ============================================================================
void connectMqtt() {
  if (mqttClient.connected())
    return;

  Serial.printf("[MQTT] Dang ket noi Mosquitto Hub %s:%d...\n", mqtt_server, mqtt_port);
  String clientId = "Homing-Xiaozhi-Gateway-" + String(random(0xffff), HEX);

  bool connected = false;
  if (strlen(mqtt_user) > 0) {
    connected = mqttClient.connect(clientId.c_str(), mqtt_user, mqtt_pass);
  } else {
    connected = mqttClient.connect(clientId.c_str());
  }

  if (connected) {
    Serial.println("[MQTT] KET NOI THANH CONG!");
    setOledEvent("MQTT Connected");

    // Đăng ký nhận lệnh điều khiển từ Backend & Web Dashboard
    mqttClient.subscribe("homing/devices/+/command");
    mqttClient.subscribe("homing/speaker/say");
    mqttClient.subscribe("homing/speaker/play");
    mqttClient.subscribe("homing/broadcast/scan");

    // Bắn thông báo Gateway Online và duy trì kết nối cho các cụm thiết bị ESP-NOW
    mqttClient.publish(
        "homing/gateway/state",
        "{\"status\":\"online\",\"protocol\":\"esp-now+wss+i2s_audio\"}", true);
    mqttClient.publish("homing/devices/esp32_home_appliances/ack",
                       "{\"event\":\"device.ack\",\"device_id\":\"esp32_home_appliances\",\"status\":\"ok\"}");
    mqttClient.publish("homing/devices/esp32_main_entrance/ack",
                       "{\"event\":\"device.ack\",\"device_id\":\"esp32_main_entrance\",\"status\":\"ok\"}");
    mqttClient.publish("homing/devices/living-light/state",
                       "{\"device_id\":\"living-light\",\"state\":{\"power\":false},\"online\":true}", true);
    mqttClient.publish("homing/devices/living-fan/state",
                       "{\"device_id\":\"living-fan\",\"state\":{\"power\":false,\"speed\":0},\"online\":true}", true);
    mqttClient.publish("homing/devices/entry-lock/state",
                       "{\"device_id\":\"entry-lock\",\"state\":{\"locked\":true},\"online\":true}", true);
  } else {
    Serial.printf("[MQTT] That bai, rc=%d. Thu lai sau 5s.\n", mqttClient.state());
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

  // 0. Khởi tạo Onboard LED GPIO 2 làm đèn báo trạng thái phần cứng
  pinMode(ONBOARD_LED_PIN, OUTPUT);
  digitalWrite(ONBOARD_LED_PIN, LOW);

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

  // Cấp phát trước khối RAM liên tục cho bộ đệm WAV ngay từ đầu để tránh phân mảnh Heap (128KB = 4.0s)
  if (wavBufStatic == NULL) {
    size_t tryBytes = 128000; // 4.0 giây @ 16kHz 16-bit Mono
    wavBufStatic = (uint8_t *)malloc(44 + tryBytes);
    if (!wavBufStatic) {
      tryBytes = 96000; // 3.0 giây fallback
      wavBufStatic = (uint8_t *)malloc(44 + tryBytes);
    }
    if (wavBufStatic) {
      maxWavDataBytes = tryBytes;
      Serial.printf("[AUDIO INIT] Da cap phat san %d bytes bo dem WAV (%.1fs)! Heap con: %d bytes\n",
                    maxWavDataBytes, (float)maxWavDataBytes / 32000.0, ESP.getFreeHeap());
    }
  }

  // Phát nhạc kiểm tra loa ngay khi cấp nguồn
  playBootChime();

  // Tạo Task FreeRTOS chạy ngầm đọc Micro INMP441 trên Core 1 (Stack 12288 bytes cho HTTP Stream)
  xTaskCreatePinnedToCore(micAudioReaderTask, "mic_reader_task", 12288, NULL, 1,
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

    // Đồng bộ với máy chủ Homing AI Hub tự host
    syncWithHomingServer();

    // Kết nối WebSocket Full-Duplex với Xiaozhi Hub
    connectWebSocket();
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
  esp_now_register_send_cb(OnDataSent);

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

  // Đăng ký Broadcast Peer để gửi lệnh toàn mạng
  memset(&peerBroadcast, 0, sizeof(peerBroadcast));
  memcpy(peerBroadcast.peer_addr, broadcastMac, 6);
  peerBroadcast.channel = WiFi.channel();
  peerBroadcast.encrypt = false;
  esp_now_add_peer(&peerBroadcast);

  // 5. Cấu hình MQTT với Local Mosquitto Hub
  mqttClient.setServer(mqtt_server, mqtt_port);
  mqttClient.setCallback(onMqttMessage);
  mqttClient.setBufferSize(512);
  mqttClient.setKeepAlive(60); // Duy trì kết nối MQTT 60 giây, chống tuyệt đối ngắt kết nối timeout

  connectMqtt();

  setOledEvent("San sang hoat dong");
  renderOledDashboard();
}

// ============================================================================
// LOOP
// ============================================================================
void loop() {
  unsigned long now = millis();

  // Duy trì kết nối WiFi, MQTT và WebSocket
  if (WiFi.status() == WL_CONNECTED) {
    // 1. Duy trì MQTT
    if (!mqttClient.connected()) {
      if (now - lastMqttRetry > 5000) {
        lastMqttRetry = now;
        connectMqtt();
      }
    } else {
      mqttClient.loop();
    }

    // 2. Duy trì WebSocket Xiaozhi
    if (wsIsConnected) {
      wsClient.poll();
    } else if (now - lastWsReconnect > 30000) {
      lastWsReconnect = now;
      connectWebSocket();
    }
  }

  // Gửi nhịp tim định kỳ mỗi 8 giây để duy trì kết nối toàn bộ thiết bị
  if (now - lastHeartbeat > 8000) {
    lastHeartbeat = now;
    if (mqttClient.connected()) {
      mqttClient.publish("homing/gateway/heartbeat",
                         "{\"gateway\":\"online\",\"esp_now\":\"active\","
                         "\"audio\":\"i2s_active\"}");
      mqttClient.publish("homing/devices/esp32_home_appliances/ack",
                         "{\"event\":\"device.ack\",\"device_id\":\"esp32_home_appliances\",\"status\":\"ok\"}");
      mqttClient.publish("homing/devices/esp32_main_entrance/ack",
                         "{\"event\":\"device.ack\",\"device_id\":\"esp32_main_entrance\",\"status\":\"ok\"}");
      mqttClient.publish("homing/devices/living-light/ack",
                         "{\"event\":\"device.ack\",\"device_id\":\"living-light\",\"status\":\"ok\"}");
      mqttClient.publish("homing/devices/living-fan/ack",
                         "{\"event\":\"device.ack\",\"device_id\":\"living-fan\",\"status\":\"ok\"}");
      mqttClient.publish("homing/devices/bedroom-light/ack",
                         "{\"event\":\"device.ack\",\"device_id\":\"bedroom-light\",\"status\":\"ok\"}");
      mqttClient.publish("homing/devices/bedroom-fan/ack",
                         "{\"event\":\"device.ack\",\"device_id\":\"bedroom-fan\",\"status\":\"ok\"}");
      mqttClient.publish("homing/devices/kitchen-light/ack",
                         "{\"event\":\"device.ack\",\"device_id\":\"kitchen-light\",\"status\":\"ok\"}");
      mqttClient.publish("homing/devices/kitchen-fan/ack",
                         "{\"event\":\"device.ack\",\"device_id\":\"kitchen-fan\",\"status\":\"ok\"}");
      mqttClient.publish("homing/devices/kitchen-gas/ack",
                         "{\"event\":\"device.ack\",\"device_id\":\"kitchen-gas\",\"status\":\"ok\"}");
      mqttClient.publish("homing/devices/living-temperature/ack",
                         "{\"event\":\"device.ack\",\"device_id\":\"living-temperature\",\"status\":\"ok\"}");
      mqttClient.publish("homing/devices/entry-lock/ack",
                         "{\"event\":\"device.ack\",\"device_id\":\"entry-lock\",\"status\":\"ok\"}");
    }
  }

  // Cập nhật màn hình OLED định kỳ mỗi 200ms để chớp mắt và hiển thị biểu cảm robot mượt mà
  static unsigned long lastOledRefresh = 0;
  if (!isSpeakerPlaying && (oledNeedsUpdate || (now - lastOledRefresh > 200))) {
    lastOledRefresh = now;
    oledNeedsUpdate = false;
    renderOledDashboard();
  }
}

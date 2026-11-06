#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <HTTPClient.h>
#include <MFRC522.h>
#include <U8g2lib.h>

// ESP32 + RC522 + SSD1306 wiring (same pin map as the original sketch).
#define RFID_SS_PIN   5
#define RFID_RST_PIN  13
#define RFID_SCK_PIN  18
#define RFID_MISO_PIN 19
#define RFID_MOSI_PIN 23
#define BUZZER_PIN    14
#define LED_PIN       27
#define OLED_SDA_PIN  21
#define OLED_SCL_PIN  22
#define OLED_ADDR     0x3C

// For local testing, the computer and ESP32 must be on the same Wi-Fi.
const char *WIFI_SSID = "YOUR_WIFI_NAME";
const char *WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char *API_URL = "http://192.168.1.22:5000/attendance-payroll/api/rfid/scan";
const char *DEVICE_TOKEN = "PASTE_THE_SAME_RFID_DEVICE_TOKEN_FROM_SERVER_ENV";

MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);
U8G2_SSD1306_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE);
String lastUid = "-";
String statusText = "Connecting WiFi";
unsigned long lastWifiAttempt = 0;

String uidToString(const MFRC522::Uid &uid) {
  String out;
  for (byte i = 0; i < uid.size; ++i) {
    if (i) out += ":";
    if (uid.uidByte[i] < 0x10) out += "0";
    out += String(uid.uidByte[i], HEX);
  }
  out.toUpperCase();
  return out;
}

void showStatus(const String &message) {
  statusText = message;
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x12_tr);
  u8g2.drawStr(0, 12, "RFID Attendance");
  u8g2.drawHLine(0, 14, 128);
  u8g2.drawStr(0, 30, "Status:");
  u8g2.drawStr(0, 44, statusText.substring(0, 21).c_str());
  u8g2.drawStr(0, 60, (String("UID: ") + lastUid).substring(0, 21).c_str());
  u8g2.sendBuffer();
}

void feedback(bool success) {
  const int count = success ? 3 : 1;
  for (int i = 0; i < count; ++i) {
    digitalWrite(LED_PIN, HIGH);
    digitalWrite(BUZZER_PIN, HIGH);
    delay(success ? 120 : 500);
    digitalWrite(LED_PIN, LOW);
    digitalWrite(BUZZER_PIN, LOW);
    delay(100);
  }
  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
}

bool connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  if (millis() - lastWifiAttempt < 10000) return false;
  lastWifiAttempt = millis();
  showStatus("Connecting WiFi");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  const unsigned long started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 12000) delay(250);
  if (WiFi.status() == WL_CONNECTED) showStatus("Ready - scan card");
  else showStatus("WiFi unavailable");
  return WiFi.status() == WL_CONNECTED;
}

bool sendScan(const String &uid) {
  if (!connectWiFi()) return false;
  // Flask's local development server at 192.168.1.22:5000 uses HTTP.
  WiFiClient client;
  HTTPClient http;
  if (!http.begin(client, API_URL)) {
    showStatus("Server unavailable");
    return false;
  }
  http.setTimeout(8000);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Token", DEVICE_TOKEN);
  const String body = String("{\"uid\":\"") + uid + "\"}";
  const int code = http.POST(body);
  String response = code > 0 ? http.getString() : "";
  http.end();

  if (code >= 200 && code < 300 && response.indexOf("\"ok\":true") >= 0) {
    const String action = response.indexOf("CLOCK_OUT") >= 0 ? "Clocked out" : "Clocked in";
    showStatus(action);
    return true;
  }
  if (code == 401) showStatus("Device token invalid");
  else if (code == 404) showStatus("Card not registered");
  else if (code == 403) showStatus("Card access denied");
  else if (code < 0) showStatus("Server connection error");
  else showStatus("Attendance save failed");
  Serial.printf("Scan API HTTP %d: %s\n", code, response.c_str());
  return false;
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  Serial.begin(115200);

  Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN);
  u8g2.setI2CAddress(OLED_ADDR << 1);
  u8g2.begin();
  showStatus("Starting");

  SPI.begin(RFID_SCK_PIN, RFID_MISO_PIN, RFID_MOSI_PIN, RFID_SS_PIN);
  rfid.PCD_Init();
  connectWiFi();
  Serial.println("RFID attendance scanner ready");
}

void loop() {
  connectWiFi();
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    delay(20);
    return;
  }

  lastUid = uidToString(rfid.uid);
  Serial.print("UID: ");
  Serial.println(lastUid);
  showStatus("Sending scan...");
  const bool success = sendScan(lastUid);
  feedback(success);

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  // Require card removal to avoid repeated clock-in/out from one presentation.
  while (rfid.PICC_IsNewCardPresent()) delay(50);
  delay(300);
}

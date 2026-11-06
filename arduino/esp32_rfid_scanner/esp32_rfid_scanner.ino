#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
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

const char *WIFI_SSID = "YOUR_WIFI_NAME";
const char *WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char *API_URL = "https://resort-management-website.vercel.app/attendance-payroll/api/rfid/scan";
const char *DEVICE_TOKEN = "PASTE_THE_SAME_RFID_DEVICE_TOKEN_FROM_SERVER_ENV";

MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);
U8G2_SSD1306_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE);
String lastUid = "-";
String statusText = "Connecting WiFi";
bool wifiStarted = false;
bool wifiWasConnected = false;
unsigned long lastWifiStatusLog = 0;

void onWiFiEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
  if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) {
    Serial.printf(
        "WiFi disconnect reason: %u\n",
        (unsigned int)info.wifi_sta_disconnected.reason);
  } else if (event == ARDUINO_EVENT_WIFI_STA_GOT_IP) {
    Serial.print("WiFi obtained IP: ");
    Serial.println(WiFi.localIP());
  }
}

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
  u8g2.setFont(u8g2_font_5x8_tr);
  u8g2.drawStr(0, 8, "RFID Attendance");
  u8g2.drawHLine(0, 11, 128);
  u8g2.drawStr(0, 23, (String("Status: ") + statusText).substring(0, 25).c_str());
  u8g2.drawStr(0, 36, "UID:");

  // Raw 4- and 7-byte UIDs fit on one row; longer UIDs wrap to row two.
  if (lastUid.length() <= 25) {
    u8g2.drawStr(0, 49, lastUid.c_str());
  } else {
    u8g2.drawStr(0, 49, lastUid.substring(0, 25).c_str());
    u8g2.drawStr(0, 62, lastUid.substring(25).c_str());
  }
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
  const wl_status_t wifiStatus = WiFi.status();
  if (wifiStatus == WL_CONNECTED) {
    if (!wifiWasConnected) {
      showStatus("Ready - scan card");
      Serial.print("WiFi connected. ESP32 IP: ");
      Serial.println(WiFi.localIP());
    }
    wifiWasConnected = true;
    return true;
  }

  wifiWasConnected = false;

  // Start Wi-Fi once. Let the ESP32 driver's auto-reconnect handle retries.
  // Calling WiFi.begin() while association is pending triggers
  // "sta is connecting, cannot set config".
  if (!wifiStarted) {
    wifiStarted = true;
    showStatus("Connecting WiFi");
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);
    WiFi.setAutoReconnect(true);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.println("Started WiFi connection; auto-reconnect enabled");
  }

  if (millis() - lastWifiStatusLog >= 5000) {
    lastWifiStatusLog = millis();
    Serial.printf("Waiting for WiFi; status code: %d\n", (int)wifiStatus);
    if (millis() >= 20000) showStatus("WiFi not connected");
  }
  return false;
}

bool sendScan(const String &uid) {
  if (!connectWiFi()) return false;
  WiFiClientSecure client;
  // Temporary certificate bypass for initial connectivity testing.
  // Replace with client.setCACert(ROOT_CA) before production use.
  client.setInsecure();
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
    String action;
    if (response.indexOf("REGISTRATION_PENDING") >= 0) {
      action = "Card ready to register";
    } else if (response.indexOf("CLOCK_OUT") >= 0) {
      action = "Clocked out";
    } else {
      action = "Clocked in";
    }
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
  WiFi.onEvent(onWiFiEvent);

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

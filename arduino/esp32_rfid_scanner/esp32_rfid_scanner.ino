#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <MFRC522.h>
#include <U8g2lib.h>
#include <ctype.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>

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
// Paste the Project URL (without a trailing slash) and publishable key here.
const char *SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co";
const char *SUPABASE_PUBLISHABLE_KEY = "sb_publishable_YOUR_KEY";

MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);
U8G2_SSD1306_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE);
String lastUid = "-";
String statusText = "Connecting WiFi";
bool wifiStarted = false;
bool wifiWasConnected = false;
bool ntpStarted = false;
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

String urlEncode(const String &value) {
  String encoded;
  char escaped[4];
  for (size_t i = 0; i < value.length(); ++i) {
    const unsigned char c = (unsigned char)value[i];
    const bool unreserved = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
                            (c >= '0' && c <= '9') || c == '-' || c == '_' ||
                            c == '.' || c == '~';
    if (unreserved) encoded += (char)c;
    else {
      snprintf(escaped, sizeof(escaped), "%%%02X", c);
      encoded += escaped;
    }
  }
  return encoded;
}

String jsonField(const String &json, const char *field) {
  const String marker = String("\"") + field + "\"";
  int position = json.indexOf(marker);
  if (position < 0) return "";
  position = json.indexOf(':', position + marker.length());
  if (position < 0) return "";
  ++position;
  while (position < (int)json.length() && isspace((unsigned char)json[position])) ++position;
  if (position >= (int)json.length()) return "";

  if (json[position] == '"') {
    const int start = ++position;
    while (position < (int)json.length()) {
      if (json[position] == '\\') {
        position += 2;
        continue;
      }
      if (json[position] == '"') return json.substring(start, position);
      ++position;
    }
    return "";
  }

  int end = position;
  while (end < (int)json.length() && json[end] != ',' && json[end] != '}' &&
         json[end] != ']' && !isspace((unsigned char)json[end])) ++end;
  return json.substring(position, end);
}

long jsonLongField(const String &json, const char *field) {
  const String value = jsonField(json, field);
  if (!value.length() || value == "null") return -1;
  return value.toInt();
}

bool hasJsonRow(const String &response) {
  return response.indexOf('{') >= 0;
}

int supabaseRequest(const char *method, const String &path, const String &body,
                    String &response, const char *prefer = nullptr) {
  if (!connectWiFi()) return -1;
  WiFiClientSecure client;
  // Certificate verification is disabled for bring-up; install the Supabase
  // root CA and use setCACert() before deploying this scanner.
  client.setInsecure();
  HTTPClient http;
  const String url = String(SUPABASE_URL) + "/rest/v1/" + path;
  if (!http.begin(client, url)) return -1;
  http.setTimeout(8000);
  http.addHeader("apikey", SUPABASE_PUBLISHABLE_KEY);
  // Legacy anon keys are JWTs and also belong in Authorization. New
  // sb_publishable_ keys are not JWTs and should only be sent as apikey.
  if (String(SUPABASE_PUBLISHABLE_KEY).startsWith("eyJ")) {
    http.addHeader("Authorization", String("Bearer ") + SUPABASE_PUBLISHABLE_KEY);
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Accept", "application/json");
  if (prefer) http.addHeader("Prefer", prefer);
  int code = strcmp(method, "GET") == 0 ? http.GET() : http.sendRequest(method, body);
  response = code > 0 ? http.getString() : "";
  http.end();
  return code;
}

bool getUtcTimes(time_t &nowEpoch, String &nowText, String &dayStart, String &nextDayStart) {
  if (!ntpStarted) {
    configTime(0, 0, "pool.ntp.org", "time.google.com");
    ntpStarted = true;
  }

  nowEpoch = time(nullptr);
  const unsigned long startWait = millis();
  while (nowEpoch < 1700000000 && millis() - startWait < 10000) {
    delay(250);
    nowEpoch = time(nullptr);
  }
  if (nowEpoch < 1700000000) return false;

  struct timeval preciseNow;
  gettimeofday(&preciseNow, nullptr);
  nowEpoch = preciseNow.tv_sec;
  struct tm utcNow;
  gmtime_r(&nowEpoch, &utcNow);
  char buffer[40];
  strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%S", &utcNow);
  snprintf(buffer + strlen(buffer), sizeof(buffer) - strlen(buffer), ".%06ld",
           (long)preciseNow.tv_usec);
  nowText = buffer;

  const time_t midnightEpoch = nowEpoch - (utcNow.tm_hour * 3600) -
                               (utcNow.tm_min * 60) - utcNow.tm_sec;
  struct tm utcMidnight;
  gmtime_r(&midnightEpoch, &utcMidnight);
  strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%S", &utcMidnight);
  dayStart = buffer;

  const time_t nextMidnightEpoch = midnightEpoch + 24 * 60 * 60;
  gmtime_r(&nextMidnightEpoch, &utcMidnight);
  strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%S", &utcMidnight);
  nextDayStart = buffer;
  return true;
}

bool patchLastUsed(long cardId, const String &timestamp) {
  String response;
  const String path = String("rfid_cards?id=eq.") + cardId;
  const String body = String("{\"last_used_at\":\"") + timestamp + "\"}";
  const int code = supabaseRequest("PATCH", path, body, response, "return=minimal");
  if (code < 200 || code >= 300) {
    Serial.printf("RFID last_used_at update HTTP %d: %s\n", code, response.c_str());
    return false;
  }
  return true;
}

// Returns -1 on request failure, 0 when admin scan mode is off, and 1 when ready.
int readAdminScanSession(String &sessionId) {
  String response;
  const String path = String("rfid_scan_control?select=is_armed,session_id") +
      "&id=eq.1&is_armed=eq.true&limit=1";
  const int code = supabaseRequest("GET", path, "", response);
  if (code < 200 || code >= 300) {
    Serial.printf("RFID scan-session read HTTP %d: %s\n", code, response.c_str());
    return -1;
  }
  if (!hasJsonRow(response) || jsonField(response, "is_armed") != "true") return 0;
  sessionId = jsonField(response, "session_id");
  return sessionId.length() ? 1 : 0;
}

bool publishAdminScan(const String &uid, const String &sessionId, long cardId) {
  String response;
  String body = String("{\"card_uid\":\"") + uid +
      "\",\"scan_session_id\":\"" + sessionId + "\"";
  if (cardId >= 0) body += String(",\"rfid_card_id\":") + cardId;
  body += "}";
  const int code = supabaseRequest("POST", "rfid_scan_events", body, response,
                                   "return=minimal");
  if (code < 200 || code >= 300) {
    Serial.printf("RFID admin scan publish HTTP %d: %s\n", code, response.c_str());
    return false;
  }
  return true;
}

bool sendScan(const String &uid) {
  if (!connectWiFi()) return false;

  String sessionId;
  const int scanMode = readAdminScanSession(sessionId);
  if (scanMode < 0) {
    showStatus("Scan mode check failed");
    return false;
  }
  const bool adminScan = scanMode == 1;

  String response;
  String path = String("rfid_cards?select=id,staff_id,status&card_uid=eq.") +
                urlEncode(uid) + "&limit=1";
  int code = supabaseRequest("GET", path, "", response);
  if (code < 200 || code >= 300) {
    showStatus(code == 401 ? "Supabase key invalid" : "Supabase read failed");
    Serial.printf("Supabase RFID lookup HTTP %d: %s\n", code, response.c_str());
    return false;
  }

  long cardId = jsonLongField(response, "id");
  long staffId = jsonLongField(response, "staff_id");
  String cardStatus = jsonField(response, "status");
  const bool cardAlreadyInDatabase = hasJsonRow(response);

  if (!cardAlreadyInDatabase) {
    if (!adminScan) {
      Serial.printf("[RFID] Ignored unregistered card while admin scan is off: %s\n",
                    uid.c_str());
      showStatus("Admin scan required");
      return false;
    }
  }

  if (adminScan) {
    if (!publishAdminScan(uid, sessionId, cardId)) {
      showStatus("Admin scan was not saved");
      return false;
    }
    Serial.printf("[RFID] Admin scan event saved: UID=%s CARD_ID=%ld\n",
                  uid.c_str(), cardId);
    showStatus("Admin scan captured");
    return true;
  }

  if (cardStatus == "pending" && staffId < 0) {
    showStatus("Admin scan required");
    return false;
  }
  if (cardStatus != "active" || staffId < 0 || cardId < 0) {
    showStatus("Card access denied");
    return false;
  }

  String staffResponse;
  path = String("staff?select=id,shift,status&id=eq.") + staffId + "&limit=1";
  code = supabaseRequest("GET", path, "", staffResponse);
  if (code < 200 || code >= 300) {
    showStatus("Supabase read failed");
    Serial.printf("Supabase staff read HTTP %d: %s\n", code, staffResponse.c_str());
    return false;
  }
  if (!hasJsonRow(staffResponse) || jsonField(staffResponse, "status") != "active") {
    showStatus("Card access denied");
    return false;
  }

  // NTP is required for attendance timestamps, but not for admin card lookup.
  time_t nowEpoch;
  String nowText, dayStart, nextDayStart;
  if (!getUtcTimes(nowEpoch, nowText, dayStart, nextDayStart)) {
    Serial.println("[RFID] NTP time unavailable; attendance was not written.");
    showStatus("Time sync failed");
    return false;
  }

  String openLogResponse;
  path = String("attendance_logs?select=id,time_in&staff_id=eq.") + staffId +
         "&time_out=is.null&and=(time_in.gte." + dayStart +
         ",time_in.lt." + nextDayStart + ")&order=time_in.desc&limit=1";
  code = supabaseRequest("GET", path, "", openLogResponse);
  if (code < 200 || code >= 300) {
    showStatus("Supabase read failed");
    Serial.printf("Supabase attendance lookup HTTP %d: %s\n", code, openLogResponse.c_str());
    return false;
  }

  if (hasJsonRow(openLogResponse)) {
    const long attendanceId = jsonLongField(openLogResponse, "id");
    if (attendanceId < 0) {
      showStatus("Attendance lookup failed");
      return false;
    }
    const String body = String("{\"time_out\":\"") + nowText +
                        "\",\"rfid_tap_out\":\"" + uid + "\"}";
    path = String("attendance_logs?id=eq.") + attendanceId;
    code = supabaseRequest("PATCH", path, body, response, "return=minimal");
    if (code < 200 || code >= 300) {
      showStatus("Clock-out save failed");
      Serial.printf("Supabase clock-out HTTP %d: %s\n", code, response.c_str());
      return false;
    }
    patchLastUsed(cardId, nowText);
    showStatus("Clocked out");
    return true;
  }

  const String shift = jsonField(staffResponse, "shift");
  const int expectedHour = shift == "morning" ? 8 : (shift == "afternoon" ? 14 : 20);
  struct tm utcNow;
  gmtime_r(&nowEpoch, &utcNow);
  const bool isLate = (utcNow.tm_hour * 60 + utcNow.tm_min) > expectedHour * 60 + 15;
  const String body = String("{\"staff_id\":") + staffId +
      ",\"time_in\":\"" + nowText + "\",\"status\":\"" +
      (isLate ? "late" : "on_time") + "\",\"rfid_tap_in\":\"" + uid +
      "\",\"notes\":\"ESP32 RFID tap in via Card " + uid + "\"}";
  code = supabaseRequest("POST", "attendance_logs", body, response, "return=minimal");
  if (code < 200 || code >= 300) {
    showStatus("Clock-in save failed");
    Serial.printf("Supabase clock-in HTTP %d: %s\n", code, response.c_str());
    return false;
  }

  patchLastUsed(cardId, nowText);
  showStatus("Clocked in");
  return true;
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

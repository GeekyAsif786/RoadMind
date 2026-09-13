#include <WiFi.h>
#include <time.h>

// -----------------------------
// Wi-Fi configuration
// -----------------------------
const char* WIFI_SSID = "XAC3";
const char* WIFI_PASSWORD = "11111123";

// -----------------------------
// NTP configuration
// -----------------------------
const char* NTP_SERVER = "pool.ntp.org";

const long GMT_OFFSET_SEC = 0;
const int DAYLIGHT_OFFSET_SEC = 0;

// -----------------------------
// Connect to Wi-Fi
// -----------------------------
void connectWiFi() {
  Serial.print("Connecting to Wi-Fi");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("Wi-Fi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

// -----------------------------
// Synchronize time
// -----------------------------
bool syncTime() {
  Serial.println("Synchronizing UTC time...");

  configTime(
    GMT_OFFSET_SEC,
    DAYLIGHT_OFFSET_SEC,
    NTP_SERVER
  );

  struct tm timeinfo;

  for (int i = 0; i < 20; i++) {
    if (getLocalTime(&timeinfo, 1000)) {
      Serial.println("Time synchronized");
      return true;
    }

    Serial.println("Waiting for NTP...");
  }

  Serial.println("NTP synchronization failed");
  return false;
}

// -----------------------------
// Print current UTC time
// -----------------------------
void printCurrentTime() {
  struct tm timeinfo;

  if (!getLocalTime(&timeinfo, 1000)) {
    Serial.println("Unable to read system time");
    return;
  }

  char buffer[32];

  strftime(
    buffer,
    sizeof(buffer),
    "%Y-%m-%d %H:%M:%S UTC",
    &timeinfo
  );

  Serial.print("Current time: ");
  Serial.println(buffer);
}

// -----------------------------
// Setup
// -----------------------------
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("RoadMind Edge Network Test");

  connectWiFi();

  if (syncTime()) {
    printCurrentTime();
  }
}

// -----------------------------
// Loop
// -----------------------------
void loop() {
  static unsigned long lastPrint = 0;

  if (millis() - lastPrint >= 5000) {
    lastPrint = millis();
    printCurrentTime();
  }
}
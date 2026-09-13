#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID = "XAC3";
const char* WIFI_PASSWORD = "11111123";

const char* SERVER_URL = "http://10.75.178.35:8000/api/v1/health";

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("RoadMind ESP32 HTTP Test");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Connecting to Wi-Fi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("Wi-Fi connected");
  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());

  HTTPClient http;

  Serial.print("Requesting: ");
  Serial.println(SERVER_URL);

  http.begin(SERVER_URL);

  int httpCode = http.GET();

  Serial.print("HTTP status: ");
  Serial.println(httpCode);

  if (httpCode > 0) {
    Serial.println("Response:");
    Serial.println(http.getString());
  } else {
    Serial.print("HTTP request failed: ");
    Serial.println(http.errorToString(httpCode));
  }

  http.end();
}

void loop() {
}
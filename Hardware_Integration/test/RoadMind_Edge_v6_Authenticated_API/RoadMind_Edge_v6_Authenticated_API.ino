#include <WiFi.h>
#include <HTTPClient.h>
#include "secrets.h"

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("RoadMind authenticated API test");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("Wi-Fi connected");
  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());

  HTTPClient http;

  String url =
      String(ROADMIND_BASE_URL) +
      "/api/v1/device/signals/control/pending";

  Serial.print("GET ");
  Serial.println(url);

  http.begin(url);

  http.addHeader(
      "X-Device-Credential",
      ROADMIND_DEVICE_CREDENTIAL
  );

  int httpCode = http.GET();

  Serial.print("HTTP status: ");
  Serial.println(httpCode);

  if (httpCode > 0) {
    String response = http.getString();

    Serial.println("Response:");
    Serial.println(response);
  } else {
    Serial.print("Request failed: ");
    Serial.println(http.errorToString(httpCode));
  }

  http.end();
}

void loop() {
}
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#include "secrets.h"

const unsigned long POLL_INTERVAL = 5000;
unsigned long lastPoll = 0;

void fetchPendingCommands() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Poll skipped: Wi-Fi disconnected");
    return;
  }

  HTTPClient http;

  String url =
      String(ROADMIND_BASE_URL) +
      "/api/v1/device/signals/control/pending";

  Serial.println();
  Serial.print("Polling: ");
  Serial.println(url);

  http.begin(url);

  http.addHeader(
      "X-Device-Credential",
      ROADMIND_DEVICE_CREDENTIAL
  );

  int httpCode = http.GET();

  Serial.print("HTTP status: ");
  Serial.println(httpCode);

  if (httpCode < 0) {
    Serial.print("HTTP request failed: ");
    Serial.println(http.errorToString(httpCode));
    http.end();
    return;
  }

  String response = http.getString();

  if (httpCode != HTTP_CODE_OK) {
    Serial.println("Server returned an error:");
    Serial.println(response);
    http.end();
    return;
  }

  Serial.println("Server response:");
  Serial.println(response);

  JsonDocument doc;

  DeserializationError error = deserializeJson(doc, response);

  if (error) {
    Serial.print("JSON parse failed: ");
    Serial.println(error.c_str());
    http.end();
    return;
  }

  JsonArray commands = doc.as<JsonArray>();

  Serial.print("Pending commands: ");
  Serial.println(commands.size());

  for (JsonObject command : commands) {
    Serial.println();
    Serial.println("Command:");

    Serial.print("  ID: ");
    Serial.println(command["command_id"].as<String>());

    Serial.print("  Intersection: ");
    Serial.println(command["intersection_id"].as<String>());

    Serial.print("  Plan: ");
    Serial.println(command["plan_id"].as<String>());

    Serial.print("  Phase: ");
    Serial.println(command["phase_number"].as<int>());

    Serial.print("  Direction: ");
    Serial.println(command["direction"].as<String>());

    Serial.print("  Green: ");
    Serial.print(command["green_seconds"].as<int>());
    Serial.println(" seconds");

    Serial.print("  Yellow: ");
    Serial.print(command["yellow_seconds"].as<int>());
    Serial.println(" seconds");

    Serial.print("  Expires: ");
    Serial.println(command["expires_at"].as<String>());

    Serial.print("  Status: ");
    Serial.println(command["status"].as<String>());
  }

  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("================================");
  Serial.println("RoadMind Edge v7 - Command Poll");
  Serial.println("================================");

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
}

void loop() {
  if (millis() - lastPoll >= POLL_INTERVAL) {
    lastPoll = millis();
    fetchPendingCommands();
  }
}
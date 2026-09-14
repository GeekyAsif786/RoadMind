#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include <Preferences.h>

#include "secrets.h"

// ============================================================
// GPIO
// ============================================================

const int RED_LED = 4;
const int YELLOW_LED = 5;
const int GREEN_LED = 6;

// ============================================================
// Wi-Fi
// ============================================================

const unsigned long WIFI_RETRY_INTERVAL = 10000;

unsigned long lastWiFiAttempt = 0;
bool wifiReportedConnected = false;

// ============================================================
// NTP / UTC
// ============================================================

const char* NTP_SERVER = "pool.ntp.org";

const long GMT_OFFSET_SEC = 0;
const int DAYLIGHT_OFFSET_SEC = 0;

bool timeSynchronized = false;
unsigned long lastTimeCheck = 0;

// ============================================================
// Signal state machine
// ============================================================

enum SignalState {
  SAFE_RED,
  GREEN,
  YELLOW,
  ALL_RED
};

SignalState state = SAFE_RED;

unsigned long stateStartedAt = 0;

// Prototype safety values.
// Later these can come from configuration.
const unsigned long MIN_GREEN_TIME = 5000;
const unsigned long RED_CLEARANCE_TIME = 3000;
const unsigned long EXECUTION_REPORT_RETRY_INTERVAL = 5000;
//-------------------------

unsigned long activeGreenTime = MIN_GREEN_TIME;
unsigned long activeYellowTime = 2000;
unsigned long lastExecutionReportAttempt = 0;

// ============================================================
// RoadMind command
// ============================================================

struct PendingCommand {
  bool valid = false;

  // Server acknowledgement state.
  bool acknowledged = false;

  // True once the requested phase has actually become active.
  bool executionStarted = false;
  String commandId;
  String planId;

  int phaseNumber = 0;

  unsigned long greenTime = 0;
  unsigned long yellowTime = 0;

  String expiresAt;
};

PendingCommand activeCommand;

// ============================================================
// Persistent storage
// ============================================================

Preferences commandPrefs;

const char* COMMAND_NAMESPACE = "roadmind";

String lastCompletedCommandId = "";

// After reboot, a recovered command must wait until UTC is
// synchronized before we decide whether it is expired.
bool recoveryValidationPending = false;

// ============================================================
// GPIO helpers
// ============================================================

void allOff() {
  digitalWrite(RED_LED, LOW);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(GREEN_LED, LOW);
}


void applyState(SignalState newState) {
  state = newState;
  stateStartedAt = millis();

  // Fail-safe output transition:
  // turn everything off before activating the new state.
  allOff();

  switch (state) {
    case SAFE_RED:
    case ALL_RED:
      digitalWrite(RED_LED, HIGH);
      break;

    case GREEN:
      digitalWrite(GREEN_LED, HIGH);
      break;

    case YELLOW:
      digitalWrite(YELLOW_LED, HIGH);
      break;
  }
}


// ============================================================
// Wi-Fi
// ============================================================

void startWiFiConnection() {
  Serial.println("Starting Wi-Fi connection...");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  lastWiFiAttempt = millis();
}


void updateWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifiReportedConnected) {
      wifiReportedConnected = true;

      Serial.println("Wi-Fi connected");
      Serial.print("ESP32 IP: ");
      Serial.println(WiFi.localIP());
    }

    return;
  }

  if (wifiReportedConnected) {
    wifiReportedConnected = false;

    // IMPORTANT:
    // Do not invalidate timeSynchronized here.
    // Once NTP has synchronized the clock, the ESP32 can continue
    // keeping time while Wi-Fi is temporarily unavailable.

    Serial.println("Wi-Fi disconnected");
  }

  if (millis() - lastWiFiAttempt >= WIFI_RETRY_INTERVAL) {
    startWiFiConnection();
  }
}


// ============================================================
// NTP / UTC
// ============================================================

void updateTimeSync() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  // Try immediately when not synchronized.
  // Otherwise periodically refresh the clock.
  if (
    timeSynchronized &&
    millis() - lastTimeCheck < 10000
  ) {
    return;
  }

  lastTimeCheck = millis();

  configTime(
    GMT_OFFSET_SEC,
    DAYLIGHT_OFFSET_SEC,
    NTP_SERVER
  );

  struct tm timeinfo;

  if (getLocalTime(&timeinfo, 1000)) {
    if (!timeSynchronized) {
      timeSynchronized = true;
      Serial.println("UTC time synchronized");
    }
  }
}


// ============================================================
// ISO-8601 UTC parser
// ============================================================

bool parseIsoUtc(
  const String& value,
  time_t& timestamp
) {
  if (value.length() < 20) {
    return false;
  }

  int year;
  int month;
  int day;
  int hour;
  int minute;
  int second;

  int parsed = sscanf(
    value.c_str(),
    "%d-%d-%dT%d:%d:%d",
    &year,
    &month,
    &day,
    &hour,
    &minute,
    &second
  );

  if (parsed != 6) {
    return false;
  }

  struct tm timeinfo = {};

  timeinfo.tm_year = year - 1900;
  timeinfo.tm_mon = month - 1;
  timeinfo.tm_mday = day;
  timeinfo.tm_hour = hour;
  timeinfo.tm_min = minute;
  timeinfo.tm_sec = second;

  // Timezone is explicitly configured to UTC in setup().
  timestamp = mktime(&timeinfo);

  return timestamp != (time_t)-1;
}


// ============================================================
// Command expiration validation
// ============================================================

bool commandIsExpired(const String& expiresAt) {
  if (expiresAt.length() == 0) {
    return false;
  }

  if (!timeSynchronized) {
    Serial.println(
      "Command rejected: UTC time is not synchronized"
    );

    return true;
  }

  time_t expiryTimestamp;

  if (!parseIsoUtc(expiresAt, expiryTimestamp)) {
    Serial.println(
      "Command rejected: invalid expiration timestamp"
    );

    return true;
  }

  time_t now = time(nullptr);

  return now >= expiryTimestamp;
}


// ============================================================
// Command validation
// ============================================================

bool validateCommand(
  const String& commandId,
  const String& planId,
  int phaseNumber,
  int greenSeconds,
  int yellowSeconds,
  const String& expiresAt
) {
  if (commandId.length() == 0) {
    Serial.println("Command rejected: missing command ID");
    return false;
  }

  if (planId.length() == 0) {
    Serial.println("Command rejected: missing plan ID");
    return false;
  }

  if (phaseNumber < 1 || phaseNumber > 16) {
    Serial.println("Command rejected: invalid phase");
    return false;
  }

  if (greenSeconds < 15 || greenSeconds > 90) {
    Serial.println("Command rejected: invalid GREEN duration");
    return false;
  }

  if (yellowSeconds < 1 || yellowSeconds > 10) {
    Serial.println("Command rejected: invalid YELLOW duration");
    return false;
  }

  if (commandIsExpired(expiresAt)) {
    Serial.println("Command rejected: command expired");
    return false;
  }

  return true;
}


// ============================================================
// Persistent command storage
// ============================================================

void saveActiveCommand() {
  commandPrefs.begin(COMMAND_NAMESPACE, false);

  commandPrefs.putBool(
    "valid",
    activeCommand.valid
  );

  commandPrefs.putBool(
    "ack",
    activeCommand.acknowledged
  );

  commandPrefs.putBool(
    "started",
    activeCommand.executionStarted
  );

  commandPrefs.putString(
    "commandId",
    activeCommand.commandId
  );

  commandPrefs.putString(
    "planId",
    activeCommand.planId
  );

  commandPrefs.putInt(
    "phase",
    activeCommand.phaseNumber
  );

  commandPrefs.putULong(
    "greenMs",
    activeCommand.greenTime
  );

  commandPrefs.putULong(
    "yellowMs",
    activeCommand.yellowTime
  );

  commandPrefs.putString(
    "expiresAt",
    activeCommand.expiresAt
  );

  commandPrefs.end();

  Serial.println("Active command persisted");
}


void clearStoredCommand() {
  commandPrefs.begin(COMMAND_NAMESPACE, false);

  commandPrefs.clear();

  commandPrefs.end();

  Serial.println("Stored command cleared");
}


bool loadActiveCommand() {
  commandPrefs.begin(COMMAND_NAMESPACE, true);

  bool valid =
    commandPrefs.getBool("valid", false);

  if (!valid) {
    commandPrefs.end();
    return false;
  }

  activeCommand.valid = true;

  activeCommand.acknowledged =
    commandPrefs.getBool("ack", false);

  // After a reboot we do not trust the previous physical
  // execution state. The controller always restarts safely
  // from SAFE_RED.
  activeCommand.executionStarted = false;
  lastExecutionReportAttempt = 0;
  activeCommand.commandId =
    commandPrefs.getString("commandId", "");

  activeCommand.planId =
    commandPrefs.getString("planId", "");

  activeCommand.phaseNumber =
    commandPrefs.getInt("phase", 0);

  activeCommand.greenTime =
    commandPrefs.getULong("greenMs", 0);

  activeCommand.yellowTime =
    commandPrefs.getULong("yellowMs", 0);

  activeCommand.expiresAt =
    commandPrefs.getString("expiresAt", "");

  commandPrefs.end();

  return true;
}


// ============================================================
// Validate recovered command after UTC synchronization
// ============================================================

void updateRecoveredCommandValidation() {
  if (!activeCommand.valid) {
    return;
  }

  if (!recoveryValidationPending) {
    return;
  }

  // Stay SAFE_RED until we have a trustworthy UTC clock.
  if (!timeSynchronized) {
    return;
  }

  if (commandIsExpired(activeCommand.expiresAt)) {
    Serial.println(
      "Recovered command has expired; discarding"
    );

    activeCommand.valid = false;
    clearStoredCommand();

    applyState(SAFE_RED);

    recoveryValidationPending = false;

    return;
  }

  Serial.println(
    "Recovered command passed expiration check"
  );

  recoveryValidationPending = false;
}


// ============================================================
// RoadMind acknowledgement
// ============================================================

bool acknowledgeCommand(
  const String& commandId
) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(
      "Acknowledgement skipped: Wi-Fi disconnected"
    );

    return false;
  }

  HTTPClient http;

  String url =
    String(ROADMIND_BASE_URL) +
    "/api/v1/device/signals/control/" +
    commandId +
    "/acknowledge";

  http.begin(url);

  http.addHeader(
    "X-Device-Credential",
    ROADMIND_DEVICE_CREDENTIAL
  );

  int httpCode = http.POST("");

  Serial.print("Acknowledgement HTTP status: ");
  Serial.println(httpCode);

  if (httpCode == HTTP_CODE_OK) {
    Serial.println("Command acknowledged");

    http.end();

    return true;
  }

  if (httpCode > 0) {
    Serial.println(http.getString());
  }

  http.end();

  return false;
}


// ============================================================
// RoadMind execution report
// ============================================================

bool reportExecution() {
  if (!activeCommand.valid) {
    return false;
  }

  if (
    !activeCommand.acknowledged ||
    !activeCommand.executionStarted
  ) {
    return false;
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(
      "Execution report postponed: Wi-Fi disconnected"
    );

    return false;
  }

  HTTPClient http;

  String url =
    String(ROADMIND_BASE_URL) +
    "/api/v1/device/signals/control/" +
    activeCommand.commandId +
    "/execution";

  http.begin(url);

  http.addHeader(
    "Content-Type",
    "application/json"
  );

  http.addHeader(
    "X-Device-Credential",
    ROADMIND_DEVICE_CREDENTIAL
  );

  String body =
    String("{") +
    "\"current_phase\":" +
    String(activeCommand.phaseNumber) +
    "," +
    "\"phase_state\":\"green\"," +
    "\"controller_status\":\"online\"," +
    "\"reported_plan_id\":\"" +
    activeCommand.planId +
    "\"" +
    "}";

  int httpCode = http.POST(body);

  Serial.print("Execution report HTTP status: ");
  Serial.println(httpCode);

  if (httpCode == HTTP_CODE_OK) {
    Serial.println("Execution report accepted");

    http.end();

    return true;
  }

  if (httpCode > 0) {
    Serial.println(http.getString());
  }

  http.end();

  return false;
}


// ============================================================
// Complete command after successful execution report
// ============================================================

void completeActiveCommand() {
  lastCompletedCommandId =
    activeCommand.commandId;

  activeCommand.valid = false;
  activeCommand.acknowledged = false;
  activeCommand.executionStarted = false;

  clearStoredCommand();

  Serial.println(
    "Command execution confirmed by RoadMind"
  );
}


// ============================================================
// Retry execution report when needed
// ============================================================

void retryExecutionReport() {
  if (!activeCommand.valid) {
    return;
  }

  if (
    !activeCommand.acknowledged ||
    !activeCommand.executionStarted
  ) {
    return;
  }

  unsigned long now = millis();

  // First attempt is immediate.
  // Subsequent attempts are rate-limited.
  if (
    lastExecutionReportAttempt != 0 &&
    now - lastExecutionReportAttempt <
      EXECUTION_REPORT_RETRY_INTERVAL
  ) {
    return;
  }

  lastExecutionReportAttempt = now;

  Serial.println("Attempting RoadMind execution report...");

  if (reportExecution()) {
    completeActiveCommand();
  } else {
    Serial.println(
      "Execution report not confirmed; will retry"
    );
  }
}


// ============================================================
// Fetch pending commands
// ============================================================

void fetchPendingCommands() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  // Do not fetch another command while one exists locally.
  if (activeCommand.valid) {
    return;
  }

  HTTPClient http;

  String url =
    String(ROADMIND_BASE_URL) +
    "/api/v1/device/signals/control/pending";

  http.begin(url);

  http.addHeader(
    "X-Device-Credential",
    ROADMIND_DEVICE_CREDENTIAL
  );

  int httpCode = http.GET();

  Serial.print("Pending HTTP status: ");
  Serial.println(httpCode);

  if (httpCode != HTTP_CODE_OK) {
    if (httpCode > 0) {
      Serial.println(http.getString());
    }

    http.end();

    return;
  }

  String response = http.getString();

  JsonDocument doc;

  DeserializationError error =
    deserializeJson(doc, response);

  if (error) {
    Serial.print("JSON parse failed: ");
    Serial.println(error.c_str());

    http.end();

    return;
  }

  JsonArray commands = doc.as<JsonArray>();

  if (
    commands.isNull() ||
    commands.size() == 0
  ) {
    Serial.println("No pending commands");

    http.end();

    return;
  }

  // Current prototype:
  // process only the newest command.
  JsonObject command = commands[0];

  String commandId =
    command["command_id"].as<String>();

  // Local replay guard.
  if (
    commandId.length() > 0 &&
    commandId == lastCompletedCommandId
  ) {
    Serial.print("Duplicate command ignored: ");
    Serial.println(commandId);

    http.end();

    return;
  }

  String planId =
    command["plan_id"].as<String>();

  int phaseNumber =
    command["phase_number"].as<int>();

  int greenSeconds =
    command["green_seconds"].as<int>();

  int yellowSeconds =
    command["yellow_seconds"].as<int>();

  String expiresAt =
    command["expires_at"].as<String>();

  String status =
    command["status"].as<String>();

  Serial.println();
  Serial.println("RoadMind command received:");

  Serial.print("  ID: ");
  Serial.println(commandId);

  Serial.print("  Phase: ");
  Serial.println(phaseNumber);

  Serial.print("  Green: ");
  Serial.println(greenSeconds);

  Serial.print("  Yellow: ");
  Serial.println(yellowSeconds);

  Serial.print("  Status: ");
  Serial.println(status);

  // Server should only give accepted commands.
  if (status != "accepted") {
    Serial.println(
      "Command ignored: status is not accepted"
    );

    http.end();

    return;
  }

  // Validate locally before any acknowledgement.
  if (
    !validateCommand(
      commandId,
      planId,
      phaseNumber,
      greenSeconds,
      yellowSeconds,
      expiresAt
    )
  ) {
    http.end();

    return;
  }

  // ----------------------------------------------------------
  // Persist BEFORE acknowledgement.
  // ----------------------------------------------------------

  activeCommand.valid = true;
  activeCommand.acknowledged = false;
  activeCommand.executionStarted = false;

  activeCommand.commandId = commandId;
  activeCommand.planId = planId;
  activeCommand.phaseNumber = phaseNumber;

  activeCommand.greenTime =
    greenSeconds * 1000UL;

  activeCommand.yellowTime =
    yellowSeconds * 1000UL;

  activeCommand.expiresAt = expiresAt;

  activeGreenTime =
    activeCommand.greenTime;

  activeYellowTime =
    activeCommand.yellowTime;

  saveActiveCommand();

  // ----------------------------------------------------------
  // Acknowledge server.
  // ----------------------------------------------------------

  if (!acknowledgeCommand(commandId)) {
    Serial.println(
      "Acknowledgement failed; command remains persisted"
    );

    http.end();

    return;
  }

  // ----------------------------------------------------------
  // Persist acknowledgement state.
  // ----------------------------------------------------------

  activeCommand.acknowledged = true;

  saveActiveCommand();

  Serial.println(
    "Command acknowledged and safely persisted"
  );

  Serial.println(
    "Command queued for deterministic execution"
  );

  http.end();
}


// ============================================================
// Process active command
// ============================================================

void processActiveCommand() {
  if (!activeCommand.valid) {
    return;
  }

  // A recovered command cannot execute until UTC validation
  // has completed.
  if (recoveryValidationPending) {
    return;
  }

  // Never execute before server acknowledgement.
  if (!activeCommand.acknowledged) {

    // An unacknowledged command that expires is discarded.
    if (
      !activeCommand.executionStarted &&
      commandIsExpired(activeCommand.expiresAt)
    ) {
      Serial.println(
        "Pending command expired before acknowledgement"
      );

      activeCommand.valid = false;
      clearStoredCommand();

      applyState(SAFE_RED);

      return;
    }

    // Retry acknowledgement when possible.
    if (
      acknowledgeCommand(activeCommand.commandId)
    ) {
      activeCommand.acknowledged = true;
      saveActiveCommand();

      Serial.println(
        "Command acknowledgement recovered"
      );
    }

    return;
  }

  // ==========================================================
  // EXECUTION HAS ALREADY STARTED
  // ==========================================================

  if (activeCommand.executionStarted) {

    // Keep retrying the execution report until RoadMind
    // confirms physical execution.
    retryExecutionReport();

    unsigned long elapsed =
      millis() - stateStartedAt;

    // ==========================================================
    // GREEN
    // ==========================================================

    if (state == GREEN) {

      if (elapsed >= activeGreenTime) {
        applyState(YELLOW);

        Serial.println(
          "Command execution GREEN -> YELLOW"
        );
      }

      return;
    }

    // ==========================================================
    // YELLOW
    // ==========================================================

    if (state == YELLOW) {

      if (elapsed >= activeYellowTime) {
        applyState(ALL_RED);

        Serial.println(
          "Command execution YELLOW -> ALL_RED"
        );
      }

      return;
    }

    // ==========================================================
    // ALL_RED
    // ==========================================================

    if (state == ALL_RED) {

      if (elapsed >= RED_CLEARANCE_TIME) {

        applyState(SAFE_RED);

        Serial.println(
          "Execution complete; waiting for RoadMind confirmation"
        );
      }

      return;
    }

    // ==========================================================
    // SAFE_RED
    // ==========================================================

    // Remain SAFE_RED while retrying the execution report.
    return;
  }

  // ==========================================================
  // EXECUTION HAS NOT STARTED YET
  // ==========================================================

  unsigned long elapsed =
    millis() - stateStartedAt;

  // ----------------------------------------------------------
  // SAFE_RED
  // ----------------------------------------------------------

  if (state == SAFE_RED) {

    activeGreenTime =
      activeCommand.greenTime;

    activeYellowTime =
      activeCommand.yellowTime;

    applyState(GREEN);

    activeCommand.executionStarted = true;
    lastExecutionReportAttempt = 0;
    saveActiveCommand();

    Serial.print("Execution started: ");
    Serial.println(activeCommand.commandId);

    // Requested phase is now physically active.
    // Report immediately, then retry every 5 seconds if needed.
    retryExecutionReport();

    return;
  }

  // ----------------------------------------------------------
  // GREEN
  // ----------------------------------------------------------

  if (state == GREEN) {

    // Always enforce the safety minimum.
    if (elapsed < MIN_GREEN_TIME) {
      return;
    }

    activeYellowTime =
      activeCommand.yellowTime;

    applyState(YELLOW);

    Serial.println(
      "Command transition: GREEN -> YELLOW"
    );

    return;
  }

  // ----------------------------------------------------------
  // YELLOW
  // ----------------------------------------------------------

  if (state == YELLOW) {

    if (elapsed < activeYellowTime) {
      return;
    }

    applyState(ALL_RED);

    Serial.println(
      "Command transition: YELLOW -> ALL_RED"
    );

    return;
  }

  // ----------------------------------------------------------
  // ALL_RED
  // ----------------------------------------------------------

  if (state == ALL_RED) {

    if (elapsed < RED_CLEARANCE_TIME) {
      return;
    }

    activeGreenTime =
      activeCommand.greenTime;

    applyState(GREEN);

    activeCommand.executionStarted = true;
    lastExecutionReportAttempt = 0;
    saveActiveCommand();

    Serial.println(
      "Requested phase is now physically active"
    );

    retryExecutionReport();

    return;
  }
}


// ============================================================
// Normal deterministic state machine
// ============================================================

void updateStateMachine() {

  if (recoveryValidationPending) {
    return;
  }

  if (activeCommand.valid) {
    processActiveCommand();
    return;
  }

  unsigned long elapsed =
    millis() - stateStartedAt;

  switch (state) {

    case SAFE_RED:
      break;

    case GREEN:
      if (elapsed >= activeGreenTime) {
        applyState(YELLOW);
      }
      break;

    case YELLOW:
      if (elapsed >= activeYellowTime) {
        applyState(ALL_RED);
      }
      break;

    case ALL_RED:
      if (elapsed >= RED_CLEARANCE_TIME) {
        applyState(GREEN);
      }
      break;
  }
}


// ============================================================
// Setup
// ============================================================

void setup() {

  pinMode(RED_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);

  Serial.begin(115200);

  delay(1000);

  // Explicitly make mktime()/time handling UTC.
  setenv("TZ", "UTC0", 1);
  tzset();

  Serial.println();
  Serial.println(
    "======================================"
  );

  Serial.println(
    "RoadMind Edge Controller v8.1"
  );

  Serial.println(
    "Persistent + Safety + Network"
  );

  Serial.println(
    "======================================"
  );

  // ----------------------------------------------------------
  // SAFETY FIRST
  // ----------------------------------------------------------

  applyState(SAFE_RED);

  // ----------------------------------------------------------
  // Recover any persisted command.
  // ----------------------------------------------------------

  if (loadActiveCommand()) {

    recoveryValidationPending = true;

    Serial.println();
    Serial.println(
      "Recovered persisted command:"
    );

    Serial.print("  ID: ");
    Serial.println(activeCommand.commandId);

    Serial.print("  Phase: ");
    Serial.println(activeCommand.phaseNumber);

    Serial.print("  Acknowledged: ");
    Serial.println(
      activeCommand.acknowledged
        ? "yes"
        : "no"
    );

   Serial.println(
    "  Execution state: reset to SAFE_RED after reboot"
  );

    Serial.println(
      "Waiting for UTC synchronization before recovery validation"
    );
  }

  // Configure Wi-Fi.
  startWiFiConnection();
}


// ============================================================
// Main loop
// ============================================================

void loop() {

  // ----------------------------------------------------------
  // Network management first.
  // ----------------------------------------------------------

  updateWiFi();

  // ----------------------------------------------------------
  // UTC clock.
  // ----------------------------------------------------------

  updateTimeSync();

  // ----------------------------------------------------------
  // Recovered command validation.
  // ----------------------------------------------------------

  updateRecoveredCommandValidation();

  // ----------------------------------------------------------
  // Deterministic controller.
  // ----------------------------------------------------------

  updateStateMachine();

  // ----------------------------------------------------------
  // Poll RoadMind every 5 seconds.
  // ----------------------------------------------------------

  static unsigned long lastPoll = 0;

  if (
    millis() - lastPoll >= 5000
  ) {
    lastPoll = millis();

    fetchPendingCommands();
  }
}
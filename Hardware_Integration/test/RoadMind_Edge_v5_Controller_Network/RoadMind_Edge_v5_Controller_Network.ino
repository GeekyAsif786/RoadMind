#include <WiFi.h>
#include <time.h>

// ============================================================
// GPIO
// ============================================================

const int RED_LED = 4;
const int YELLOW_LED = 5;
const int GREEN_LED = 6;

// ============================================================
// Wi-Fi
// ============================================================

const char* WIFI_SSID = "XAC3";
const char* WIFI_PASSWORD = "11111123";

const unsigned long WIFI_RETRY_INTERVAL = 10000;
unsigned long lastWiFiAttempt = 0;

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

const unsigned long MIN_GREEN_TIME = 5000;
const unsigned long DEFAULT_YELLOW_TIME = 2000;
const unsigned long RED_CLEARANCE_TIME = 3000;

unsigned long activeGreenTime = MIN_GREEN_TIME;
unsigned long activeYellowTime = DEFAULT_YELLOW_TIME;

// ============================================================
// Structured command
// ============================================================

bool commandPending = false;

String pendingCommandId;
int pendingPhase = 0;

unsigned long pendingGreenTime = 0;
unsigned long pendingYellowTime = 0;

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
// Wi-Fi manager
// ============================================================

void startWiFiConnection() {
  Serial.println("Starting Wi-Fi connection...");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  lastWiFiAttempt = millis();
}

void updateWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    static bool reportedConnected = false;

    if (!reportedConnected) {
      reportedConnected = true;

      Serial.println("Wi-Fi connected");
      Serial.print("IP address: ");
      Serial.println(WiFi.localIP());
    }

    return;
  }

  static bool reportedDisconnected = false;

  if (!reportedDisconnected) {
    reportedDisconnected = true;
    Serial.println("Wi-Fi disconnected");
  }

  if (millis() - lastWiFiAttempt >= WIFI_RETRY_INTERVAL) {
    reportedDisconnected = false;
    startWiFiConnection();
  }
}

// ============================================================
// NTP / UTC manager
// ============================================================

bool trySynchronizeTime() {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

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

    return true;
  }

  return false;
}

void updateTimeSync() {
  if (WiFi.status() != WL_CONNECTED) {
    timeSynchronized = false;
    return;
  }

  if (millis() - lastTimeCheck < 10000) {
    return;
  }

  lastTimeCheck = millis();

  trySynchronizeTime();
}

void printCurrentUTC() {
  struct tm timeinfo;

  if (!getLocalTime(&timeinfo, 1000)) {
    Serial.println("UTC time unavailable");
    return;
  }

  char buffer[32];

  strftime(
    buffer,
    sizeof(buffer),
    "%Y-%m-%d %H:%M:%S UTC",
    &timeinfo
  );

  Serial.print("Current UTC: ");
  Serial.println(buffer);
}

// ============================================================
// Command validation
// ============================================================

bool validateCommand(
  const String& commandId,
  int phaseNumber,
  int greenSeconds,
  int yellowSeconds
) {
  if (commandId.length() == 0) {
    Serial.println("Command rejected: missing command ID");
    return false;
  }

  if (phaseNumber < 1 || phaseNumber > 16) {
    Serial.println("Command rejected: invalid phase number");
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

  return true;
}

// ============================================================
// Structured command parser
// ============================================================

void handleStructuredCommand(String input) {
  input.trim();

  if (!input.startsWith("CMD,")) {
    Serial.println("Command rejected: expected CMD format");
    return;
  }

  input.remove(0, 4);

  int comma1 = input.indexOf(',');
  int comma2 = input.indexOf(',', comma1 + 1);
  int comma3 = input.indexOf(',', comma2 + 1);

  if (comma1 < 0 || comma2 < 0 || comma3 < 0) {
    Serial.println("Command rejected: malformed CMD");
    return;
  }

  String commandId = input.substring(0, comma1);
  String phaseText = input.substring(comma1 + 1, comma2);
  String greenText = input.substring(comma2 + 1, comma3);
  String yellowText = input.substring(comma3 + 1);

  int phaseNumber = phaseText.toInt();
  int greenSeconds = greenText.toInt();
  int yellowSeconds = yellowText.toInt();

  if (!validateCommand(
        commandId,
        phaseNumber,
        greenSeconds,
        yellowSeconds
      )) {
    return;
  }

  pendingCommandId = commandId;
  pendingPhase = phaseNumber;

  pendingGreenTime = greenSeconds * 1000UL;
  pendingYellowTime = yellowSeconds * 1000UL;

  commandPending = true;

  Serial.println("Command accepted for safety processing");

  Serial.print("Command ID: ");
  Serial.println(pendingCommandId);

  Serial.print("Phase: ");
  Serial.println(pendingPhase);

  Serial.print("GREEN: ");
  Serial.print(greenSeconds);
  Serial.println(" seconds");

  Serial.print("YELLOW: ");
  Serial.print(yellowSeconds);
  Serial.println(" seconds");
}

// ============================================================
// Command execution
// ============================================================

void clearPendingCommand() {
  commandPending = false;

  pendingCommandId = "";
  pendingPhase = 0;
  pendingGreenTime = 0;
  pendingYellowTime = 0;
}

void processPendingCommand() {
  if (!commandPending) {
    return;
  }

  unsigned long elapsed = millis() - stateStartedAt;

  // ----------------------------------------------------------
  // GREEN
  // ----------------------------------------------------------

  if (state == GREEN) {
    if (elapsed < MIN_GREEN_TIME) {
      return;
    }

    activeYellowTime = pendingYellowTime;

    applyState(YELLOW);

    Serial.println("Command transition: GREEN -> YELLOW");
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

    Serial.println("Command transition: YELLOW -> ALL_RED");
    return;
  }

  // ----------------------------------------------------------
  // ALL RED
  // ----------------------------------------------------------

  if (state == ALL_RED) {
    if (elapsed < RED_CLEARANCE_TIME) {
      return;
    }

    activeGreenTime = pendingGreenTime;

    applyState(GREEN);

    Serial.print("Command executed: ");
    Serial.println(pendingCommandId);

    Serial.print("Executed phase: ");
    Serial.println(pendingPhase);

    clearPendingCommand();
    return;
  }

  // ----------------------------------------------------------
  // SAFE RED
  // ----------------------------------------------------------

  if (state == SAFE_RED) {
    activeGreenTime = pendingGreenTime;
    activeYellowTime = pendingYellowTime;

    applyState(GREEN);

    Serial.print("Command executed: ");
    Serial.println(pendingCommandId);

    Serial.print("Executed phase: ");
    Serial.println(pendingPhase);

    clearPendingCommand();
  }
}

// ============================================================
// Deterministic state machine
// ============================================================

void updateStateMachine() {
  unsigned long elapsed = millis() - stateStartedAt;

  if (commandPending) {
    processPendingCommand();
    return;
  }

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

  Serial.println();
  Serial.println("=================================");
  Serial.println("RoadMind Edge Controller v5");
  Serial.println("Controller + Wi-Fi + NTP");
  Serial.println("=================================");

  // Most important safety rule:
  // boot into RED.
  applyState(SAFE_RED);

  startWiFiConnection();
}

// ============================================================
// Main loop
// ============================================================

void loop() {
  // Safety controller runs continuously.
  updateStateMachine();

  // Network management runs independently.
  updateWiFi();

  // Time synchronization runs independently.
  updateTimeSync();

  // Temporary structured command interface.
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    handleStructuredCommand(input);
  }
}
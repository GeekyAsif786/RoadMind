const int RED_LED = 4;
const int YELLOW_LED = 5;
const int GREEN_LED = 6;

enum SignalState {
  SAFE_RED,
  GREEN,
  YELLOW,
  ALL_RED
};

SignalState state = SAFE_RED;

unsigned long stateStartedAt = 0;

// Safety limits
const unsigned long MIN_GREEN_TIME = 5000;
const unsigned long RED_CLEARANCE_TIME = 3000;

// Currently active phase timing
unsigned long activeGreenTime = 5000;
unsigned long activeYellowTime = 2000;

// Pending command
bool commandPending = false;

String pendingCommandId;
int pendingPhase = 0;
unsigned long pendingGreenTime = 0;
unsigned long pendingYellowTime = 0;


// --------------------------------------------------
// GPIO
// --------------------------------------------------

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


// --------------------------------------------------
// Command validation
// --------------------------------------------------

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


// --------------------------------------------------
// Structured command parser
// --------------------------------------------------

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


// --------------------------------------------------
// Execute pending command safely
// --------------------------------------------------

void processPendingCommand() {
  if (!commandPending) {
    return;
  }

  unsigned long elapsed = millis() - stateStartedAt;

  // Currently GREEN: respect minimum green.
  if (state == GREEN) {

    if (elapsed < MIN_GREEN_TIME) {
      return;
    }

    applyState(YELLOW);

    // Apply command-specific yellow timing.
    activeYellowTime = pendingYellowTime;

    Serial.println("Command transition: GREEN -> YELLOW");
    return;
  }

  // Currently YELLOW: wait for requested yellow duration.
  if (state == YELLOW) {

    if (elapsed < activeYellowTime) {
      return;
    }

    applyState(ALL_RED);

    Serial.println("Command transition: YELLOW -> ALL_RED");
    return;
  }

  // ALL_RED clearance.
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

    commandPending = false;
    pendingCommandId = "";
    pendingPhase = 0;
    pendingGreenTime = 0;
    pendingYellowTime = 0;

    return;
  }

  // SAFE_RED: start requested green phase.
  if (state == SAFE_RED) {

    activeGreenTime = pendingGreenTime;
    activeYellowTime = pendingYellowTime;

    applyState(GREEN);

    Serial.print("Command executed: ");
    Serial.println(pendingCommandId);

    Serial.print("Executed phase: ");
    Serial.println(pendingPhase);

    commandPending = false;
    pendingCommandId = "";
    pendingPhase = 0;
    pendingGreenTime = 0;
    pendingYellowTime = 0;
  }
}


// --------------------------------------------------
// Normal state machine
// --------------------------------------------------

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


// --------------------------------------------------
// Setup
// --------------------------------------------------

void setup() {
  pinMode(RED_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);

  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("RoadMind Edge Controller");
  Serial.println("Structured command mode");
  Serial.println(
    "Format: CMD,<command_id>,<phase>,<green_seconds>,<yellow_seconds>"
  );

  // Safe boot.
  applyState(SAFE_RED);
}


// --------------------------------------------------
// Main loop
// --------------------------------------------------

void loop() {
  updateStateMachine();

  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    handleStructuredCommand(input);
  }
}
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

const unsigned long GREEN_TIME = 5000;
const unsigned long YELLOW_TIME = 2000;
const unsigned long RED_CLEARANCE_TIME = 3000;

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

void updateStateMachine() {
  unsigned long elapsed = millis() - stateStartedAt;

  switch (state) {
    case SAFE_RED:
      break;

    case GREEN:
      if (elapsed >= GREEN_TIME) {
        applyState(YELLOW);
      }
      break;

    case YELLOW:
      if (elapsed >= YELLOW_TIME) {
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

void handleCommand(String command) {
  command.trim();
  command.toUpperCase();

  if (command == "GREEN") {
    applyState(GREEN);
    Serial.println("Command accepted: GREEN");
  }
  else if (command == "YELLOW") {
    applyState(YELLOW);
    Serial.println("Command accepted: YELLOW");
  }
  else if (command == "SAFE_RED") {
    applyState(SAFE_RED);
    Serial.println("Command accepted: SAFE_RED");
  }
  else {
    Serial.println("Command rejected: unknown command");
  }
}

void setup() {
  pinMode(RED_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);

  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("RoadMind Edge Controller");
  Serial.println("Commands: GREEN, YELLOW, SAFE_RED");

  // Safe boot.
  applyState(SAFE_RED);

  // Start demonstration cycle.
  applyState(GREEN);
}

void loop() {
  updateStateMachine();

  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    handleCommand(command);
  }
}
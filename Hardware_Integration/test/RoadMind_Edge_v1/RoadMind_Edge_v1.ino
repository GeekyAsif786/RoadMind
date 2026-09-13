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
  unsigned long now = millis();
  unsigned long elapsed = now - stateStartedAt;

  switch (state) {
    case SAFE_RED:
      // Stay safe on boot until explicitly changed.
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

void setup() {
  pinMode(RED_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);

  // Always boot into the safest state.
  applyState(SAFE_RED);

  // Start the automatic cycle after boot.
  applyState(GREEN);
}

void loop() {
  updateStateMachine();

  // Other work can run here later:
  // Wi-Fi
  // RoadMind polling
  // watchdog
  // command validation
}
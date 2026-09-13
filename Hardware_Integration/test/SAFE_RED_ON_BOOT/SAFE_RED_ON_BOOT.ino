const int RED_LED = 4;

enum SignalState {
  SAFE_RED,
  RED,
  GREEN,
  YELLOW
};

SignalState state = SAFE_RED;

void applyState(SignalState newState) {
  state = newState;

  switch (state) {
    case SAFE_RED:
      digitalWrite(RED_LED, HIGH);
      break;

    case RED:
      digitalWrite(RED_LED, HIGH);
      break;

    case GREEN:
      digitalWrite(RED_LED, LOW);
      break;

    case YELLOW:
      digitalWrite(RED_LED, LOW);
      break;
  }
}

void setup() {
  pinMode(RED_LED, OUTPUT);

  // On boot, always enter the safe state.
  applyState(SAFE_RED);
}

void loop() {
  // Stay in the safe state for now.
  applyState(SAFE_RED);
  delay(100);
}
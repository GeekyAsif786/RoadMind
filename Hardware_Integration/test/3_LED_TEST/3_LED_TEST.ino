const int RED_LED = 4;
const int YELLOW_LED = 5;
const int GREEN_LED = 6;

enum SignalState {
  SAFE_RED,
  GREEN,
  YELLOW,
  RED
};

SignalState state = SAFE_RED;

void allOff() {
  digitalWrite(RED_LED, LOW);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(GREEN_LED, LOW);
}

void applyState(SignalState newState) {
  state = newState;

  // Always start by turning everything off.
  allOff();

  switch (state) {
    case SAFE_RED:
    case RED:
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

void setup() {
  pinMode(RED_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);

  // Safety rule: boot into RED.
  applyState(SAFE_RED);
}

void loop() {
  // RED
  applyState(RED);
  delay(3000);

  // GREEN
  applyState(GREEN);
  delay(5000);

  // YELLOW
  applyState(YELLOW);
  delay(2000);
}
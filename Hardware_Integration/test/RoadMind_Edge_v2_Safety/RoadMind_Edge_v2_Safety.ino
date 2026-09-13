const int RED_LED = 4;
const int YELLOW_LED = 5;
const int GREEN_LED = 6;

enum SignalState {
  SAFE_RED,
  GREEN,
  YELLOW,
  ALL_RED
};

enum RequestedState {
  REQUEST_NONE,
  REQUEST_GREEN,
  REQUEST_SAFE_RED
};

SignalState state = SAFE_RED;
RequestedState requestedState = REQUEST_NONE;

unsigned long stateStartedAt = 0;

const unsigned long MIN_GREEN_TIME = 5000;
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

void requestState(RequestedState request) {
  requestedState = request;

  if (request == REQUEST_GREEN) {
    Serial.println("GREEN request received");
  }
  else if (request == REQUEST_SAFE_RED) {
    Serial.println("SAFE_RED request received");
  }
}

void processRequest() {
  if (requestedState == REQUEST_NONE) {
    return;
  }

  unsigned long elapsed = millis() - stateStartedAt;

  if (requestedState == REQUEST_GREEN) {

    if (state == GREEN) {
      requestedState = REQUEST_NONE;
      Serial.println("Already GREEN");
      return;
    }

    if (state == SAFE_RED || state == ALL_RED) {
      applyState(GREEN);
      requestedState = REQUEST_NONE;
      Serial.println("GREEN request accepted");
      return;
    }
  }

  if (requestedState == REQUEST_SAFE_RED) {

    if (state == SAFE_RED) {
      requestedState = REQUEST_NONE;
      Serial.println("Already SAFE_RED");
      return;
    }

    if (state == GREEN) {
      if (elapsed < MIN_GREEN_TIME) {
        Serial.println("SAFE_RED request waiting for minimum GREEN time");
        return;
      }

      applyState(YELLOW);
      return;
    }

    if (state == YELLOW) {
      return;
    }

    if (state == ALL_RED) {
      applyState(SAFE_RED);
      requestedState = REQUEST_NONE;
      Serial.println("SAFE_RED request accepted");
      return;
    }
  }
}

void updateStateMachine() {
  unsigned long elapsed = millis() - stateStartedAt;

  switch (state) {

    case SAFE_RED:
      break;

    case GREEN:
      if (requestedState == REQUEST_SAFE_RED) {
        processRequest();
      }
      break;

    case YELLOW:
      if (elapsed >= YELLOW_TIME) {
        applyState(ALL_RED);
      }
      break;

    case ALL_RED:
      if (elapsed >= RED_CLEARANCE_TIME) {

        if (requestedState == REQUEST_GREEN) {
          applyState(GREEN);
          requestedState = REQUEST_NONE;
          Serial.println("GREEN request accepted");
        }
        else if (requestedState == REQUEST_SAFE_RED) {
          applyState(SAFE_RED);
          requestedState = REQUEST_NONE;
          Serial.println("SAFE_RED request accepted");
        }
      }
      break;
  }
}

void handleCommand(String command) {
  command.trim();
  command.toUpperCase();

  if (command == "GREEN") {
    requestState(REQUEST_GREEN);
  }
  else if (command == "SAFE_RED") {
    requestState(REQUEST_SAFE_RED);
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
  Serial.println("Commands: GREEN, SAFE_RED");

  applyState(SAFE_RED);
}

void loop() {
  updateStateMachine();

  processRequest();

  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    handleCommand(command);
  }
}
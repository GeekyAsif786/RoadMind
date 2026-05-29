# RoadMind Hardware Integration Architecture

## Overview

This document describes the recommended hardware integration roadmap for RoadMind, starting from a software-only simulation and progressing toward a real-world intelligent traffic signal control system.

The architecture is designed to preserve the existing RoadMind backend while allowing incremental hardware upgrades.

---

# Phase 1 — Software-Controlled LED Simulation

## Objective

Validate the complete signal control workflow before introducing physical traffic hardware.

## Architecture

```text
RoadMind Backend
        │
        │ HTTP / MQTT
        ▼
      ESP32
        │
        ▼
  LED Simulation
```

## Components

### RoadMind Backend

Responsible for:

* Vehicle detection
* Traffic density calculation
* Signal optimization
* Emergency handling
* Prediction generation
* Signal plan generation

Example signal plan:

```json
{
  "intersection_id": 1,
  "north_green": 40,
  "south_green": 40,
  "east_green": 20,
  "west_green": 20
}
```

---

### ESP32

Acts as a hardware controller.

Responsibilities:

* Receive signal commands
* Interpret timing instructions
* Control GPIO pins
* Drive LED outputs

Communication methods:

* HTTP API
* MQTT (recommended)

---

### LED Simulation

Represents traffic lights using LEDs.

Each direction consists of:

```text
Red LED
Yellow LED
Green LED
```

Example:

```text
North
 ├─ Red
 ├─ Yellow
 └─ Green

South
 ├─ Red
 ├─ Yellow
 └─ Green
```

---

## Benefits

* Very low cost
* Fast prototyping
* Safe testing environment
* Complete end-to-end validation

---

# Phase 2 — Physical Signal Prototype

## Objective

Move from simple LEDs to a realistic traffic signal model.

## Architecture

```text
RoadMind Backend
        │
        │ MQTT
        ▼
      ESP32
        │
        ▼
    Relay Board
        │
        ▼
 Mini Signal Model
```

---

## Components

### RoadMind Backend

Unchanged from Phase 1.

No modifications required.

---

### MQTT Communication Layer

Recommended broker:

* Mosquitto

Communication flow:

```text
RoadMind
     │ Publish
     ▼
MQTT Broker
     │
     ▼
ESP32 Subscriber
```

Example topic:

```text
intersection/1/signal
```

Example payload:

```json
{
  "phase": "NS_GREEN",
  "duration": 40
}
```

---

### ESP32 Controller

Receives MQTT messages and controls relay outputs.

Responsibilities:

* Subscribe to traffic topics
* Decode signal plans
* Switch relays
* Monitor hardware state

---

### Relay Board

Acts as an electrical isolation layer.

Responsibilities:

* Separate ESP32 logic voltage from signal voltage
* Control larger loads safely
* Simulate industrial traffic controllers

Typical configuration:

```text
Relay 1 → North Green
Relay 2 → North Yellow
Relay 3 → North Red

Relay 4 → South Green
Relay 5 → South Yellow
Relay 6 → South Red
```

---

### Mini Signal Model

A physical traffic signal prototype.

Can be built using:

* LEDs
* Mini traffic signal kits
* Acrylic signal towers
* 3D-printed enclosures

Represents:

```text
North
South
East
West
```

traffic directions.

---

# Future Phase 3 — Industrial Deployment

## Objective

Transition RoadMind to real traffic infrastructure.

## Architecture

```text
RoadMind Backend
        │
        │ MQTT / Modbus TCP / API
        ▼
Industrial Traffic Controller
        │
        ▼
Traffic Signal Hardware
```

Examples:

* PLC Controllers
* Traffic Signal Controllers (TSC)
* NEMA Controllers
* ATC Controllers

RoadMind generates signal plans.

Industrial controllers execute them safely.

---

# Recommended Technology Stack

## Backend

* FastAPI
* PostgreSQL
* Redis
* MQTT Publisher

## Communication

* MQTT
* Mosquitto Broker

## Hardware

* ESP32
* 8-Channel Relay Board
* Breadboard
* Traffic LEDs

## Monitoring

* Prometheus
* Grafana

---

# Final Recommended Development Path

```text
Phase 1
RoadMind
    ↓
ESP32
    ↓
LED Simulation

        ↓

Phase 2
RoadMind
    ↓
MQTT
    ↓
ESP32
    ↓
Relay Board
    ↓
Mini Signal Model

        ↓

Phase 3
RoadMind
    ↓
Industrial Controller
    ↓
Real Traffic Signals
```

This roadmap allows RoadMind to evolve from a software project into a hardware-integrated intelligent traffic management platform without requiring major architectural changes to the backend.

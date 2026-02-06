# Controller Modules

This folder contains the runtime services that drive AVR field control: an MQTT
broker, a Python match controller, a Node-RED UI, and an optional event
processor for InfluxDB logging. The pieces are wired together via MQTT topics
and run via Docker Compose.

## Quick start (Docker)

From `controller_modules/`:

```sh
docker compose up --build
```

This brings up:
- `mqtt` (Mosquitto on `localhost:1883`)
- `controller` (Python match logic, publishes UI state and actuator commands)
- `nodered` (UI + operator controls on `http://localhost:1880`)

The event processor and InfluxDB services are present but commented out in
`controller_modules/docker-compose.yaml`.

## Repository map

- `controller/` - Python match controller service
  - `src/controller.py` - main loop, MQTT I/O, publishes UI and building commands
  - `src/match.py` - match state machine, scoring rules, phase timers
  - `src/buildings.py` - building state machines (fire/heater)
  - `src/mqtt_client.py` - MQTT helper with topic matching
  - `configs/config.json` - phase durations (seconds)
  - `logs/` - match result JSONs (mounted to `/logs` in container)
- `nodered/` - Node-RED UI flows and settings (stored in `nodered/data/`)
- `mqtt/` - Mosquitto config (`listener 1883`, anonymous enabled)
- `event-processor/` - optional InfluxDB event logger
  - `src/main.py` - consumes MQTT events, writes to InfluxDB
  - `src/mqtt_client.py` - MQTT helper

## How it fits together

1. **MQTT broker** provides the shared bus.
2. **Controller** subscribes to `+/events/#` and listens for:
   - Building hits (`laser_detector` / `ball_detector`) to douse fires.
   - UI events from `ui/...` to drive match state and score toggles.
3. **Controller** publishes:
   - UI state to `ui/state/...` (scores, timers, match phase, tables).
   - Building commands such as `{building}/relay/set` and
     `{building}/progress_bar/set`.
4. **Node-RED** provides the operator UI and pushes UI events to MQTT.
5. **Event processor** (optional) records MQTT events into InfluxDB.

## Controller service details

- **Match phases**: Idle -> Staging -> Phase 1 -> Phase 2 -> Phase 3 -> Post Match.
- **Timers**: `config.json` controls phase durations in seconds.
- **Buildings**:
  - Fire buildings use a two-window scoring model (ball vs. laser differ in
    initial fire levels and points per window).
  - Heater buildings run a preheat timer and are ignited during staging.
- **Logs**: When `match_id` is set and the match ends with a score, a JSON
  summary is written to `/logs/{match_id}.json` (mounted to
  `controller/logs/`).

## MQTT topic notes

The controller uses a simple topic layout:
- **Incoming events**: `+/events/#`
  - Example: `1/events/laser_detector` with `{"event_type":"hit"}`
  - Example: `ui/events/...` with `{"event_type":"ui_toggle","data":{...}}`
- **UI state**: `ui/state/*`
  - Examples: `ui/state/score`, `ui/state/match_state`,
    `ui/state/table_data`, `ui/state/phase_remaining`
- **Building commands**:
  - `"{building}/relay/set"` with `{"channel":"window1","state":"on"}`
  - `"{building}/progress_bar/set"` with `{"pixel_data":[...]}`

The current controller uses building IDs `"1"`-`"9"` for fire/heater logic.
The event-processor's `BUILDINGS` list is `"A"`-`"I"`; keep this in mind if you
enable it.

## Node-RED UI

Flows and dashboard settings are stored in `controller_modules/nodered/data/`.
When you edit flows in the Node-RED UI, these JSON files update in place and
are mounted into the container for persistence.

## Event processor (optional)

The event processor writes MQTT events to InfluxDB. The compose services for
InfluxDB and the event processor are commented out by default. If you enable
them, verify the InfluxDB credentials and bucket/org names in:
- `controller_modules/event-processor/src/main.py`
- `controller_modules/docker-compose.yaml`

## Development notes

- Python services target Python 3.10 and install dependencies via
  `requirements.txt` in each service folder.
- The controller reads `config.json` from `/configs/` (mounted in compose).
- If you run services outside Docker, set MQTT host/port accordingly (defaults
  to `mqtt:1883` inside the compose network).

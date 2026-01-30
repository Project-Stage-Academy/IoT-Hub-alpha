1. [Overview](#1-overview)
2. [Features](#2-features)
3. [Architecture](#3-architecture)
4. [Installation](#4-installation)
5. [Configuration](#5-configuration)
6. [Usage](#6-usage)
7. [Logging](#7-logging)
8. [Examples](#8-examples)
9. [Limitations](#9-limitations)




## `1) Overview`

### [Video Guide](https://youtu.be/2D-JnWzfibI)

The Telemetry Ingest Simulator is a CLI tool used to send telemetry payloads to an ingest API.

It is intended for:

- load testing
- schema validation
- demo runs on a clean stack
- ingestion debugging

The simulator supports rate-limited execution, finite or infinite runs, expected vs actual HTTP status code comparisons, demo runs and structured logging.

## `2) Features`
- HTTP telemetry ingestion
- Finite/infinite execution mode
- JSONL logging
- Verbose console output

Device / file operating modes:
- device mode for continuous debugging or live data dumps
- file mode for deterministic demo runs

MQTT mode is currently a stub (see [Limitations](#9-limitations)).

## `3) Architecture`
```
Task Source -> Sender -> Runner -> Reporter
```

| Components | Responsibility |
|-------------|--------------|
|Task source | Loads payloads from config / demo files|
|Sender | Sends payload via HTTP or MQTT |
|Runner | Controls pacing, looping and counting |
|Reporter | Handles console and file outputs|

## `4) Installation`
Requirements:
- Python 3.10+
- pip

Install dependencies:
```
pip install -r requirements-dev.txt
```

## `5) Configuration`
The simulator is critically dependent on config.simulator.json and will NOT function without it. The file is expected at `/simulator/config.simulator.json`.

The simulator can also load demo payloads located in `/docs/demos/`. These are not strictly required. and the simulator can run without it when using devices.

config.simulator.json example:
```json
{
    "default_url": "https://iot-industry.redocly.app/_mock/openapi/telemetry",
    "default_data_file": [
        "Demo1.json",
        "Demo2.json",
        "Demo3.json"
    ],
    "default_timeout": 5,
    "log_file": "sim_log.jsonl",
    "devices": [
        {
            "name": "device1",
            "data": {
                "schema_version": "1.0",
                "ssn": "SN2221144",
                "value": 2652
            },
            "expected": 202
        },
        {
            "name": "device2",
            "data": {
                "schema_version": "1.0",
                "ssn": "SN2225555",
                "value": 3244
            },
            "expected": 202
        }
    ]
}
```
### Config fields:
|Field            | Usage                  | Example |
|-----------------|------------------------|---------|
|default_url | Full ingest Api endpoint | http://127.0.0.1:8000/api/v1/telemetry |
|default_data_file| full name(case sensitive) or demo files located in /docs/demos, must be a list | [Demo1.json, Demo2.json] |
|default_timeout | timeout time in seconds (can accept floats) | 2.5 |
|log_file| logfile name in jsonl format to which logging will be written (if enabled in CLI) | sim_log.jsonl |
|devices| a list of device objects (breakdown below) | |

### device field breakdown:
|Field            | Usage                  | Example |
|-----------------|------------------------|---------|
|name | device name, this will NOT be included in the payload and is used ONLY for console/log output | device1 |
|data | contains payload, further explanation below | |
|expected | expected status code returned for payload | 200|

### Data(Actually sent payload) field structure
This describes the minimal payload structure for `schema_version` 1.0.0.
any further schema will have additional fields
|Field            | Usage                  | Example |
|-----------------|------------------------|-------------|
|schema_version | Schema version of the sent data, used for validation on backend (Sent as string)| "1.0" |
|ssn | Serial number of the device (str)| SN-222111|
|value| Actual value sent by device (Could be int/float depending on schema)| 3452 |


## `6) Usage`
Basic run (HTTP mode, using default demo files from config)
```
python -m simulator.run
```
Using docker compose
```
docker compose run --rm simulator.run
```
Infinite mode
```
python -m simulator.run -d device1 -c 0
```


### CLI Options
|quick flag | flag| Description | Default value|
|-----------|-----|-------------|--------------|
|-d | --devices (str)| select 1 or more devices from the config to run | None|
| -f| --files (str) | select 1 or more files from /docs/demos to run | default value is loaded from config|
|-c| --count (int)| count of task loops, multiplicative with multiple tasks | 1 |
|-m| --mode ("http"/"mqtt")|  select http or mqtt sender | http |
|-r| --rate(float)| delay between requests in seconds | 0.7 |
|-v| --verbose(flag) | enables verbose mode in console output | False |
|-l| --log(flag) | enables logging to the file specified in config (`log_file`) | False|

## `7) Logging`
Logs are written in JSON Lines (JSONL) format.
```
{"ts": "2026-01-20T11:57:44.502524+00:00", "device": "device1", "status": "Pass", "expected": 202, "got": 202, "latency": 141.0}
```
- each line is a standalone json object

## `8) Examples`

Run tasks located in Demo1.json file, with verbose and log enabled 5 times with a delay of 0.5 seconds:
```
python -m simulator.run -f Demo1.json -v -l -c 5 -r 0.5
```

Run device1 (located in config) continuously with a delay of 1 second with no verbose console output and no file logging:
```
python -m simulator.run -d device1 -c 0 -r 1
```

## `9) Limitations`

- MQTT mode is not implemented yet

- No retry or backoff logic

- No parallel execution

- HTTP only supports POST

## `10) Simulator dependencies`

The telemetry simulator relies only on a minimal subset of dependencies.
These are documented in:

requirements-dev.txt

Required for simulator execution:
- pydantic
- requests

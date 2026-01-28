API Style Guide (Industry 4.0)

## Table of Contents

1. [Obtaining a JWT Token for testing](#1-obtaining-a-jwt-token-for-testing)
2. [Overview](#2-overview)
3. [Standards & Tooling](#3-standards--tooling)
4. [URL Design](#4-url-design)
5. [HTTP Methods & Semantics](#5-http-methods--semantics)
6. [Request & Response Format](#6-request--response-format)
7. [Authentication & Authorization](#7-authentication--authorization)
8. [Pagination](#8-pagination)
9. [Errors](#9-errors)
10. [Create / Update Patterns](#10-create-update-patterns)
11. [Resource Representations](#11-resource-representations)
12. [Filtering, Searching, Sorting](#12-filtering-searching-sorting)
13. [Security Requirements](#13-security-requirements)
14. [Deprecation Policy](#14-deprecation-policy)
15. [Documentation Rules](#15-documentation-rules)


## `1) Obtaining a JWT Token for testing`

- curl / call / postman the following endpoint:

`https://iot-industry.redocly.app/_mock/openapi/auth/fake`

Copy the token and insert it into the header as described in chapter [Authentication & Authorization](#7-authentication--authorization)

## `2) Overview`

- API name: IoT Industry

- Owner/team: alpha team

- Audience/consumers: API

- API style: REST / JSON

Primary goals: To create a RESTful API alongside Ingest API for telemetry gathering from machine sensors

## `3) Standards & Tooling`

Spec format: OpenAPI 3.0.3

Docs location: [Industry ReDocly](https://iot-industry.redocly.app)

Postman: [Collection](IoTIndustry.postman_collection) | [Workspace](https://app.getpostman.com/join-team?invite_code=dd81ab120ddf5fc4e2e04b31ec1bb07004b4fa89e26caad2d004bde97e76a257&target_code=e0949259bdabcd7186883424baab71c6)

(Curl, python requests examples can be found on [Industry ReDocly](https://iot-industry.redocly.app).)

Linting rules: redocly.yaml in root


## `4) URL Design`
#### `4.1 Base Path & Versioning`

Versioning approach: URL/Header hybrid approach

- URL versioning /api/v1/...

- header-based (schema_version) is used for telemetry data submition to ingest endpoint

Rule for introducing v2: TBD, anything that would break previous functionality

Deprecation policy: None at the moment as we are dealing with hardware

#### `4.2 Resource Naming`

Use nouns, plural collections: /telemetry, /devices

Use snake_case in URLs

Nested resources only when it’s a true hierarchy:

Example: /devices/{id}

#### `4.2 Query Parameters`

Filtering: .../?status=active

Sorting: .../?sort=created_at


## `5) HTTP Methods & Semantics`

GET — read

POST — create

## `6) Request & Response Format`
#### `6.1 Content Types`

Requests: Content-Type: application/json

Responses: application/json

#### `6.2 JSON Conventions`

Field naming: snake_case

Dates/times: ISO 8601, timezone: UTC

Booleans: true/false

#### `6.3 Envelope`

Envelopes present on pagination, for more information go to [Pagination](#8-pagination)

### `6.4 Telemetry Ingest Example`

Request:
```http
POST /api/v1/telemetry
Content-Type: application/json
X-Device-Serial-Number: SN2224412
```
```json
{
  "value": 2432,
  "schema_version": "1.0"
}
```

Rules:
- `X-Device-Serial-Number` header is REQUIRED
- Device identifiers MUST NOT appear in the request body
- Requests missing the header MUST return `400 Bad Request`

## `7) Authentication & Authorization`

Auth type: JWT

How to send(Header): 
```
Authorization: Bearer <token>
```
Scopes/roles model: TODO

Permissions rules: TODO (who can read/write which resources)

Token expiry/refresh: 

- 60 min for access token
- 10 days for refresh token

Example:
```http
GET /api/v1/devices
Authorization: Bearer <token>
```

### Telemetry ingest endpoint (POST /telemetry)

The telemetry ingest endpoint **does NOT require JWT authentication**.

Device identity is provided via the request header:

X-Device-Serial-Number

The backend validates the device based on this header value.

```
POST /api/v1/telemetry
X-Device-Serial-Number: SN2224412
Content-Type: application/json
```

## `8) Pagination`

### Overview
All endpoints that return **collections** MUST support pagination and MUST return results in a **pagination envelope** (response wrapper) to provide consistent metadata for clients.

This API uses **page-based pagination** (`page`, `page_size`) with a standard response envelope:

- `data`: the list of returned items
- `pagination`: metadata about the current page and the overall result set

---

### Applicable endpoints
Pagination applies to collection endpoints such as:

- `GET /api/v1/devices`
- `GET /api/v1/telemetry`

---

### Request parameters

| Parameter | In | Type | Default | Constraints | Description |
|----------|----|------|---------|-------------|-------------|
| `page` | query | integer | `1` | min `1` | Page number (1-based) |
| `page_size` | query | integer | `10` | min `1`, max `1000` | Number of items per page |

**Rules**
- `page` MUST be **>= 1**
- `page_size` MUST be **between 1 and 1000**
- If omitted, defaults MUST apply (`page=1`, `page_size=10`)
- Invalid values MUST return `400 Bad Request`

---

### Response envelope

|Field |	Type |	Description|
|---------|-------|--------------------------------------------------|
|page |	integer |	Current page number|
|page_size |	integer |	Page size used for this response|
|total |	integer | Total number of items matching the query (after filters)|
|total_pages |	 integer |	Total pages available (ceil(total / page_size))|
|next_page |	integer or null	| Next page number if available, else null|
|prev_page |	integer or null	| Previous page number if available, else null|

All paginated collection responses MUST follow this structure:

```json
{
  "data": [],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total": 0,
    "total_pages": 0,
    "next_page": null,
    "prev_page": null
  }
}
```

### Rules

data *MUST* be an array (never null)

total *MUST* reflect the total items for the current filter set

total_pages *MUST* be consistent with total and page_size

next_page / prev_page *MUST* be null when not available


### Example

```
GET /api/v1/devices?page=1&page_size=2
Authorization: Bearer <token>
```
```
{
  "data": [
    {
      "name": "Thermometer lower level 5",
      "ssn": "SN2224412",
      "location": "Industrial park 15",
      "status": "Paused",
      "created": "2026-01-16T14:30:00Z",
      "updated": "2026-01-16T17:30:00Z"
    },
    {
      "name": "Thermometer upper level 2",
      "ssn": "SN2224413",
      "location": "Industrial park 15",
      "status": "Active",
      "created": "2026-01-16T14:35:00Z",
      "updated": "2026-01-16T17:31:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 2,
    "total": 11,
    "total_pages": 6,
    "next_page": 2,
    "prev_page": null
  }
}
```

### Edge Cases
When no match is found in filtering return
```
{
  "data": [],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total": 0,
    "total_pages": 0,
    "next_page": null,
    "prev_page": null
  }
}
```

### Error handling
Incase of an error, return 400(Bad request) with standard error format.

## `9) Errors`
8.1 Status Codes

Use:

200 OK (read success)

201 Created (create success)

202 Accepted (Accepted for async telemetry operations)

400 Bad Request (validation, malformed)

401 Unauthorized

403 Forbidden

404 Not Found

500/503 server issues

### `9.1 Error Response Format`

Standard shape:
```
{
    "error" : "An error has occured"
}
```
## `10) Create Update Patterns`

Create returns: 201 + created resource (or location header) 

Telemetry POST requests return `202 Accepted` with no response body.

The device identity MUST be provided via the `X-Device-Serial-Number` header.
The request body MUST contain only telemetry data (no device identifiers).

## `11) Resource Representations`

- JSON objects use snake_case

- Arrays are returned for collections

- Fields are explicitly defined (no magic / undocumented fields)

- Avoid abbreviations unless domain-standard (id, ts)

Device serial numbers are NOT included in telemetry request bodies.
They are provided via the `X-Device-Serial-Number` request header.

### Common type representation

- Timestamps - ISO 8601 (date-time)

- Numbers - integers are used for telemetry data which may represent floats
for example, a thermometer will send its value(31.4) in such a way:

Headers:
```
"X-Device-Serial-Number": "SN222331"
```
Body:
```
{
"value": 3140
}
``` 

- IDs - UUID for all API operations

## `12) Filtering, Searching, Sorting`

Note:
The device serial number MAY be included in telemetry responses for identification purposes.
However, it MUST NOT be included in telemetry POST request bodies.

Resource access is currently supported on:
- devices endpoint using a url parameter of {id}
```
GET .../api/v1/devices/a1b2c3d4-e5f6-7890-1234-567890abcdef
```
``` json
{
    "name": "Themometer lower level 5",
    "ssn": "SN2224412",
    "location": "Industrial park 15",
    "status": "Paused",
    "created": "2026-01-16T14:30:00Z",
    "updated": "2026-01-16T17:30:00Z"
}
```
Filtering is currently supported on: 
- telemetry endpoint using query parameters:
```
GET .../api/v1/telemetry?device_id=a1b2c3d4-e5f6-7890-1234-567890abcdef
```
``` json
{
    "data": [
        {
            "ssn": "SN2224412",
            "value": 2432,
            "metric": "C",
            "ts": "2026-01-16T22:53:00Z"
        },
        {
            "ssn": "SN2224412",
            "value": 2432,
            "metric": "C",
            "ts": "2026-01-16T22:53:00Z"
        }
    ],
    "pagination": {
        "page": 2,
        "page_size": 2,
        "total": 2,
        "total_pages": 1,
        "next_page": null,
        "prev_page": null
    }
}
```

## `13) Security Requirements`

TLS only: yes

Audit logging: TODO

## `14) Deprecation Policy`

How endpoints are deprecated: Endpoints are never deprecated as it is a IoT system

How clients are notified: Changelog

Deprecation: false

## `15) Documentation Rules`

For every endpoint, document:

Purpose

Auth requirements

Request/response examples

Error cases (at least 2–3 common ones)

Field descriptions + constraints

Pagination (if applicable)

(see [Industry ReDocly](https://iot-industry.redocly.app) for examples)
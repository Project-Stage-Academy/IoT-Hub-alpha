Style guide:

## `0) Obtaining a JWT Token for testing`

- curl / call / postman the following endpoint:

`https://iot-industry.redocly.app/_mock/openapi/auth/fake`

Copy the token and insert it into the header as described in chapter `6) Authentication & Authorization`

API Style Guide (Industry 4.0)
## `1) Overview`

- API name: Api Owner

- Owner/team: industry

- Audience/consumers: API

- Base URL(s): TODO

- Prod: https://TODO

- Staging: https://TODO

- API style: REST / JSON

Primary goals: To create a restful API alongside Ingest API for telemetry gathering from machine sensors

## `2) Standards & Tooling`

Spec format: OpenAPI 3.0.3

Docs location: [Industry ReDocly](https://iot-industry.redocly.app)

Postman wrokspace: [Workspace](https://app.getpostman.com/join-team?invite_code=dd81ab120ddf5fc4e2e04b31ec1bb07004b4fa89e26caad2d004bde97e76a257&target_code=e0949259bdabcd7186883424baab71c6)

(Curl, python requests etc' examples can be found on ReDocly.)

Linting rules: Spectral ruleset link TODO


## `3) URL Design`
3.1 Base Path & Versioning

Versioning approach: URL/Header hybrid approach

- URL versioning /api/v1/...

- header-based (content negotiation) for telemetry data

Rule for introducing v2: TBD, anything that would break previous functionality

Deprecation policy: None at the moment as we are dealing with hardware

#### `3.2 Resource Naming`

Use nouns, plural collections: /telemetry, /devices

Use snake_case in URLs

Nested resources only when it’s a true hierarchy:

Example: /devices/{id}

#### `3.3 Query Parameters`

Filtering: .../?status=active

Sorting: .../?sort=created_at

Pagination: [Industry ReDocly](https://iot-industry.redocly.app).

## `4) HTTP Methods & Semantics`

GET — read

POST — create

## `5) Request & Response Format`
5.1 Content Types

Requests: Content-Type: application/json

Responses: application/json

#### `5.2 JSON Conventions`

Field naming: snake_case

Dates/times: ISO 8601, timezone: UTC

Booleans: true/false

#### `5.3 Envelope`

no envelope:

{ "ssn": 123321, "value": 2342 }

## `6) Authentication & Authorization`

Auth type: JWT

How to send(Header): Authorization: Bearer `<token>`

Scopes/roles model: TODO

Permissions rules: TODO (who can read/write which resources)

Token expiry/refresh: TODO

Example:
```http
GET /api/v1/devices
Authorization: Bearer <token>
```

## `7) Pagination`

See [Industry ReDocly](https://iot-industry.redocly.app) for pagination rules

## `8) Errors`
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

## `8.2 Error Response Format`

Standard shape:

{
    "error" : "An error has occured"
}

## `9) Create/Update Patterns`

Create returns: 201 + created resource (or location header) With telemetry exception, which returns 202 with no body

## `10) Resource Representations`

IDs are not exposed at all at this point in the API

## `11) Filtering, Searching, Sorting`

Please refer to [Industry ReDocly](https://iot-industry.redocly.app) for max per page and pagination rules

## `12) Security Requirements`

TLS only: yes

Audit logging: TODO

## `13) Deprecation Policy`

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
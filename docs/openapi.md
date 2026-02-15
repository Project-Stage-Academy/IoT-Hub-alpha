## 1. Modify the spec

Edit:
```
docs/api.yaml
```

Guidelines:

- Keep paths REST-consistent
- Provide request/response examples
- Always define schemas under components/schemas
- Ensure all endpoints include:
    - summary
    - operationId
    - responses
    - security (if required)

## 2. Validate locally

Run:
```
scripts/validate-openapi.sh
```

This will:

- Lint the spec (Redocly)
- Validate structure
- Catch schema errors early

If validation fails, fix errors before committing.

## Regenerate postman collections

Postman collections can be regenerated from the api.yaml file like so:
- Open postman
- Import docs/api.yaml (File -> Import or  Ctrl + O)
- Export json to (... -> More -> Export -> Continue with Export -> Export JSON)
```
docs/postman/postman_collection.json
```

validate api + collection:
This script validate OpenApi lint and check collection contract against a local prism server.

```
scripts/validate-openapi.sh
```

## 3. UI and prism local server.

Redocly UI for endpoints can be accessed here:

[Industry 4.0](https://iot-industry.redocly.app)

for local testing purposes Prism can be use to generate mock endpoints:

install prism:
```
npm install -g @stoplight/prism-cli
```

start mock server:
```
npx @stoplight/prism-cli mock docs/api.yaml
```

## 4. Deprecation
## API change process, versioning, and deprecation

The OpenAPI spec follows explicit versioning rules and a consistent deprecation annotation pattern.
These rules are documented in `docs/api-change-process.md` and must be followed for every API change.

**Goal:** breaking changes are never introduced silently.
Any breaking change must be versioned, documented, and clearly marked as deprecated (with timelines and migration guidance).
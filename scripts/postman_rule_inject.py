import json
import sys

path = sys.argv[1]

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

if "event" not in data:
    data["event"] = []

for event in data["event"]:
    if event["listen"] == "test":
        exit(0)

data["event"].append({
    "listen": "test",
    "script": {
        "type": "text/javascript",
        "exec": [
            "pm.test('Status is 2xx', function () {",
            "  pm.expect(pm.response.code).to.be.within(200, 299);",
            "});"
        ]
    }
})

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Injected global 2xx test into collection")

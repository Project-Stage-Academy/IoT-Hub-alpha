import os

TELEMETRY_RETENTION_DAYS = int(os.getenv("TELEMETRY_RETENTION_DAYS", "90"))

# Number of recent telemetry records shown on Device detail page in admin
DEVICE_TELEMETRY_INLINE_LIMIT = int(os.getenv("DEVICE_TELEMETRY_INLINE_LIMIT", "10"))

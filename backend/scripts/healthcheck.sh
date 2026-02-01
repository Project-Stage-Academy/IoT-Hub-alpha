#!/bin/bash
# Health check script for container orchestration
# Performs both liveness and readiness checks
# Exit 0 = healthy, Exit 1 = unhealthy

set -e

# Liveness probe: Check if HTTP endpoint responds
# This ensures the Django application process is running
if ! curl -f http://localhost:8000/health/ > /dev/null 2>&1; then
    echo "Liveness check failed: HTTP health endpoint not responding"
    exit 1
fi

# Readiness probe: Check if database connectivity is available
# This ensures the application is ready to handle requests
if ! curl -f http://localhost:8000/ready/ > /dev/null 2>&1; then
    echo "Readiness check failed: Database not available or connection failed"
    exit 1
fi

echo "Health checks passed: Service is healthy and ready"
exit 0

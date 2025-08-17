#!/bin/bash
# Docker health check script

# Set timeout for the health check
TIMEOUT=30

# Function to check if the service is ready
check_health() {
    # First check if the service is responding at all
    if curl -f --max-time $TIMEOUT http://localhost:8000/ > /dev/null 2>&1; then
        # Then check if it's ready to serve requests
        if curl -f --max-time $TIMEOUT http://localhost:8000/health/ready | grep -q "READY"; then
            echo "Service is healthy and ready"
            exit 0
        else
            echo "Service is responding but not ready"
            exit 1
        fi
    else
        echo "Service is not responding"
        exit 1
    fi
}

# Run the health check
check_health

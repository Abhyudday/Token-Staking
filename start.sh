#!/bin/bash

# Startup script for the Telegram Bot application

echo "Starting Telegram Bot application..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed or not in PATH"
    exit 1
fi

# Check if required files exist
if [ ! -f "main.py" ]; then
    echo "Error: main.py not found"
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    echo "Error: requirements.txt not found"
    exit 1
fi

# Install dependencies if needed
echo "Installing dependencies..."
pip3 install -r requirements.txt

# Set environment variables if not set
export ENVIRONMENT=${ENVIRONMENT:-"production"}
export PORT=${PORT:-"8000"}

echo "Environment: $ENVIRONMENT"
echo "Port: $PORT"

# Start the application
echo "Starting application..."
python3 main.py

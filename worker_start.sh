#!/bin/bash

# This script is used to start the worker process with proper environment variables
# and ensure it restarts if it crashes

echo "Starting portfolio history worker..."
echo "Current time: $(date)"
echo "Environment: $RAILWAY_ENVIRONMENT"

# Set environment variables for the worker
export HISTORY_INTERVAL_SECONDS=${HISTORY_INTERVAL_SECONDS:-3600}  # Default to 1 hour
export INITIAL_DELAY_SECONDS=${INITIAL_DELAY_SECONDS:-30}  # Default to 30 seconds

echo "Worker will run with:"
echo "- Interval: $HISTORY_INTERVAL_SECONDS seconds"
echo "- Initial delay: $INITIAL_DELAY_SECONDS seconds"

# Start the worker with automatic restart
while true; do
  echo "Starting worker process at $(date)"
  python worker.py
  
  # If the worker exits, log the event and restart after a delay
  echo "Worker process exited at $(date). Restarting in 60 seconds..."
  sleep 60
done

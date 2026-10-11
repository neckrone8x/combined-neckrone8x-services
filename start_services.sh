#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Start Nginx (the traffic cop) in the background
service nginx start

# Start the Weather API on port 3000
cd /app/weather-api
PORT=3000 python app.py &

# Start the Mkuu AI app on port 3001
cd /app/mkuu-ai
uvicorn app.main:app --host 0.0.0.0 --port 3001 &

# Start the Stories Backend on port 3002
cd /app/Neckrone8x-Stories-Backend
PORT=3002 python app.py &

# Wait for any process to exit (keeps the container running)
wait -n

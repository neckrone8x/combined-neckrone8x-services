#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Start Nginx (the traffic cop) in the background
service nginx start

# Start the Weather API in the background
cd /app/weather-api
python app.py &

# Start the Mkuu AI app in the background
cd /app/mkuu-ai
python main.py & 

# Start the Stories Backend in the background
cd /app/Neckrone8x-Stories-Backend
python app.py &

# Wait for any process to exit (keeps the container running)
wait -n

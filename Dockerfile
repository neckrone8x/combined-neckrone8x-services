# Use a base image that has both Python and Node.js installed
FROM nikolaik/python-nodejs:python3.11-nodejs20

# Set the working directory inside the container
WORKDIR /app

# Install Nginx (the traffic cop)
RUN apt-get update && apt-get install -y nginx

# Copy all your project files into the container
COPY . .

# Install dependencies for Weather API
WORKDIR /app/weather-api
RUN pip install -r requirements.txt

# Install dependencies for Stories Backend
WORKDIR /app/Neckrone8x-Stories-Backend
RUN pip install -r requirements.txt

# Install dependencies for Mkuu AI
WORKDIR /app/mkuu-ai
RUN pip install --upgrade pip
RUN pip install .
RUN pip install fastapi uvicorn

# Copy the Nginx and startup configurations we will create next
COPY nginx.conf /etc/nginx/nginx.conf
COPY start_services.sh /app/start_services.sh
RUN chmod +x /app/start_services.sh

# Expose the port Render expects
EXPOSE 10000

# Run the startup script
CMD ["/app/start_services.sh"]

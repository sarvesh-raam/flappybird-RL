# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Install a comprehensive set of system dependencies for OpenCV, Pygame, and Gymnasium
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libsdl2-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements FIRST to leverage Docker cache
COPY requirements.txt .

# Install dependencies one-by-one to avoid memory crashes on small servers
RUN pip install --no-cache-dir numpy gymnasium pygame
RUN pip install --no-cache-dir opencv-python gunicorn
RUN pip install --no-cache-dir stable-baselines3[extra] flappy-bird-gymnasium

# Copy the rest of the application code
COPY . .

# Expose the port
EXPOSE 5000

# Start the app
CMD ["python", "app.py"]

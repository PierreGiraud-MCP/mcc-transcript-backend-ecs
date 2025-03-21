FROM python:3.11

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    python3-dev \
    libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port
EXPOSE 5001

# Run the application
CMD ["python", "run.py"]
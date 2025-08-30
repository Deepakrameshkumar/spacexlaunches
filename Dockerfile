# Use a lightweight Python base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements file (if you have one) or install dependencies directly
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY main.py .
COPY json_dump.json .  # Include cached JSON file if used in testing
# Copy .env file for environment variables
COPY .env .

# Set environment variable to ensure Python output is not buffered
ENV PYTHONUNBUFFERED=1

# Command to run the application
CMD ["python", "main.py"]
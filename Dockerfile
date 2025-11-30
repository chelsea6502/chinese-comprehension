# Use Python 3.9 slim image for smaller size
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy Chinese model
RUN python -m spacy download zh_core_web_sm

# Create necessary directories (volumes will mount here)
RUN mkdir -p input known unknown

# Copy application files (only what's needed to run)
COPY script.py .
COPY definitions.txt .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the script
CMD ["python", "script.py"]
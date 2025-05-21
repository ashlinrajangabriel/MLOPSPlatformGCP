FROM python:3.8-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy feature store code
COPY feature_store/ /app/feature_store/

# Set environment variables
ENV FEAST_FEATURE_SERVER_TYPE=python
ENV FEAST_FEATURE_SERVER_PORT=8666

# Expose port
EXPOSE 8666

# Start feature server
CMD ["feast", "serve", "--host", "0.0.0.0", "--port", "8666"] 
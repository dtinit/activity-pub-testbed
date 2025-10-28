# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
ENV APP_HOME /app
WORKDIR $APP_HOME

# Removes output stream buffering, allowing for more efficient logging
ENV PYTHONUNBUFFERED 1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy local code to the container image
COPY . .

# Run the web service on container startup
# Cloud Run sets the PORT environment variable
# Gunicorn configuration:
# - capture-output: Capture stdout/stderr in logs
# - bind: Listen on all interfaces on the PORT provided by Cloud Run
# - workers: 1 worker process (Cloud Run handles scaling)
# - threads: 8 threads per worker (for handling concurrent requests)
# - timeout: 0 (no timeout, Cloud Run handles this)
CMD exec gunicorn --capture-output --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 testbed.wsgi

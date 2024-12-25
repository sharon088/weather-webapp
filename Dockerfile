# Stage 1: Build the application
FROM python:3-slim AS build

# Install dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip --no-cache-dir
RUN pip install -r requirements.txt --no-cache-dir

# Stage 2: Runtime environment
FROM python:3-slim AS runtime

# Set environment variables (you can override BG_COLOR in docker-compose or at runtime)
ENV BG_COLOR "#f0f0f0"

# Create directories for logs and set permissions
RUN mkdir -p /var/log/flask /var/log/gunicorn
RUN chmod -R 755 /var/log/flask /var/log/gunicorn

# Set working directory for the app
WORKDIR /app

# Copy only the necessary files (installed dependencies and app code) from the build stage
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . .

# Expose the port for Gunicorn
EXPOSE 8000

# Start Gunicorn and configure logging
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "wsgi:app", "--access-logfile", "/var/log/gunicorn/access.log", "--error-logfile", "/var/log/gunicorn/error.log"]

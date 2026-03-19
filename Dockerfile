FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create a non-root user for security
RUN useradd -m -r appuser

# Only copy what's needed for installation first to maximize caching
COPY requirements.txt .

# psycopg2-binary, lxml, and other dependencies in requirements.txt have precompiled wheels for python 3.11 slim
# so we don't need heavy build-essential or libpq-dev packages.
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the necessary application source code
COPY src/ ./src/
COPY config/ ./config/
# If there are any other configuration files needed, copy them here
# COPY pyproject.toml .

# Set permissions
RUN chown -R appuser:appuser /app

USER appuser

# Execute the application
ENTRYPOINT ["python", "-m", "src.main"]

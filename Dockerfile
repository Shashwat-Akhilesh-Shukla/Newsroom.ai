# ==========================================
# STAGE 1: Build the Vite React Frontend
# ==========================================
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend

# Copy Node dependency definitions
COPY frontend/package.json ./
# Install dependencies
RUN npm install

# Copy the rest of the frontend source
COPY frontend/ ./
# Build the production static assets into /app/frontend/dist
RUN npm run build


# ==========================================
# STAGE 2: Build the FastAPI Python Backend
# ==========================================
FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create a non-root user for security
RUN useradd -m -r appuser

# Install system dependencies if necessary (slim mostly has what we need)
# (Any apt-get install commands would go here)

# Optimize caching by installing pip requirements first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code and config
COPY src/ ./src/
COPY config/ ./config/

# Ensure output directory exists (for generated artifacts)
RUN mkdir -p /app/output

# Copy the built Vite frontend assets from Stage 1 into the location
# expected by FastAPI (src/api/server.py mounts this directory)
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Set correct ownership for the non-root user
RUN chown -R appuser:appuser /app
USER appuser

# Render dynamically injects $PORT. We expose 8000 for local docker-compose.
EXPOSE 8000

# Execute uvicorn server directly to respect $PORT and start FastAPI
# We use shell form to evaluate the $PORT environment variable if injected by Render
CMD ["sh", "-c", "uvicorn src.api.server:app --host 0.0.0.0 --port ${PORT:-8000}"]

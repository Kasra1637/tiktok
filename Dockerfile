# Stage 1: Build React frontend
FROM node:18-slim AS builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/yarn.lock* ./
RUN yarn install --frozen-lockfile || yarn install

COPY frontend/ ./

# Build with empty BACKEND_URL so API calls use same-origin
RUN REACT_APP_BACKEND_URL="" yarn build


# Stage 2: Python runtime with backend + built frontend
FROM python:3.11-slim AS runtime

# Install ffmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Install yt-dlp via pip (ensures latest version)
RUN pip install --no-cache-dir yt-dlp

# Copy backend source
COPY backend/ /app/backend/

# Copy built frontend from builder stage
COPY --from=builder /app/frontend/build /app/frontend_build/

# Expose the application port
EXPOSE 8080

# Run from backend directory so uvicorn can find server:app
WORKDIR /app/backend

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}"]

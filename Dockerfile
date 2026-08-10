# Stage 1: Build React frontend
FROM node:20-slim AS builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/yarn.lock* ./
RUN yarn install --frozen-lockfile || yarn install

COPY frontend/ ./

# Create React App inlines REACT_APP_* variables at BUILD time, so anything
# the browser needs must be present here — not just in the runtime container.
# Pass the Clerk key with either:
#   docker build --build-arg REACT_APP_CLERK_PUBLISHABLE_KEY=pk_live_...
# or, on Render, by declaring it as an Environment Variable (Render forwards
# service env vars to the build as --build-arg automatically).
#
# If it's absent the app still builds and runs, just with sign-in disabled
# (see frontend/src/lib/clerk.js) rather than rendering a blank page.
ARG REACT_APP_CLERK_PUBLISHABLE_KEY=""

# Build with empty BACKEND_URL so API calls use same-origin
RUN REACT_APP_BACKEND_URL="" \
    REACT_APP_CLERK_PUBLISHABLE_KEY="$REACT_APP_CLERK_PUBLISHABLE_KEY" \
    yarn build && \
    if [ -n "$REACT_APP_CLERK_PUBLISHABLE_KEY" ]; then \
      echo "Clerk key baked into frontend build."; \
    else \
      echo "WARNING: REACT_APP_CLERK_PUBLISHABLE_KEY not set — auth disabled in this build."; \
    fi


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

# Ensure storage directories exist (videos/frames/uploads/generated/templates/db)
RUN mkdir -p /app/backend/storage/videos /app/backend/storage/frames \
             /app/backend/storage/uploads /app/backend/storage/generated \
             /app/backend/storage/templates

# IMPORTANT: This RUN instruction MUST change value on every deploy where
# frontend code changed. It busts Docker BuildKit's runtime stage cache
# which otherwise reuses the old COPY --from=builder output independently
# of whether the builder stage produced new files.
RUN echo "FRONTEND_VERSION=hookflow-v4-seedream-2026-08-10" > /tmp/frontend_version.txt
COPY --from=builder /app/frontend/build /app/frontend_build/

# Expose the application port
EXPOSE 8080

# Run from backend directory so uvicorn can find server:app
WORKDIR /app/backend

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}"]

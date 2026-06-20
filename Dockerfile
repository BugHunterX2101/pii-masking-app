# ==============================================================
# Stage 1 — Build the React frontend
# ==============================================================
FROM node:18-slim AS frontend-build

WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ==============================================================
# Stage 2 — Python runtime + serve everything
# ==============================================================
FROM python:3.12-slim

# System libraries required by OpenCV headless, Redis, and Supervisor
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        redis-server \
        supervisor \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (HF Spaces runs containers as uid 1000)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH="/home/user/.local/bin:$PATH"

WORKDIR $HOME/app

# Install Python dependencies
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# spaCy model is installed via requirements.txt (direct pip wheel URL)

# Copy backend source
COPY --chown=user:user backend/ ./backend/

# Copy the built React frontend from Stage 1
COPY --chown=user:user --from=frontend-build /build/build ./frontend/build

# Copy supervisord config
COPY --chown=user:user supervisord.conf .

# HF Spaces expects port 7860
EXPOSE 7860

CMD ["supervisord", "-c", "/home/user/app/supervisord.conf"]

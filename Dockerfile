FROM python:3.12-slim

WORKDIR /app

# System dependencies: git for cloning, bash for scripts
# RUN apt-get update \
#     && apt-get install -y --no-install-recommends git bash \
#     && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (including github-hosted libraries)
# COPY requirements.txt .
# RUN pip install --no-cache-dir --upgrade pip \
#     && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code (including supervisord.conf)
COPY . /app

# Run build-time processing
RUN ./app_build.sh

# Start the application under supervisord (Option 2)
CMD ["supervisord", "-c", "/app/supervisord.conf"]

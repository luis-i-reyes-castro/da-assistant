#!/bin/bash

set -e

# Start supervisor to manage the queue worker only
supervisord -c supervisord.conf &

# Run gunicorn directly as the main process (PID 1 inside container)
exec \
gunicorn --bind 0.0.0.0:${PORT:-8080} app:app \
         --workers 1 \
         --max-requests 1000 \
         --max-requests-jitter 20 \
         --timeout 300 \
         --graceful-timeout 60 \
         --keep-alive 10 \
         --preload \
         --access-logfile - \
         --error-logfile - \
         --log-level info

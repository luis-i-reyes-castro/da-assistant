#!/bin/bash

trap "kill 0" TERM INT

gunicorn --bind 0.0.0.0:$PORT app:app \
         --workers 1 \
         --max-requests 1000 \
         --max-requests-jitter 20 \
         --timeout 300 \
         --graceful-timeout 60 \
         --keep-alive 10 \
         --preload \
         --access-logfile - \
         --error-logfile - \
         --log-level info &

python3 queue_worker.py &

wait

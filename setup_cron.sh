#!/bin/bash

# Set up the cron job
echo "*/2 * * * * /usr/local/bin/python /app/scripts/poll_terminals.py >> /app/logs/poll_terminals.log 2>&1" | crontab -

# Start the cron daemon in the foreground
cron -f

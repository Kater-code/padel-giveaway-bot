#!/bin/sh
# Keep the bot alive on a laptop: no idle sleep, restart on crash.
cd "$(dirname "$0")"
set -a; . ./.env; set +a
exec caffeinate -i sh -c 'while true; do .venv/bin/python bot.py >> bot.log 2>&1; sleep 5; done'

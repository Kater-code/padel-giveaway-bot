# padel-giveaway-bot

Telegram bot for giveaways with screenshot verification.
Built for a padel community: prize — one hour on the courts at Barto Padel Space,
condition — follow the group in the Pado app and send a screenshot.

## Why not @RandomGodBot
Off-the-shelf bots pick a random button-clicker. This one accepts a screenshot
from each participant and draws **only among verified entries**. Admin sees every
screenshot before the prize is handed out.

## Features
- `/new` — admin creates a giveaway (text → prize → draw date), bot posts it to the group with a "Join" button
- participant clicks → bot asks for a screenshot in DM, stores `file_id`
- draw runs automatically at `draw_at`, only among participants with a screenshot
- `/participants`, `/redraw` for the admin

## Run
```
cp .env.example .env   # fill in
pip install -r requirements.txt
python bot.py
```

## Deploy
Docker: `docker build -t giveaway . && docker run --env-file .env -v ./data:/app/data giveaway`

## Stack
Python 3.12, aiogram 3, sqlite3 (stdlib). No scheduler lib — a 60s asyncio loop checks due giveaways.

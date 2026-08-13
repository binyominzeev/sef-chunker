# Sefaria Daily AI

A self-hosted web application that imports books from [Sefaria](https://www.sefaria.org/), splits them into daily reading portions, generates Hungarian AI summaries, and automatically sends them via a Telegram bot every day.

## Features

- 📥 **Import books** from Sefaria by reference (e.g. `Tomer Devorah`, `Pirkei Avot`)
- ✂️ **Split into daily chunks** — either into an equal number of days or by target character count, preferring natural chapter/paragraph/sentence boundaries
- 🧠 **AI summaries** in Hungarian, generated with the OpenAI Responses API
- 🧪 **Prompt Lab** — experiment with prompts, models, and temperature before saving a summary
- 🤖 **Telegram delivery** — a daily scheduled job (APScheduler) sends the next unread chunk's summary to your Telegram chat
- 🖥️ **Simple dashboard** built with FastAPI, Jinja2, HTMX and Bootstrap 5 — no SPA build step required
- 💾 **SQLite** storage via SQLAlchemy — zero external database dependency

## Tech Stack

- Python 3.13
- FastAPI + Uvicorn
- SQLAlchemy + SQLite
- Jinja2 + HTMX + Bootstrap 5
- OpenAI Responses API
- python-telegram-bot
- APScheduler
- pydantic-settings
- httpx
- [uv](https://github.com/astral-sh/uv) for package management

## Installation

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (`pip install uv` or see the [official install docs](https://docs.astral.sh/uv/getting-started/installation/))

### Setup

```bash
git clone <this-repo-url>
cd sef-chunker

# Install dependencies (creates a .venv automatically)
uv sync --dev
```

## Configuration

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
DEFAULT_MODEL=gpt-4o-mini
DAILY_SEND_TIME=08:00
DATABASE_URL=sqlite:///./data/sefaria_daily.db
```

All settings can also be changed later from the **Settings** page in the web UI (values are persisted to the database and take effect immediately for the running process, e.g. rescheduling the daily send time).

### Getting a Telegram Bot Token & Chat ID

1. Talk to [@BotFather](https://t.me/BotFather) on Telegram and run `/newbot` to create a bot and obtain a token.
2. Send a message to your new bot (or add it to a group/channel).
3. Find your chat ID — the easiest way is to call `https://api.telegram.org/bot<TOKEN>/getUpdates` after sending a message and read the `chat.id` field, or use a helper bot such as [@userinfobot](https://t.me/userinfobot).
4. Put the token and chat ID into `.env` (or the Settings page).

### Getting an OpenAI API Key

Create an API key at [platform.openai.com](https://platform.openai.com/api-keys) and put it in `.env` as `OPENAI_API_KEY`.

## Database Initialization

The SQLite database and tables are created automatically on application startup (see `app/database.py::init_db`). The `data/` directory is created automatically if it doesn't exist. No manual migration step is required.

## Running Locally

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000 in your browser.

### Typical workflow

1. Go to **Books → Import** and enter a Sefaria reference (e.g. `Tomer Devorah`).
2. After import, you'll be redirected to **Generate Chunks** — choose either "equal number of days" or "target character count" and generate.
3. Browse the generated chunks under **Chunks**, and preview any chunk's Hebrew text.
4. Use **Prompt Lab** to craft and test the Hungarian summary prompt against a chunk, and save the result once you're happy with it.
5. Configure your Telegram bot token/chat ID and daily send time on the **Settings** page.
6. The scheduler will automatically send the next unsent chunk's summary every day at the configured time. You can also trigger a manual send from the **Dashboard** ("Mai részlet küldése").

## Running Tests

```bash
uv run pytest tests/ -v
```

## Deploying to a VPS

A simple systemd-based deployment:

```bash
# On the server
git clone <this-repo-url> /opt/sefaria-daily-ai
cd /opt/sefaria-daily-ai
pip install uv
uv sync --no-dev
cp .env.example .env   # then edit with real credentials
```

Create `/etc/systemd/system/sefaria-daily-ai.service`:

```ini
[Unit]
Description=Sefaria Daily AI
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/sefaria-daily-ai
ExecStart=/opt/sefaria-daily-ai/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
EnvironmentFile=/opt/sefaria-daily-ai/.env

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sefaria-daily-ai
```

Put a reverse proxy (nginx/Caddy) in front of port 8000 for TLS termination if you need HTTPS.

### Updating the application

To deploy a new version on the server, pull the code, synchronize the production dependencies, and restart the service:

```bash
cd /opt/sefaria-daily-ai
git pull
uv sync --no-dev
sudo systemctl restart sefaria-daily-ai
```

Check that the service started successfully:

```bash
sudo systemctl status sefaria-daily-ai
```

Run `sudo systemctl daemon-reload` before the restart only when the systemd service file itself has changed. The SQLite database is kept in `data/` and is not replaced by this update procedure.

## Scheduler

The app uses [APScheduler](https://apscheduler.readthedocs.io/) with an `AsyncIOScheduler` and a daily `CronTrigger`. The trigger's hour/minute are parsed from the `daily_send_time` setting (`HH:MM`, 24h format). Changing the send time on the Settings page reschedules the job in the running process without a restart.

Each run of the scheduled job:

1. Picks the first `Book` in the database (single active book workflow) and its `Progress` record.
2. Determines the next unsent `Chunk` (`last_sent_chunk + 1`).
3. Generates a Hungarian summary via OpenAI if one doesn't already exist for that chunk.
4. Sends the formatted message via the Telegram bot.
5. Advances `last_sent_chunk`.

If all chunks have already been sent, the job is a no-op and logs that the reading is complete.

## Project Layout

```
app/
  config.py             # pydantic-settings configuration
  database.py            # SQLAlchemy engine/session/Base
  models.py               # ORM models (Book, Chunk, Summary, Progress, AppSettings)
  schemas.py                # Pydantic request/response schemas
  main.py                     # FastAPI app + router wiring + lifespan (DB init, scheduler)
  routes/                      # FastAPI routers (dashboard, books, chunks, prompt_lab, settings)
  services/                     # Business logic (Sefaria import, chunking, summarizer, Telegram, scheduler)
  prompts/summary.txt             # Default Hungarian summarization prompt template
  templates/                        # Jinja2 + HTMX + Bootstrap 5 templates
  static/                              # Static assets
tests/                                  # Pytest test suite
data/                                     # SQLite database file lives here (gitignored)
```

## License

This project is provided as-is for personal/self-hosted use.

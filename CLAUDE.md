# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
poetry install

# Run the bot
poetry run dev        # dev mode (uses .env.dev, enables hot-reload)
poetry run prod       # production mode

# Run database migrations
poetry run migrate

# Run tests
poetry run test

# Create a new cog scaffold
poetry run cog create --name MyCog --description "My description"

# Format code
poetry run black .
poetry run isort .

# Docker
docker-compose up --build
```

## Architecture

LancoBot is a modular Discord bot (Python / discord.py) built around a **cog system** where each feature is a self-contained module under `app/cogs/<name>/`.

### Core Components

**`app/main.py`** — Entry point. Creates the `LancoBot` instance, sets up logging, initializes the database via `init_db()`, and auto-loads all cogs from `app/cogs/`.

**`app/run.py`** — Poetry script entrypoints for `dev`, `prod`, and `test`. Handles `sys.path` setup so bare imports work correctly.

**`app/cogs/lancocog.py`** — `LancoCog` base class that all cogs inherit. Provides a per-cog logger, a scoped data directory, and context menu helpers. Every cog also defines a `CogDefinition` with name/description metadata.

**`app/db.py`** — Peewee `DatabaseProxy` that abstracts SQLite (default) vs MySQL. All Peewee models should inherit `BaseModel` defined here; it binds to this proxy so the same model code works with either backend.

**`app/utils/config.py`** — `GuildConfig` and `UserConfig` Peewee models used for per-guild and per-user persistent settings (prefix, timezone, opt-out, etc.).

**`app/utils/command_utils.py`** — Permission decorators (`is_bot_owner_or_admin`, etc.) used across cogs.

**`migrations/`** — Sequential numbered migration scripts run via `poetry run migrate`. Use Peewee's `SqliteMigrator` / `MySQLMigrator` depending on `DB_TYPE`.

**`tests/`** — Core bot test suite using pytest + dpytest. Run with `poetry run test`.

### Cog Pattern

```
app/cogs/mycog/
├── mycog.py      # main cog — inherits LancoCog
├── models.py     # optional Peewee models (if DB state is needed)
└── README.md     # optional per-cog docs
```

Minimal cog:
```python
from cogs.lancocog import LancoCog
from discord.ext import commands

class MyCog(LancoCog, name="MyCog", description="My description"):
    def __init__(self, bot):
        super().__init__(bot)

    async def cog_load(self):
        self.bot.database.create_tables([MyModel])  # create tables here, not in __init__

async def setup(bot):
    await bot.add_cog(MyCog(bot))
```

Use `poetry run cog create` to scaffold from `tools/templates/cog_template.py` rather than writing from scratch.

### URL Embed Handlers

Several cogs (Spotify, Twitter/X, Instagram, TikTok fixes) register themselves as URL handlers via a registry on the bot. When a message contains a matching URL, the relevant cog intercepts it to produce a better embed.

### Development Mode

Running `poetry run dev` loads `.env.dev` and sets `DEV_MODE=true` automatically, enabling `watchfiles`-based hot-reload: any change to a file under `app/cogs/` automatically reloads the affected cog without restarting the process.

### Environment

Copy `.env.default` to `.env` and fill in values. Key variables:
- `DISCORD_TOKEN` — required
- `DB_TYPE` — `sqlite` (default) or `mysql`
- `SQLITE_DB` — path to SQLite file (default `data/lancobot.db`)
- `DEV_MODE` — set to `true` to enable hot-reload (set automatically by `poetry run dev`)
- `COG_WHITELIST` — comma-separated list of cog directory names to load exclusively (e.g. `geoguesser,incidents`). When set, all other cogs are skipped. Useful for faster dev startup.
- `LOG_COGS` — comma-separated list of cog names whose logs appear on the console in dev mode (e.g. `geoguesser`). All other cog loggers are suppressed on console only; the log file still receives everything.
- All external API keys (OpenAI, Google Maps, Spotify, OWM, etc.) are optional; the cogs that depend on them fail gracefully or skip loading when the keys are absent.

### Deployment

The bot is deployed via GitHub Actions on push to `master`:
1. Tests run via `poetry run test`
2. Docker image is built and pushed to `ghcr.io`
3. VPS pulls the new image and restarts via `docker-compose`

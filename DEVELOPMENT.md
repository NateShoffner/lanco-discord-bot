# Development

## Commands

```bash
# Install dependencies
poetry install

# Run the bot
poetry run dev        # dev mode (uses .env, enables hot-reload)

# Run database migrations
poetry run migrate

# Run tests
poetry run test

# Create a new cog scaffold
poetry run cog create --name MyCog --description "My description"

# Format code
poetry run black .
poetry run isort .
```

## Environment

Copy `.env.default` to `.env` and fill in values. Key variables:

- `DISCORD_TOKEN` - required
- `DB_TYPE` - `sqlite` (default) or `mysql`
- `SQLITE_DB` - path to SQLite file
- `DEV_MODE` - set to `true` to enable hot-reload (set automatically by `poetry run dev`)
- `COG_WHITELIST` - comma-separated cog names to load exclusively; all others are skipped (e.g. `geoguesser,incidents`)
- `COG_BLACKLIST` - comma-separated cog names to skip; ignored if `COG_WHITELIST` is set
- `LOG_COGS` - comma-separated cog names whose logs appear on the console in dev mode; all others are suppressed on console only
- All external API keys are optional; cogs that depend on them fail gracefully when absent

## Architecture

LancoBot is a modular Discord bot (Python / discord.py) built around a **cog system** where each feature is a self-contained module under `app/cogs/<name>/`. Cogs are auto-loaded at startup, so adding a directory is all it takes to register a new feature.

Pieces a cog author touches:

**`app/cogs/lancocog.py`** - `LancoCog` base class that all cogs inherit. Provides a per-cog logger, a scoped data directory, and context menu helpers.

**`app/db.py`** - Peewee `DatabaseProxy` that abstracts SQLite (default) vs MySQL. All Peewee models should inherit `BaseModel` defined here.

**`app/utils/command_utils.py`** - Permission decorators (`is_bot_owner_or_admin`, etc.) used across cogs.

**`migrations/`** - Sequential numbered migration scripts run via `poetry run migrate`. Needed only when changing an existing model's schema; new tables are created by the cog itself.

**`tests/`** - Core bot test suite using pytest + dpytest. Run with `poetry run test`.

## Cog Structure

```
app/cogs/mycog/
├── __init__.py   # re-exports setup() - required
├── mycog.py      # main cog - inherits LancoCog
├── models.py     # optional Peewee models (if DB state is needed)
└── README.md     # optional per-cog docs
```

`__init__.py`:

```python
from .mycog import setup
```

Minimal cog:

```python
from cogs.lancocog import LancoCog
from discord.ext import commands

class MyCog(LancoCog, name="MyCog", description="My description"):
    def __init__(self, bot):
        super().__init__(bot)

    async def cog_load(self):
        await super().cog_load()
        self.bot.database.create_tables([MyModel])  # create tables here, not in __init__

async def setup(bot):
    await bot.add_cog(MyCog(bot))
```

Use `poetry run cog create` to scaffold from the template rather than writing from scratch.

In dev mode, saving any file under `app/cogs/` reloads the affected cog package (including submodules such as `models.py`) without restarting the bot.

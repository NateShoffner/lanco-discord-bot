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

**`app/main.py`** - Entry point. Creates the `LancoBot` instance, resolves the environment, sets up logging, initializes the database via `init_db()`, wires up APM via `init_apm()`, and auto-loads all cogs from `app/cogs/`.

**`app/run.py`** - Poetry script entrypoints for `dev`, `prod`, and `test`. Sets `BOT_ENV` and handles `sys.path` setup so bare imports work correctly.

**`app/utils/env.py`** - Resolves `BOT_ENV`, the single source of truth for which environment the process is. See "Environments" below.

**`app/utils/apm.py`** - Elastic APM instrumentation. Reports command, router-intent, and embed-fix activity as labelled transactions, plus the registered command/cog inventory. See "Observability" below.

**`app/cogs/lancocog.py`** — `LancoCog` base class that all cogs inherit. Provides a per-cog logger, a scoped data directory, and context menu helpers.

**`app/db.py`** — Peewee `DatabaseProxy` bound to the SQLite database. All Peewee models should inherit `BaseModel` defined here, which binds to this proxy.

**`app/utils/config.py`** — `GuildConfig` and `UserConfig` Peewee models used for per-guild and per-user persistent settings (prefix, timezone, opt-out, etc.).

**`app/utils/command_utils.py`** — Permission decorators (`is_bot_owner_or_admin`, etc.) used across cogs.

**`migrations/`** — Sequential numbered migration scripts run via `poetry run migrate`. Each file exposes a single `upgrade(ctx)` function and makes every change through the idempotent helpers on the `MigrationContext` in `migrations/helpers.py`, which owns the connection and the migrator. Applied filenames are tracked in `schema_migrations`. See `migrations/README.md` for the contract.

**`tests/`** — Core bot test suite using pytest + dpytest. Run with `poetry run test`.

### Cog Pattern

Each cog is a Python package. The directory must contain an `__init__.py` that re-exports `setup()` — this is what `load_extension("cogs.<name>")` resolves.

```
app/cogs/mycog/
├── __init__.py   # re-exports setup() — required
├── mycog.py      # main cog — inherits LancoCog
├── models.py     # optional Peewee models (if DB state is needed)
└── README.md     # per-cog docs
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

Use `poetry run cog create` to scaffold from `tools/templates/cog_template.py` rather than writing from scratch.

### URL Embed Handlers

Several cogs (Spotify, Twitter/X, Instagram, TikTok fixes) register themselves as URL handlers via a registry on the bot. When a message contains a matching URL, the relevant cog intercepts it to produce a better embed.

### Router

Core bot functionality (`app/utils/router/`, not a cog) that owns the single `on_message` handler. It is a three-layer inheritance chain: `MessageRouter` (registry, cheap gate, score, arbitrate, dispatch) → `FileRouter` (extract attachments, download each once) → `ImageRouter` (filter to images, one shared vision call). Only `ImageRouter` is instantiated and it inherits the other levels; there is one registry (`bot.processors`) and one listener. Cogs subclass `ProcessorCog` and register an `Intent` at the `message`, `file`, or `image` level (cheap predicate, confidence scorer, processor; image intents add vision questions). The cog's own `cheap_predicate` is the arbiter of whether the router runs it for a message (channel, regex, user, content type, whatever the cog wants), checked before any download or model call. The router gates cheaply, downloads each file once, runs **one** shared vision call answering the union of all image intents' questions, scores, arbitrates by confidence (isolated by default; `conflict_group` for mutually exclusive outputs), and dispatches the winner(s). This prevents N cogs from each re-downloading and independently calling a vision model on the same image. See `app/utils/router/README.md` for the full contract and a worked cog example.

### Environments

`BOT_ENV` is the single source of truth for which environment a process is. It decides three things that used to be decided independently and could disagree: which dotenv file loads, whether dev mode (hot-reload, debug logging) is on, and the environment reported to Elastic APM.

| Entrypoint | `BOT_ENV` | Dotenv file loaded |
|---|---|---|
| `poetry run dev` | `dev` | `.env.dev`, falling back to `.env` |
| `poetry run prod` | `prod` | `.env.prod`, falling back to `.env` |
| `poetry run test` | `test` | `.env.test` only, **never** `.env` |
| Docker | `prod` by default, overridable | `.env.${BOT_ENV}` (mounted config; nothing is baked into the image) |

The compose stack is parameterized rather than pinned to production. Setting `BOT_ENV`, `CONTAINER_NAME`, `WEBSERVER_PORT`, `DATA_DIR`, and `LOGS_DIR` in the `.env` next to `docker-compose.yml` runs it as a dev stack alongside prod on one host without colliding on the container name, the published port, or the database. Those values are read by compose's own interpolation, which only ever looks at the shell and that adjacent `.env`, never at the `env_file` it loads into the container. `BOT_ENV` is passed through the `environment:` block as well, so it outranks the `env_file` and the container can never load one environment's secrets while reporting itself as another.

Resolution is two-phase and lives in `app/utils/env.py`. What the process declares (a real `BOT_ENV` env var, the argv the entrypoint was called with, or a legacy `DEV_MODE=true`) is settled before any file is read, and it **outranks the file**. Without that, `load_dotenv(override=True)` reading a `DEV_MODE=false` out of `.env` would silently demote a dev run to production. After loading, both `BOT_ENV` and `DEV_MODE` are rewritten to agree.

Unknown names pass through (a deployment can call itself `staging` and have that reach APM intact); only `dev` turns on dev mode. `test` deliberately does not fall back to `.env`, because the suite imports `main` and a developer's file would replace the in-memory test database with the real one.

### Development Mode

Running `poetry run dev` sets `BOT_ENV=dev`, which loads `.env.dev` and enables `watchfiles`-based hot-reload. A background task started in `setup_hook` watches `app/cogs/` - any file change triggers a reload of the affected cog package, including all submodules (`models.py`, etc.).

### Observability

Elastic is the sink. Kibana does the aggregation, dashboards, and alerting; nothing is stored locally and there are no in-bot reporting commands. `app/utils/apm.py` supplies only what Kibana cannot work out for itself.

**Activity.** Every command, router intent, and embed fix becomes an APM transaction labelled `cog`, `command`, `guild_id`, and `error_type`. Transaction types are the vocabulary every dashboard filters on, so renaming one silently breaks saved queries:

| `transaction.type` | Source |
|---|---|
| `command` | prefix commands |
| `app_command` | slash commands and context menus |
| `router_intent` | a dispatched routing intent |
| `embed_fix` | an embed rewritten, per handler |
| `cog_action` | whatever a cog reports via `record_activity` |
| `inventory` | the startup inventory (see below) |

Results are `success`, `failure`, or `denied`. `denied` means a check rejected the invocation: an attempt, not a failure, and not the same thing as unused. That case matters because a rejected command never reaches `before_invoke`, so a listener in `apm.install()` reports it instead. Without that, a permission-gated command would look identical to a dead one.

Instrumentation is central, so a new cog is covered the day it lands. Work with no command behind it (a listener, a scheduled job) calls `self.record_activity(...)`, which is a no-op when APM is off.

**Inventory.** APM only ever sees what *ran*, so it cannot distinguish a command nobody has invoked from one that does not exist. Once per process, `on_ready` emits the registered commands and cogs as one span each under `transaction.type: inventory`. In Kibana the registered set is those spans and the used set is every other transaction type; what appears in the first and not the second is the retirement shortlist.

**Logs.** `ECS_LOG_FILE` turns on a second log file written as ECS JSON, one document per line, for a shipper to tail into Elasticsearch. The console and `logs/logfile.log` are unchanged, because turning those into JSON would make `docker logs` and a tail over SSH unreadable. Off unless the variable names a path.

Each document carries `service.name`, `service.version`, `service.environment`, `event.dataset`, and `data_stream.namespace`, plus `trace.id` and `transaction.id` whenever a transaction was in flight. That last pair is the point: it lets Kibana jump from a log line to the command that produced it, and puts the surrounding log lines on the APM service's Logs tab.

`ecs_logging` supplies the trace fields itself from the agent, but only during a transaction, so `app/utils/logs.py` fills the service fields in afterwards with setdefault semantics. Passing them through the formatter's own `extra` looks equivalent and is not: the merge is strict, two values for one key raise inside `format()`, the handler swallows it, and the line is dropped. That empties the log exactly when APM is working.

Shipping is a Filebeat sidecar in `docker-compose.yml`, behind a `logging` profile so it never starts for anyone who has not configured Elasticsearch:

```bash
docker-compose --profile logging up -d
```

It needs `ELASTICSEARCH_HOST` and `ELASTICSEARCH_API_KEY` in the same `.env.<env>` file as the rest of the config, and `ECS_LOG_FILE` set so there is something to tail. The automated deploy passes no profile, so to keep the sidecar running there put `COMPOSE_PROFILES=logging` in the `.env` beside `docker-compose.yml`; compose reads that variable itself, and the workflow needs no change. Note those are Elasticsearch credentials, not the APM ones: different endpoints, different keys. Filebeat forwards the documents as-is and parses nothing, so the log shape is decided in one place only. Routing is driven entirely by fields the bot stamped, into `logs-<event.dataset>-<data_stream.namespace>`, so one shipper config serves every environment and dev logs cannot land in the prod data stream: `logs-lanco_bot.log-dev` and `logs-lanco_bot.log-prod`. Both segments are sanitised in `app/utils/logs.py`, since a hyphen in either would split the data stream name into the wrong pieces. The namespace is derived from the environment rather than reusing `service.environment` directly, because that field has to match what the APM agent reports verbatim for correlation to work. Tailing a file rather than posting from inside the bot means logs written just before a crash still get shipped.

**Caveat: retention.** "Should we drop this cog" spans months, while raw APM transaction data is governed by your cluster's ILM policy and is typically kept for days to weeks. Check that policy, or lean on APM's longer-lived aggregated transaction metrics, before trusting a long-window answer.

### Environment

Copy `.env.default` to `.env` (or to `.env.dev` / `.env.prod`) and fill in values. Key variables:
- `DISCORD_TOKEN` — required
- `SQLITE_DB` — path to SQLite file (default `data/lancobot.db`)
- `BOT_ENV` - `dev` or `prod`; see "Environments" above. Set automatically by the poetry entrypoints and by `docker-compose.yml`
- `DEV_MODE` - legacy alias for `BOT_ENV=dev`; prefer `BOT_ENV`
- `COG_WHITELIST` — comma-separated list of cog directory names to load exclusively (e.g. `geoguesser,incidents`). When set, all other cogs are skipped. Useful for faster dev startup.
- `COG_BLACKLIST` — comma-separated list of cog directory names to skip (e.g. `honeybot,triviasniper`). Ignored if `COG_WHITELIST` is also set.
- `LOG_LEVEL` - optional root log level override (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Defaults to `DEBUG` in dev mode and `INFO` otherwise; set `LOG_LEVEL=INFO` in `.env.dev` to hide debug output when running `poetry run dev`.
- `LOG_COGS` — comma-separated list of cog names whose logs appear on the console in dev mode (e.g. `geoguesser`). All other cog loggers are suppressed on console only; the log file still receives everything.
- `ECS_LOG_FILE` - optional path to an ECS JSON log file for a shipper to tail into Elasticsearch. Empty disables it. See "Observability" above.
- `ELASTIC_APM_SERVER_URL` — optional. When set, enables Elastic APM error tracking; uncaught exceptions from commands, app commands, and event listeners are reported with stack traces, locals, and labels (command/cog/guild/user). The agent self-configures from the standard `ELASTIC_APM_*` env vars (`SERVER_URL`, `SECRET_TOKEN` or `API_KEY`, `SERVICE_NAME`, etc.), so it works against Elastic Cloud, a self-hosted APM Server, or a local stack with no hardcoded values. When unset, APM is fully disabled and all capture calls are no-ops.
- `ELASTIC_APM_ENVIRONMENT` - optional. Defaults to `BOT_ENV`, which is what keeps dev and prod separate in Kibana. `init_apm()` seeds the agent's env vars with `setdefault` rather than passing keyword arguments, because an explicit kwarg to `elasticapm.Client()` outranks the environment and would make this unsettable.
- `ELASTIC_APM_STARTUP_TEST` - optional. Sends one synthetic error at startup to prove the pipeline works. Defaults to on in dev and off in prod, so production does not file a fake error on every deploy. Set to `true` temporarily when verifying prod wiring. `init_apm()` also logs the resolved service name, environment, and version at startup.
- All external API keys (OpenAI, Google Maps, Spotify, OWM, etc.) are optional; the cogs that depend on them fail gracefully or skip loading when the keys are absent.

### Git

Commit messages must follow Conventional Commits with a scope:

```
type(scope): description
```

- **type**: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`
- **scope**: the cog name or subsystem (e.g. `counting`, `techlanc`, `core`, `apm`)
- **description**: lowercase, imperative, no period — concise but descriptive enough to capture intent; avoid overly specific implementation details
- No `Co-Authored-By` trailers

Examples: `feat(counting): add counting game cog`, `fix(techlanc): silence cooldown errors`

### Deployment

The bot is deployed via GitHub Actions on push to `master`. The workflow only triggers when code-relevant paths change (`app/`, `tests/`, `migrations/`, `tools/`, `pyproject.toml`, `poetry.lock`, `Dockerfile`, `docker-compose.yml`). Pushes that only modify docs or other non-code files skip the pipeline entirely.

1. Tests run via `poetry run test`
2. Docker image is built and pushed to `ghcr.io`
3. VPS pulls the new image and restarts via `docker-compose`

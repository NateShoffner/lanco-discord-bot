import asyncio
import datetime
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from enum import Enum, auto
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

import discord
import elasticapm
from cogs.lancocog import LancoCog, UrlHandler
from db import BaseModel, DatabaseType, database_proxy
from discord.ext import commands
from dotenv import load_dotenv
from logtail import LogtailHandler
from peewee import *
from utils.command_utils import is_bot_owner
from utils.image_router import ImageIntent, ImageRouter
from watchfiles import Change, awatch

DATA_DIR = "data"
LOGS_DIR = "logs"
COGS_DIR = "app/cogs"

logger = logging.getLogger()

# Remove all handlers associated with the root logger object to prevent duplicate logs
if logger.hasHandlers():
    logger.handlers.clear()

LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = LOG_FORMAT

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class WinTimedRotatingFileHandler(TimedRotatingFileHandler):
    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        super().doRollover()

    def rotate(self, source, dest):
        shutil.copy2(source, dest)
        open(source, "w").close()  # truncate in place instead of renaming


os.makedirs(LOGS_DIR, exist_ok=True)
file_logger = WinTimedRotatingFileHandler(
    filename=os.path.join(LOGS_DIR, "logfile.log"),
    when="midnight",
    interval=1,
    encoding="utf-8",
)
file_logger.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(file_logger)

console_logger = logging.StreamHandler()
console_logger.stream.reconfigure(encoding="utf-8", errors="replace")
console_logger.setFormatter(CustomFormatter())
logger.addHandler(console_logger)

log_level = (
    logging.DEBUG if os.getenv("DEV_MODE", "").lower() == "true" else logging.INFO
)
logger.setLevel(log_level)

# Suppress noisy third-party loggers regardless of log level
for noisy in [
    "urllib3",
    "asyncio",
    "aiohttp",
    "elastic_transport",
    "elasticapm",
    "peewee",
    "asyncprawcore",
    "discord",
    "watchfiles",
    "httpx",
    "openai",
]:
    logging.getLogger(noisy).setLevel(logging.WARNING)

env_file = ".env"
dev_arg = len(sys.argv) > 1 and sys.argv[1] == "dev"
if len(sys.argv) > 1:
    env = sys.argv[1]
    env_file = f".env.{env}"

if os.path.exists(env_file):
    load_dotenv(env_file, override=True)
    logger.info(f"Loaded environment: {env_file}")
else:
    logger.info("No .env file found, using environment variables")

# In dev mode, LOG_COGS=geoguesser,incidents filters console output to only those cogs
_log_cogs_env = os.getenv("LOG_COGS", "")
if _log_cogs_env and os.getenv("DEV_MODE", "").lower() == "true":
    _allowed_cogs = {c.strip().lower() for c in _log_cogs_env.split(",")}

    # build set of known non-cog logger name prefixes to always allow through
    _always_allow_prefixes = ("root", "utils.", "discord.", "db", "__main__")

    class CogFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            name = record.name.lower()
            # always allow root and utility loggers
            if name == "root" or any(
                name.startswith(p) for p in _always_allow_prefixes
            ):
                return True
            # cogs use their qualified_name as logger (e.g. "GeoGuesser", "RedditFeed")
            # submodules use dotted paths like "cogs.geoguesser.session"
            if name.startswith("cogs."):
                parts = name.split(".")
                return len(parts) > 1 and parts[1] in _allowed_cogs
            # top-level cog logger name — match directly
            return name in _allowed_cogs

    console_logger.addFilter(CogFilter())
    logger.info(f"LOG_COGS filter active: {_allowed_cogs}")

# If launched with the "dev" arg, force DEV_MODE on regardless of what the env file says
if dev_arg:
    os.environ["DEV_MODE"] = "true"

if os.getenv("LOGTAIL_TOKEN"):
    logger.addHandler(LogtailHandler(os.getenv("LOGTAIL_TOKEN")))

# Elastic APM (optional). Enabled only when ELASTIC_APM_SERVER_URL is set.
# The agent self-configures from standard ELASTIC_APM_* environment variables
# (SERVER_URL, SECRET_TOKEN or API_KEY, VERIFY_SERVER_CERT, etc.) so this works
# against Elastic Cloud, a self-hosted APM Server, or a local stack without any
# hardcoded, deployment-specific values. When unset, apm_client stays None and
# all capture calls are no-ops.
apm_client = None


class ApmLoggingHandler(logging.Handler):
    def emit(self, record):
        if apm_client is None:
            return
        if record.name.startswith("elasticapm"):
            return
        try:
            if record.exc_info and record.exc_info[0] is not None:
                apm_client.capture_exception(exc_info=record.exc_info, handled=True)
            else:
                try:
                    raise Exception(record.getMessage())
                except Exception:
                    apm_client.capture_exception(handled=True)
        except Exception:
            self.handleError(record)


def init_apm():
    """Construct the Elastic APM client once, if configured.

    Called from main() rather than at module level so cog re-imports don't
    register a duplicate client. Idempotent.
    """
    global apm_client
    if apm_client is not None:
        return
    if not os.getenv("ELASTIC_APM_SERVER_URL"):
        return
    try:
        apm_client = elasticapm.Client(
            service_name=os.getenv("ELASTIC_APM_SERVICE_NAME", "lanco-bot"),
            environment=(
                "dev" if os.getenv("DEV_MODE", "").lower() == "true" else "production"
            ),
        )
        logging.getLogger().addHandler(ApmLoggingHandler(level=logging.ERROR))
        logger.info(
            f"Elastic APM enabled (server={os.getenv('ELASTIC_APM_SERVER_URL')}, "
            f"service={apm_client.config.service_name}, "
            f"environment={apm_client.config.environment})"
        )
        try:
            raise Exception("APM startup test")
        except Exception:
            event_id = apm_client.capture_exception(handled=True)
            if event_id:
                logger.info(f"APM startup test event queued: {event_id}")
            else:
                logger.warning(
                    "APM startup test returned None — is_recording may be False"
                )
    except Exception as e:
        logger.error(f"Failed to initialize Elastic APM: {e}")
        apm_client = None


def capture_apm_exception(exc_info=None, **context) -> None:
    """Report an exception to Elastic APM, if configured.

    Pass exc_info=(type, value, tb) explicitly when there is no active
    sys.exc_info() — e.g. when the exception was passed as a parameter rather
    than caught in the current frame. Without it, capture_exception raises
    ValueError. No-op when APM is disabled.
    """
    if apm_client is None:
        return
    try:
        user = context.pop("user", None)
        labels = {k: v for k, v in context.items() if v is not None}
        ctx = {}
        if user:
            ctx["user"] = user
        if labels:
            ctx["tags"] = labels
        apm_client.capture_exception(
            exc_info=exc_info, handled=True, context=ctx or None
        )
    except Exception as e:
        logger.error(f"Failed to capture exception in Elastic APM: {e}")


intents = discord.Intents.all()

DEFAULT_PREFIX = "."
_prefix_cache: dict[int, str] = {}


def get_prefix(bot, message):
    if message.guild:
        guild_prefix = _prefix_cache.get(message.guild.id, DEFAULT_PREFIX)
        # Always include the default prefix so core bot commands remain accessible
        return list({DEFAULT_PREFIX, guild_prefix})
    return DEFAULT_PREFIX


def init_db() -> SqliteDatabase:
    """Initialize and connect the database, returning the database instance."""
    db_type_str = os.getenv("DB_TYPE", "sqlite")

    try:
        db_type = DatabaseType.from_str(db_type_str)
        logger.info(f"Using {db_type.name} database")
    except ValueError as e:
        logger.error(e)
        exit(1)

    if db_type == DatabaseType.SQLITE:
        sqlite_path = os.getenv("SQLITE_DB")
        db_dir = os.path.dirname(sqlite_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        db = SqliteDatabase(sqlite_path)

    elif db_type == DatabaseType.MYSQL:
        db = MySQLDatabase(
            os.getenv("MYSQL_DB"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT", 3306)),
        )

    else:
        raise ValueError(f"Unsupported database type: {db_type_str}")

    database_proxy.initialize(db)
    db.connect()
    return db


database = init_db()


class BlacklistedUser(BaseModel):
    user_id = BigIntegerField(primary_key=True)
    reason = TextField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "blacklisted_users"


database.create_tables([BlacklistedUser])


class CogStatus(Enum):
    LOADED = auto()
    RELOADED = auto()
    UNLOADED = auto()
    ERROR = auto()


@dataclass
class CogLoadResult:
    name: str
    status: CogStatus = CogStatus.ERROR
    error: Optional[str] = None


def _purge_cog_modules(dotted: str):
    """Remove a cog package and all its submodules from sys.modules so they reload cleanly."""
    to_remove = [k for k in sys.modules if k == dotted or k.startswith(dotted + ".")]
    for key in to_remove:
        del sys.modules[key]


class LancoBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.dev_mode = os.getenv("DEV_MODE", "").lower() == "true"
        self.start_time = datetime.datetime.now()

        # TODO probably a better way to inject a database into a cog
        self.database = database
        self.url_handlers = []
        # Image processor router. Cogs register an ImageIntent; the router owns
        # the single image on_message handler and dispatches to the winning
        # intent(s). IMAGE_ROUTER_ALL_IMAGES=true routes every image in a
        # message instead of just the first.
        self.image_processors: list["ImageIntent"] = []
        self.image_router: "ImageRouter" = ImageRouter(
            self,
            cache_dir=os.path.join(DATA_DIR, "ImageRouter", "Cache"),
            process_all_images=os.getenv("IMAGE_ROUTER_ALL_IMAGES", "").lower()
            == "true",
        )

    def set_dev_mode(self, mode: bool):
        self.dev_mode = mode

    def get_guild_prefix(self, guild: Optional[discord.Guild] = None) -> str:
        if guild:
            if guild.id in _prefix_cache:
                return _prefix_cache[guild.id]
            from utils.config import GuildConfig

            config = GuildConfig.get_or_none(guild_id=guild.id)
            prefix = config.prefix if config and config.prefix else DEFAULT_PREFIX
            _prefix_cache[guild.id] = prefix
            return prefix
        return DEFAULT_PREFIX

    def get_lanco_cog(self, cog_name: str) -> LancoCog:
        return self.get_cog(cog_name)

    def get_lanco_cogs(self, sort_by_name=True) -> list[LancoCog]:
        cogs = [c for c in self.cogs.values() if isinstance(c, LancoCog)]
        if sort_by_name:
            return sorted(cogs, key=lambda c: c.get_cog_name())
        return cogs

    def is_cog_loaded(self, name: str) -> bool:
        return f"cogs.{name}" in self.extensions

    async def load_cog(self, name: str) -> "CogLoadResult":
        dotted = f"cogs.{name}"
        result = CogLoadResult(name)
        try:
            if dotted in self.extensions:
                logger.info(f"Reloading {name}")
                _purge_cog_modules(dotted)
                await self.reload_extension(dotted)
                result.status = CogStatus.RELOADED
            else:
                logger.info(f"Loading {name}")
                await self.load_extension(dotted)
                result.status = CogStatus.LOADED
        except Exception as e:
            logger.error(f"Failed to load cog {name}: {e}")
            capture_apm_exception(cog=name, event="cog_load")
            result.status = CogStatus.ERROR
            result.error = str(e)
        return result

    async def load_cogs(self) -> list["CogLoadResult"]:
        cog_whitelist_env = os.getenv("COG_WHITELIST", "")
        cog_whitelist = (
            {c.strip().lower() for c in cog_whitelist_env.split(",") if c.strip()}
            if cog_whitelist_env
            else None
        )
        if cog_whitelist:
            logger.info(f"COG_WHITELIST active: {cog_whitelist}")

        cog_blacklist_env = os.getenv("COG_BLACKLIST", "")
        cog_blacklist = (
            {c.strip().lower() for c in cog_blacklist_env.split(",") if c.strip()}
            if cog_blacklist_env
            else None
        )
        if cog_blacklist:
            logger.info(f"COG_BLACKLIST active: {cog_blacklist}")

        results = []
        for entry in os.scandir(COGS_DIR):
            if not entry.is_dir():
                continue
            if cog_whitelist and entry.name.lower() not in cog_whitelist:
                continue
            if cog_blacklist and entry.name.lower() in cog_blacklist:
                continue
            if os.path.isfile(os.path.join(entry.path, "__init__.py")):
                result = await self.load_cog(entry.name)
                results.append(result)
        return results

    async def unload_cog(self, name: str) -> "CogLoadResult":
        dotted = f"cogs.{name}"
        result = CogLoadResult(name)
        if dotted in self.extensions:
            try:
                logger.info(f"Unloading {name}")
                await self.unload_extension(dotted)
                result.status = CogStatus.UNLOADED
            except Exception as e:
                logger.error(f"Failed to unload cog {name}: {e}")
                capture_apm_exception(cog=name, event="cog_unload")
                result.status = CogStatus.ERROR
                result.error = str(e)
        return result

    def register_url_handler(self, handler: UrlHandler):
        logger.info(
            f"Registering url handler: {handler.url_pattern.pattern} - {handler.cog.get_cog_name()}"
        )
        # do a pre-check of possible duplicate url handlers
        if handler.example_url:
            for h in self.url_handlers:
                if h.url_pattern.match(handler.example_url):
                    logger.warning(f"Duplicate url handler: {handler.example_url}")
        self.url_handlers.append(handler)

    # TODO allow cogs to declare whether a URL has been properly handled or not

    def get_url_handler(self, url: str) -> Optional[UrlHandler]:
        for handler in self.url_handlers:
            if handler.url_pattern.match(url):
                return handler
        return None

    def has_url_handler(self, url: str) -> bool:
        return self.get_url_handler(url) is not None

    def register_image_processor(self, intent: ImageIntent) -> None:
        """Register an ImageIntent with the router. Intents are removed on cog
        unload via the cleanup in LancoCog.cog_unload.
        """
        logger.info(
            f"Registering image processor: {intent.name} - {intent.cog.get_cog_name()}"
        )
        self.image_processors.append(intent)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        _prefix_cache.pop(guild.id, None)

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"Bot ready: {self.user.name} - {self.user.id}")

    async def setup_hook(self):
        self.add_listener(self.image_router.handle_message, "on_message")
        if self.dev_mode:
            self.loop.create_task(self._hot_reload_watcher())

    async def _hot_reload_watcher(self):
        async for changes in awatch(COGS_DIR):
            reverse_ordered_changes = sorted(changes, reverse=True)
            for change_type, change_path in reverse_ordered_changes:
                path = os.path.normpath(change_path)
                tokens = path.split(os.sep)
                try:
                    cogs_index = tokens.index("cogs")
                except ValueError:
                    continue
                if cogs_index + 1 >= len(tokens):
                    continue
                cog_name = tokens[cogs_index + 1]

                if change_type == Change.deleted:
                    await self.unload_cog(cog_name)
                else:
                    await self.load_cog(cog_name)


class ApmCommandTree(discord.app_commands.CommandTree):
    async def _call(self, interaction: discord.Interaction) -> None:
        if (
            apm_client is None
            or interaction.type != discord.InteractionType.application_command
        ):
            await super()._call(interaction)
            return
        command_name = (
            interaction.command.qualified_name if interaction.command else "unknown"
        )
        apm_client.begin_transaction("app_command")
        elasticapm.label(command=command_name)
        if interaction.guild_id:
            elasticapm.label(guild_id=str(interaction.guild_id))
        try:
            await super()._call(interaction)
        finally:
            result = (
                "failure"
                if getattr(interaction, "command_failed", False)
                else "success"
            )
            apm_client.end_transaction(command_name, result)


owner_id = int(os.getenv("OWNER_ID", 0))
message_cache_size = int(os.getenv("MESSAGE_CACHE_SIZE", 1000))
bot = LancoBot(
    command_prefix=get_prefix,
    intents=intents,
    owner_id=owner_id,
    max_messages=message_cache_size,
    tree_cls=ApmCommandTree,
)


def _apm_user(obj) -> Optional[dict]:
    """Build an APM user-context dict from a discord User/Member, if present."""
    user = getattr(obj, "author", None) or getattr(obj, "user", None)
    if user is None:
        return None
    return {"user_id": str(user.id), "username": str(user)}


@bot.before_invoke
async def _begin_command_transaction(ctx: commands.Context):
    if apm_client is None:
        return
    apm_client.begin_transaction("command")
    elasticapm.label(command=str(ctx.command))
    if ctx.guild:
        elasticapm.label(guild_id=str(ctx.guild.id))


@bot.after_invoke
async def _end_command_transaction(ctx: commands.Context):
    if apm_client is None:
        return
    result = "failure" if ctx.command_failed else "success"
    apm_client.end_transaction(str(ctx.command) if ctx.command else "unknown", result)


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    # Ignore the common, expected non-errors so they don't pollute APM/logs.
    if isinstance(
        error,
        (commands.CommandNotFound, commands.CheckFailure, commands.UserInputError),
    ):
        return
    original = getattr(error, "original", error)
    logger.error(f"Command error in {ctx.command}: {original}", exc_info=original)
    capture_apm_exception(
        exc_info=(type(original), original, original.__traceback__),
        command=str(ctx.command) if ctx.command else None,
        cog=ctx.cog.qualified_name if ctx.cog else None,
        guild_id=ctx.guild.id if ctx.guild else None,
        channel_id=ctx.channel.id if ctx.channel else None,
        user=_apm_user(ctx),
    )


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: Exception):
    if isinstance(error, discord.app_commands.CheckFailure):
        return
    original = getattr(error, "original", error)
    command = interaction.command.qualified_name if interaction.command else None
    logger.error(f"App command error in {command}: {original}", exc_info=original)
    capture_apm_exception(
        exc_info=(type(original), original, original.__traceback__),
        command=command,
        cog=(
            interaction.command.binding.qualified_name
            if getattr(interaction.command, "binding", None)
            else None
        ),
        guild_id=interaction.guild_id,
        channel_id=interaction.channel_id,
        user=_apm_user(interaction),
    )


@bot.event
async def on_error(event_method: str, *args, **kwargs):
    # Fires for any uncaught exception in an event listener (on_message, etc.).
    # logger.exception() pulls the active exception from sys.exc_info().
    logger.exception(f"Unhandled exception in event: {event_method}")
    capture_apm_exception(event=event_method)


@bot.command(name="gsync")
@commands.is_owner()
async def guildsync(ctx):
    guild = ctx.guild
    embed = discord.Embed(
        title=f"Syncing Guild: {guild.name}",
        description="Wait a moment...",
        color=discord.Color.dark_gray(),
    )
    msg = await ctx.send(embed=embed)
    logger.info(f"Syncing guild: {guild.name}")
    try:
        synced = await bot.tree.sync(guild=guild)
        logger.info(f"Synced {len(synced)} commands for {guild.name}")
        embed.description = f"Synced {len(synced)} commands"
        embed.color = discord.Color.green()
        await msg.edit(embed=embed)
    except Exception as e:
        logger.error(e)
        capture_apm_exception(
            command="gsync", guild_id=ctx.guild.id, user=_apm_user(ctx)
        )


@bot.command(name="sync")
@commands.is_owner()
async def sync(ctx):
    embed = discord.Embed(
        title="Syncing Commands",
        description="Wait a moment...",
        color=discord.Color.dark_gray(),
    )
    msg = await ctx.send(embed=embed)
    logger.info("Syncing commands")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands")
        embed.description = f"Synced {len(synced)} commands"
        embed.color = discord.Color.green()
        await msg.edit(embed=embed)
    except Exception as e:
        logger.error(e)
        capture_apm_exception(command="sync", user=_apm_user(ctx))


@bot.tree.command(name="reload", description="Reload a cog")
@is_bot_owner()
async def reload_cog(interaction: discord.Interaction, cog_name: str):
    result = await bot.load_cog(cog_name)
    embed = discord.Embed(title=f'Reloading Cog: "{cog_name}"', color=0x00FF00)
    if result.status == CogStatus.LOADED:
        embed.description = f"Loaded {cog_name}"
    elif result.status == CogStatus.RELOADED:
        embed.description = f"Reloaded {cog_name}"
    elif result.status == CogStatus.ERROR:
        embed.description = f"Error loading {cog_name}: ```{result.error}```"
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="reloadall", description="Reload all cogs")
@is_bot_owner()
async def reload_all(interaction: discord.Interaction):
    embed = discord.Embed(title="[Re]-Loaded Cogs", color=0x00FF00)
    results = await bot.load_cogs()

    reloaded = [r.name for r in results if r.status == CogStatus.RELOADED]
    loaded = [r.name for r in results if r.status == CogStatus.LOADED]
    errored = [r.name for r in results if r.status == CogStatus.ERROR]

    def fmt(names):
        return f"```{chr(10).join(names)}```" if names else "None"

    embed.add_field(
        name=f"Reloaded ({len(reloaded)}):", value=fmt(reloaded), inline=False
    )
    embed.add_field(name=f"Loaded ({len(loaded)}):", value=fmt(loaded), inline=False)
    error_value = fmt(errored)
    if errored:
        error_value += "\nRun the `/reload cog_name` command for more info"
    embed.add_field(name=f"Failed ({len(errored)}):", value=error_value, inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="unload", description="Unload a cog")
@is_bot_owner()
async def unload_cog(interaction: discord.Interaction, cog_name: str):
    result = await bot.unload_cog(cog_name)
    embed = discord.Embed(title=f"Unloading Cog: {cog_name}", color=0x00FF00)
    if result.status == CogStatus.UNLOADED:
        embed.description = f"Unloaded {cog_name}"
    elif result.status == CogStatus.ERROR:
        embed.description = f"Error unloading {cog_name}: ```{result.error}```"
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="devmode")
@is_bot_owner()
async def devmode(interaction: discord.Interaction):
    bot.set_dev_mode(not bot.dev_mode)
    embed = discord.Embed(
        title="Dev Mode",
        description="Enabled" if bot.dev_mode else "Disabled",
        color=0x00FF00,
    )
    await interaction.response.send_message(embed=embed)


@bot.check
async def global_block_check(ctx):
    if BlacklistedUser.get_or_none(user_id=ctx.author.id):
        return False
    return True


async def main():
    from utils.config import GuildConfig
    from utils.db_backup import DatabaseBackup

    init_apm()
    database.create_tables([GuildConfig])
    for config in GuildConfig.select():
        if config.prefix:
            _prefix_cache[config.guild_id] = config.prefix

    db_backup = DatabaseBackup()
    await bot.load_cogs()
    async with bot:
        db_backup.start()
        await bot.start(os.getenv("DISCORD_TOKEN"))
        db_backup.stop()


if __name__ == "__main__":
    asyncio.run(main())

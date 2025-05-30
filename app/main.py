import asyncio
import datetime
import logging
import os
from dataclasses import dataclass
from enum import Enum
from logging.handlers import TimedRotatingFileHandler
from sys import version_info as sysv
from time import monotonic
from typing import Optional

import discord
from cogs.lancocog import CogDefinition, LancoCog, UrlHandler, get_cog_def
from db import BaseModel, DatabaseType, database_proxy
from discord.ext import commands
from dotenv import load_dotenv
from logtail import LogtailHandler
from peewee import *
from utils.command_utils import is_bot_owner
from utils.dist_utils import get_bot_version, get_commit_hash
from utils.network_utils import get_external_ip
from watchfiles import Change, awatch

load_dotenv()

logger = logging.getLogger()

if os.getenv("LOGTAIL_TOKEN"):
    logger.addHandler(LogtailHandler(os.getenv("LOGTAIL_TOKEN")))

intents = discord.Intents.all()

db_type = None
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
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    database = SqliteDatabase(sqlite_path)

elif db_type == DatabaseType.MYSQL:
    database = MySQLDatabase(
        os.getenv("MYSQL_DB"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
    )

else:
    raise ValueError(f"Unsupported database type: {db_type}")

database_proxy.initialize(database)
database.connect()

DATA_DIR = "data"
LOGS_DIR = "logs"
COGS_DIR = "app/cogs"


class BlacklistedUser(BaseModel):
    user_id = BigIntegerField(primary_key=True)
    reason = TextField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "blacklisted_users"


database.create_tables([BlacklistedUser])


class LancoBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.dev_mode = os.getenv("DEV_MODE", False)
        self.start_time = datetime.datetime.now()

        # TODO probably a better way to inject a database into a cog
        self.database = database
        self.url_handlers = []

    def set_dev_mode(self, mode: bool):
        self.dev_mode = mode

    def get_lanco_cog(self, cog_name: str) -> LancoCog:
        """Returns a LancoCog instance by name."""
        return self.get_cog(cog_name)

    def get_lanco_cog_by_class_name(self, class_name: str) -> LancoCog:
        for c in self.get_lanco_cogs():
            if c.get_class_name().lower() == class_name.lower():
                return c
        return None

    def get_lanco_cog_by_dotted_path(self, dotted_path: str) -> LancoCog:
        for c in self.get_lanco_cogs():
            if c.get_dotted_path() == dotted_path:
                return c
        return None

    def get_lanco_cogs(self, sort_by_name=True) -> list[LancoCog]:
        """Get all cogs that are instances of LancoCog"""
        cogs = [c for c in self.cogs.values() if isinstance(c, LancoCog)]
        if sort_by_name:
            return sorted(cogs, key=lambda c: c.get_cog_name())
        return cogs

    def is_cog_loaded(self, qualified_name: str) -> bool:
        """Check if a cog with the given name is loaded"""
        for c in self.get_lanco_cogs():
            if c.get_dotted_path().lower() == qualified_name.lower():
                return True
        return False

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

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"Bot ready: {self.user.name} - {self.user.id}")

        async for changes in awatch(COGS_DIR):
            if not self.dev_mode:
                continue

            reverse_ordered_changes = sorted(changes, reverse=True)

            for change in reverse_ordered_changes:
                change_type = change[0]
                change_path = change[1]

                path = os.path.normpath(change_path)
                tokens = path.split(os.sep)
                reversed_tokens = list(reversed(tokens))

                cog_dir_index = reversed_tokens.index(COGS_DIR.split("/")[0])
                cog_dir = ".".join([token for token in tokens[-cog_dir_index:-1]])
                cog_name = cog_dir.split(".")[-1]
                loaded_cog = self.get_lanco_cog_by_dotted_path(cog_dir)

                cog_def = None
                if loaded_cog:
                    cog_def = get_cog_def(loaded_cog.get_cog_name(), COGS_DIR)
                else:
                    cog_def = get_cog_def(cog_name, COGS_DIR)

                if change_type == Change.deleted:
                    await unload_cog_by_name(self, cog_def.name)
                elif change_type == Change.added:
                    await load_cog(self, cog_def)
                elif change_type == Change.modified and change_type != (
                    Change.added or Change.deleted
                ):
                    await load_cog(self, cog_def)


owner_id = int(os.getenv("OWNER_ID", 0))
message_cache_size = int(os.getenv("MESSAGE_CACHE_SIZE", 1000))
bot = LancoBot(
    command_prefix=".",
    intents=intents,
    owner_id=owner_id,
    max_messages=message_cache_size,
)


def init_logging():
    formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")

    file_logger = TimedRotatingFileHandler(
        "./logs/logfile.log", when="midnight", backupCount=10
    )
    file_logger.setFormatter(formatter)
    logger.addHandler(file_logger)

    console_logger = logging.StreamHandler()
    console_logger.setFormatter(formatter)
    logger.addHandler(console_logger)

    # supress discord logging
    # logging.getLogger('discord').setLevel(logging.WARNING)

    logger.setLevel(logging.INFO)


@bot.command(name="gsync")
@commands.is_owner()
async def guildsync(ctx):
    """Sync commands for a specific guild"""
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


@bot.tree.command(name="about", description="Some basic info about the bot")
async def about(interaction: discord.Interaction):
    fun_facts = [
        "🤖 I'm a bot created for the Lancaster County, PA Discord",
        "✨ I'm from B̶e̶r̶k̶s̶ Lancaster ✨",
        "🖥️ I'm open-source, check out my code on [GitHub](https://github.com/NateShoffner/Lanco-Discord-Bot)",
    ]

    embed = discord.Embed(
        title=f"About {bot.user.name}",
        description="\n\n".join([f"{fact}" for fact in fun_facts]),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ping", description="Ping the bot")
async def ping(interaction: discord.Interaction):
    lat = round(bot.latency * 1000)

    embed = discord.Embed(title="🏓 Pong!", color=0x00FF00)
    embed.add_field(name="Bot Latency", value=f"{lat}ms", inline=False)

    start = monotonic()
    msg = await interaction.response.send_message(embed=embed)
    end = monotonic()

    response_msg = await interaction.original_response()

    msg_latency = round((end - start) * 1000)

    embed.add_field(name="Message Latency", value=f"{msg_latency}ms", inline=False)
    await response_msg.edit(embed=embed)


@bot.tree.command(name="dbinfo", description="Show database info")
@commands.is_owner()
async def dbinfo(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Database Info",
        color=0x00FF00,
    )

    db_size = 0
    if db_type == DatabaseType.SQLITE:
        db_size = os.path.getsize(sqlite_path)
    elif db_type == DatabaseType.MYSQL:
        query = """
        SELECT SUM(data_length + index_length) 
        FROM information_schema.tables 
        WHERE table_schema = DATABASE();
        """
        cursor = database.execute_sql(query)
        db_size = cursor.fetchone()[0]  # in bytes

    embed.add_field(name="Type", value=f"{db_type.name}", inline=False)

    size_in_mb = db_size / 1024 / 1024
    embed.add_field(name="Size", value=f"{size_in_mb:.2f} MB", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="netstats", description="Show network stats")
async def netstats(interaction: discord.Interaction):
    is_owner = await bot.is_owner(interaction.user)

    embed = discord.Embed(
        title="Network Stats",
        description="Various network stats",
        color=0x00FF00,
    )

    ip = await get_external_ip()

    if is_owner:
        embed.add_field(name="External IP", value=ip, inline=False)
    else:
        embed.add_field(name="External IP", value="🔒 Hidden", inline=False)

    embed.add_field(
        name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="status", description="Show bot status")
async def status(interaction: discord.Interaction):
    info = await bot.application_info()

    embed = discord.Embed(
        title=f"{bot.user.name} Status",
        description=f"Various diagnostic information",
        color=0x00FF00,
    )

    embed.add_field(name="Python", value=f"{sysv.major}.{sysv.minor}.{sysv.micro}")
    embed.add_field(name="Discord.py", value=f"{discord.__version__}")
    embed.add_field(name="Guilds", value=f"{len(bot.guilds)}")
    embed.add_field(name="Users", value=f"{len(bot.users)}")
    embed.add_field(name="Commands", value=f"{len(bot.commands)}")
    embed.add_field(name="Slash Commands", value=f"{len(bot.tree.get_commands())}")
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms")
    embed.add_field(
        name="Dev Mode", value=f"{'Enabled' if bot.dev_mode else 'Disabled'}"
    )
    uptime = datetime.datetime.now() - bot.start_time
    embed.add_field(
        name="Uptime",
        value=f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds // 60) % 60}m {uptime.seconds % 60}s",
    )
    embed.add_field(name=f"Cogs", value=f"{len(bot.get_lanco_cogs())}")

    owner = bot.get_user(info.owner.id)
    embed.add_field(
        name="Owner", value=f"{owner.mention if owner else info.owner.global_name}"
    )

    # TODO set these as env during build
    commit = get_commit_hash()
    github = os.getenv("GITHUB_REPO")
    if github:
        commit_url = f"{github}/commit/{commit}"
        embed.add_field(name="Commit", value=f"[{commit[:7]}]({commit_url})")
    else:
        embed.add_field(name="Commit", value=f"{commit[:7]}")

    embed.add_field(name="Message Cache", value=f"{len(bot.cached_messages)}")
    embed.add_field(name="Voice Clients", value=f"{len(bot.voice_clients)}")

    application_emojis = await bot.fetch_application_emojis()
    embed.add_field(name="Emojis", value=f"{len(bot.emojis)}")
    embed.add_field(name="App Emojis", value=f"{len(application_emojis)}")
    embed.add_field(name="Stickers", value=f"{len(bot.stickers)}")

    embed.add_field(name="URL Handlers", value=f"{len(bot.url_handlers)}")

    version = get_bot_version()
    embed.set_footer(text=f"Version: {version}")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="devmode")
@is_bot_owner()
async def dev(interaction: discord.Interaction):
    bot.set_dev_mode(not bot.dev_mode)

    embed = discord.Embed(
        title="Dev Mode",
        description=f"{'Enabled' if bot.dev_mode else 'Disabled'}",
        color=0x00FF00,
    )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="cogs", description="List loaded cogs")
async def cogs(interaction: discord.Interaction):
    cogs = bot.get_lanco_cogs()
    cog_list = ""
    for cog in cogs:
        cog_list += f"{cog.qualified_name} - {cog.description}\n"
    embed = discord.Embed(
        title=f"Loaded Cogs: {len(cogs)}",
        description=f"```{cog_list}```",
        color=0x00FF00,
    )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="reload", description="Reload a cog")
@is_bot_owner()
async def reload_cog(interaction: discord.Interaction, cog_name: str):
    """Reload a single cog."""

    cog_def = get_cog_def(cog_name, COGS_DIR)
    result = await load_cog(bot, cog_def)

    embed = discord.Embed(
        title=f'Reloading Cog: "{cog_def.name}"',
        color=0x00FF00,
    )

    if result.loaded:
        embed.description = f"Loaded {cog_def.name}"
    elif result.reloaded:
        embed.description = f"Reloaded {cog_def.name}"
    elif result.error:
        embed.description = f"Error loading {cog_def.name}: ```{result.error}```"

    await interaction.response.send_message(embed=embed)


@dataclass
class CogLoadResult:
    definition: CogDefinition
    loaded: bool = False
    reloaded: bool = False
    unloaded: bool = False
    error: Optional[str] = None
    cog: Optional[LancoCog] = None


async def load_cog(bot: LancoBot, cog_def: CogDefinition) -> CogLoadResult:
    """Load a single cog."""
    is_already_loaded = bot.is_cog_loaded(cog_def.qualified_name)
    result = CogLoadResult(cog_def)

    try:
        if is_already_loaded:
            logger.info(f"Reloading {cog_def.name}: {cog_def.path}")

            await bot.reload_extension(cog_def.qualified_name)
        else:
            logger.info(f"Loading {cog_def.name}: {cog_def.path}")
            await bot.load_extension(cog_def.qualified_name)
        result.loaded = True
        result.cog = bot.get_lanco_cog_by_dotted_path(cog_def.qualified_name)
        result.cog.set_cog_def(cog_def)

    except Exception as e:
        logger.error(f"Failed to load cog {cog_def.name}: {e}")
        result.error = str(e)

    return result


async def load_cogs(bot: LancoBot) -> list[CogLoadResult]:
    """Load all cogs in the cogs directory."""
    results = []
    for entry in os.scandir(COGS_DIR):
        cog_def = get_cog_def(entry.name, COGS_DIR)
        if os.path.isfile(cog_def.entry_point):
            result = await load_cog(bot, cog_def)
            results.append(result)
    return results


async def unload_cog_by_name(bot: LancoBot, cog_name: str) -> CogLoadResult:
    """Unload a single cog."""
    cog = bot.get_lanco_cog(cog_name)
    cog_def = get_cog_def(cog_name, COGS_DIR)

    result = CogLoadResult(cog_def)
    cog = bot.get_lanco_cog_by_class_name(cog_name)
    if cog:
        try:
            logger.info(f"Unloading {cog_name}")
            await bot.unload_extension(f"cogs.{cog_name}.{cog_name}")
            result.unloaded = True
        except Exception as e:
            logger.error(f"Failed to unload cog {cog_name}: {e}")
            result.error = str(e)

    return result


@bot.tree.command(name="reloadall")
@is_bot_owner()
async def reload_all(interaction: discord.Interaction):
    """This commands reloads all the cogs in the `./cogs` folder."""

    embed = discord.Embed(
        title=f"[Re]-Loaded Cogs",
        color=0x00FF00,
    )

    results = await load_cogs(bot)

    reloaded_cogs = [result.cog.get_cog_name() for result in results if result.reloaded]
    loaded_cogs = [result.cog.get_cog_name() for result in results if result.loaded]
    errored_cogs = [result.definition.entry_point for result in results if result.error]

    reload_value = "None"
    if len(reloaded_cogs) > 0:
        reload_value = "```"
        reload_value += "\n".join(reloaded_cogs)
        reload_value += "```"
    embed.add_field(
        name=f"Reloaded ({len(reloaded_cogs)}):", value=reload_value, inline=False
    )

    load_value = "None"
    if len(loaded_cogs) > 0:
        load_value = "```"
        load_value += "\n".join(loaded_cogs)
        load_value += "```"
    embed.add_field(
        name=f"Loaded ({len(loaded_cogs)}):", value=load_value, inline=False
    )

    error_value = "None"
    if len(errored_cogs) > 0:
        error_value = "```"
        error_value += "\n".join(errored_cogs)
        error_value += "```"
        error_value += "\nRun the `/reload cog_name` command for more info"
    embed.add_field(
        name=f"Failed ({len(errored_cogs)}):", value=error_value, inline=False
    )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="unload")
@is_bot_owner()
async def unload_cog(interaction: discord.Interaction, cog_name: str):
    """Unload a single cog."""
    result = await unload_cog_by_name(bot, cog_name)

    embed = discord.Embed(
        title=f"Unloading Cog: {cog_name}",
        color=0x00FF00,
    )

    if result.unloaded:
        embed.description = f"Unloaded {cog_name}"
    elif result.error:
        embed.description = f"Error unloading {cog_name}: ```{result.error}```"

    await interaction.response.send_message(embed=embed)


@bot.check
async def global_block_check(ctx):
    if BlacklistedUser.get_or_none(user_id=ctx.author.id):
        return False

    return True


@bot.tree.command(name="optout")
async def optout(interaction: discord.Interaction):
    """Opt out of the bot."""
    user = interaction.user
    BlacklistedUser.create(user_id=user.id)
    await interaction.response.send_message(
        "You have opted out of the bot.", ephemeral=True
    )


@bot.tree.command(name="optin")
async def optin(interaction: discord.Interaction):
    """Opt in to the bot."""
    user = interaction.user
    u = BlacklistedUser.get_or_none(user_id=user.id)

    if not u:
        await interaction.response.send_message(
            "You are already opted in to the bot.", ephemeral=True
        )
        return

    u.delete_instance()
    await interaction.response.send_message(
        "You have opted in to the bot.", ephemeral=True
    )


@bot.tree.command(name="block")
@commands.is_owner()
async def block(interaction: discord.Interaction, user: discord.User, reason: str):
    """Block a user"""
    BlacklistedUser.create(user_id=user.id, reason=reason)
    await interaction.response.send_message(
        f"Blocked {user.mention} for {reason}", ephemeral=True
    )


@bot.tree.command(name="unblock")
@commands.is_owner()
async def unblock(interaction: discord.Interaction, user: discord.User):
    """Unblock a user"""
    u = BlacklistedUser.get_or_none(user_id=user.id)
    if not u:
        await interaction.response.send_message(
            f"{user.mention} is not blocked", ephemeral=True
        )
        return

    u.delete_instance()
    await interaction.response.send_message(f"Unblocked {user.mention}", ephemeral=True)


async def main():
    init_logging()
    await load_cogs(bot)
    await bot.start(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())

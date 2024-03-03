import asyncio
import datetime
import os
from typing import Optional
from dataclasses import dataclass
import discord
import logging
from discord.ext import commands
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
from peewee import *
from utils.dist_utils import get_bot_version, get_commit_hash
from db import database_proxy
from sys import version_info as sysv

load_dotenv()

logger = logging.getLogger()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents)

database = SqliteDatabase(os.getenv("SQLITE_DB"))
database_proxy.initialize(database)
database.connect()

# TODO probably a better way to inject a database into a cog
bot.database = database

# TODO set these as env during build
bot.version = get_bot_version()
bot.commit = get_commit_hash()

bot.start_time = datetime.datetime.now()

if not os.path.exists("./data"):
    os.makedirs("./data")

COGS_DIR = "./app/cogs"


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


@dataclass
class CogDefinition:
    path: str
    name: str
    qualified_name: str
    entry_point: str


def get_cog_def(name: str) -> CogDefinition:
    path = os.path.join(COGS_DIR, name)
    qualified_name = f"cogs.{name}.{name}"
    entry_point = f"{path}/{name}.py"
    return CogDefinition(path, name, qualified_name, entry_point)


@dataclass
class CogLoadResult:
    definition: CogDefinition
    loaded: bool = False
    reloaded: bool = False
    error: Optional[str] = None


async def load_cog(bot: commands.Bot, cog_def: CogDefinition) -> CogLoadResult:
    """Load a single cog."""

    current_loaded_cog_names = list(bot.cogs)
    is_already_loaded = False

    # we have to inspect the names manually because some cogs might use the name decorator to change the name
    for name in current_loaded_cog_names:
        c = bot.get_cog(name)
        true_name = c.__class__.__name__
        if true_name.lower() == cog_def.name.lower():
            is_already_loaded = True
            break

    result = CogLoadResult(cog_def)

    try:
        if is_already_loaded:
            logger.info(f"Reloading {cog_def.name}: {cog_def.path}")
            await bot.reload_extension(f"cogs.{cog_def.name}.{cog_def.name}")
            result.reloaded = True
        else:
            logger.info(f"Loading {cog_def.name}: {cog_def.path}")
            await bot.load_extension(f"cogs.{cog_def.name}.{cog_def.name}")
            result.loaded = True
    except Exception as e:
        logger.error(f"Failed to load cog {cog_def.name}: {e}")
        result.error = str(e)

    return result


async def load_cogs(bot: commands.Bot) -> list[CogLoadResult]:
    """Load all cogs in the `./cogs` directory."""
    results = []
    for entry in os.scandir(COGS_DIR):
        cog_def = get_cog_def(entry.name)
        if os.path.isfile(cog_def.entry_point):
            result = CogLoadResult(cog_def)
            try:
                result = await load_cog(bot, cog_def)
            except:
                pass
            results.append(result)
    return results


@bot.event
async def on_ready():
    logger.info(f"{bot.user} is now running!")


@bot.command(name="sync")
@commands.is_owner()
async def sync(ctx):
    logger.info("Syncing commands")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands")
        await ctx.send(f"Synced {len(synced)} commands")
    except Exception as e:
        logger.error(e)


@bot.tree.command(name="about", description="Some basic info about the bot")
async def about(interaction: discord.Interaction):
    fun_facts = [
        "🤖 I'm a bot created for the Lancaster Discord",
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
    embed = discord.Embed(title="Pong!", description=f"🏓 {lat} ms", color=0x00FF00)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="status", description="Show bot status")
async def status(interaction: discord.Interaction):
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
    uptime = datetime.datetime.now() - bot.start_time
    embed.add_field(
        name="Uptime",
        value=f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds // 60) % 60}m {uptime.seconds % 60}s",
    )

    cog_names = [cog.get_cog_name() for cog in bot.cogs.values()]
    embed.add_field(name=f"Cogs ({len(cog_names)})", value=", ".join(cog_names))

    embed.set_footer(text=f"Version: {bot.version} | Commit: {bot.commit[:7]}")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="cogs", description="List loaded cogs")
async def cogs(interaction: discord.Interaction):
    cogs = bot.cogs.values()
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
@commands.is_owner()
async def reload_cog(interaction: discord.Interaction, cog_name: str):
    cog_def = get_cog_def(cog_name)
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


@bot.tree.command(name="reloadall")
@commands.is_owner()
async def reload_all(interaction: discord.Interaction):
    """This commands reloads all the cogs in the `./cogs` folder."""

    embed = discord.Embed(
        title=f"[Re]-Loaded Cogs",
        color=0x00FF00,
    )

    results = await load_cogs(bot)

    reloaded_cogs = [result.definition.name for result in results if result.reloaded]
    loaded_cogs = [result.definition.name for result in results if result.loaded]
    errored_cogs = [result.definition.name for result in results if result.error]

    reload_value = "None"
    if len(reloaded_cogs) > 0:
        reload_value = f"```{', '.join(reloaded_cogs)}```"
    embed.add_field(
        name=f"Reloaded {len(reloaded_cogs)}:", value=reload_value, inline=False
    )

    load_value = "None"
    if len(loaded_cogs) > 0:
        load_value = f"```{', '.join(loaded_cogs)}```"
    embed.add_field(name=f"Loaded {len(loaded_cogs)}:", value=load_value, inline=False)

    error_value = "None"
    if len(errored_cogs) > 0:
        error_value = f"```{', '.join(errored_cogs)}```\n\n"
        error_value += "Run the `/reload cog_name` command for more info"
    embed.add_field(
        name=f"Errors {len(errored_cogs)}:", value=error_value, inline=False
    )

    await interaction.response.send_message(embed=embed)


async def main():
    init_logging()
    await load_cogs(bot)

    await bot.start(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())

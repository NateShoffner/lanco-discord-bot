import asyncio
import datetime
import os
import discord
import logging
from discord.ext import commands
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
from peewee import *
from utils.dist_utils import get_bot_version, get_commit_hash
from db import database_proxy

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


async def load_cogs(bot: commands.Bot, reload: bool = False):
    cogs_dir = "./app/cogs"
    for entry in os.scandir(cogs_dir):
        entry_path = os.path.join(entry.path, f"{entry.name}.py")
        if os.path.isfile(entry_path):
            print(f"Loading {entry.name}: {entry_path}")
            try:
                if reload:
                    await bot.reload_extension(f"cogs.{entry.name}.{entry.name}")
                else:
                    await bot.load_extension(f"cogs.{entry.name}.{entry.name}")
            except Exception as e:
                print(f"Failed to load cog {entry.name}: {e}")


@bot.event
async def on_ready():
    logger.info(f"{bot.user} is now running!")


# TODO doesn't work unless mentioned explicitly
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


@commands.command(name="reloadall", hidden=True)
@commands.is_owner()
async def reload_all(self, ctx):
    """This commands reloads all the cogs in the `./cogs` folder.

    Note:
        This command can be used only from the bot owner.
        This command is hidden from the help menu.
        This command deletes its messages after 20 seconds."""

    message = await ctx.send("Reloading...")
    await ctx.message.delete()
    try:
        await load_cogs(self.bot, reload=True)
    except Exception as exc:
        await message.edit(content=f"An error has occurred: {exc}", delete_after=20)
    else:
        await message.edit(content="All cogs have been reloaded.", delete_after=20)


async def main():
    init_logging()
    await load_cogs(bot)

    await bot.start(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())

from discord.ext import commands
import logging


class LancoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(self.__get_cog_name())

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f"{self.__get_cog_name()} cog loaded")

    def __get_cog_name(self):
        return self.__class__.__name__

    def get_cog_data_directory(self):
        return f"data/{self.__get_cog_name()}"

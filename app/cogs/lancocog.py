from discord.ext import commands


class LancoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{self.__get_cog_name()} cog loaded")

    def __get_cog_name(self):
        return self.__class__.__name__

    def get_cog_data_directory(self):
        return f"data/{self.__get_cog_name()}"

🌹 LancoBot
----------------

Commmunity Discord bot for the Lancaster County Discord server.

🎉 Features
----------------

- [Incident Reporting](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/incidents) - Report emergency services incidents throughout Lancaster County.
- [Custom Commands](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/commands) - Create custom commands for your server.
- [TwitterEmbed](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/twitterembed) - Fix Twitter/X embeds in Discord.
- [InstaEmbed](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/instaembed) - Fix Instagram embeds in Discord.
- [TikTokEmbed](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/tiktokembed) - Fix TikTok embeds in Discord.
- [GeoGuesser](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/geoguesser) - Lancaster County/City tailored GeoGuessr.
- [BarHopper](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/barhopper) - Find bars within Lancaster City.
- [BusFinder](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/busfinder) - Find RRTA bus schedules and plan trips.
- [Weather](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/weather) - Get the current weather and forecast for any location.
- [AnimeToday](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/animetoday) - Display an anime screenshot featuring the current date every morning in a specified channel.
- [SpotifyEmbed](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/spotifyembed) - Alternative Spotify embeds in Discord.
- [RedditEmbed](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/redditembed) - Fix Reddit embeds in Discord.
- [OneWordStory](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/onewordstory) - Create a one word story with your friends.

🚀 Installation
----------------

```
git clone https://github.com/NateShoffner/lanco-discord-bot
cd lanco-discord-bot
poetry install
```

Note: Docker support is coming soon™.

🚀 Running
----------------

Copy the .env.default file and create a .env file with your bot token and other settings.

```
poetry run python app/main.py
```

🛠️ Contribute
-------------------

Feel free to fork and submit pull requests for any features or fixes you think should be included.

👉 Support
-------------------

If you need help with the bot join the [Lancaster County Discord](https://discord.gg/yfFp4VaZFt) or [open an issue](https://github.com/NateShoffner/lanco-discord-bot/issues/new).

📝 License
-------------------

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


📂 Project Structure
-------------------

    .
    ├── app                     # Main application directory
    │   ├── cogs                # Discord cogs
    │   └── utils               # Utility functions
    ├── data                    # Data files
    ├── logs                    # Log files
    └── migrations              # Database migrations

⚙️ Cog Development
-------------------

To create a new cog, create a new folder in the [cogs](app/cogs) directory with the name of your cog and an entrypoint script within it with the same name as the folder.

```bash
mkdir app/cogs/yourcog
touch app/cogs/yourcog/yourcog.py
```

All cogs should inherit from the [LancoCog](app/cogs/lancocog.py) class.

```python
import discord
from discord.ext import commands
from cogs.lancocog import LancoCog

class YourCog(LancoCog, name="YourCog", description="Your cog description."):

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

async def setup(bot):
    await bot.add_cog(YourCog(bot))
```
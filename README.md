🌹 LancoBot
----------------

Discord bot tailored for Lancaster Count, PA.

🎉 Features
----------------

The bot features a variety of cogs that can be enabled or disabled depending on your server's needs. The following cogs are available:

- [Incident Reporting](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/incidents) - Report emergency services incidents throughout Lancaster County.
- [Custom Commands](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/commands) - Create custom commands for your server.
- [TwitterEmbed](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/twitterembed) - Fix Twitter/X embeds in Discord.
- [InstaEmbed](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/instaembed) - Fix Instagram embeds in Discord.
- [TikTokEmbed](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/tiktokembed) - Fix TikTok embeds in Discord.
- [GeoGuesser](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/geoguesser) - Lancaster County/City tailored GeoGuessr.
- [BarHopper](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/barhopper) - Find bars within Lancaster City.
- [Weather](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/weather) - Get the current weather and forecast for any location.
- [AnimeToday](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/animetoday) - Display an anime screenshot featuring the current date every morning in a specified channel.
- [SpotifyEmbed](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/spotifyembed) - Alternative Spotify embeds in Discord.
- [RedditEmbed](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/redditembed) - Fix Reddit embeds in Discord.
- [OneWordStory](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/onewordstory) - Create a one word story with your friends.
- [TraceMoe](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/tracemoe) - Reverse image search for anime screenshots.
- [Facts](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/facts) - Define and display facts.
- [RedditFeed](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/redditfeed) - Subscribe to subreddits and receive updates in your server.
- [OpenAIPrompts](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/openaiprompts) - Generate creative writing prompts.
- [Magic8Ball](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/magic8ball) - Ask the Magic 8 Ball a question.
- [Birthday](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/birthday) - Set and display user birthdays.
- [Google](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/google) - Let me Google that for you.

🚀 Installation
----------------

First you will need to clone the repository:

```bash
git clone https://github.com/NateShoffner/lanco-discord-bot
```

Next, go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application. Create a bot for the application and copy the token. You will need to add the bot to your server using the OAuth2 URL generated in the portal.

Copy the `.env.default` file and create a `.env` file with your bot token and other settings including the SQLite database path.

The other API keys are optional depending on what cogs you want to enable.

You'll need to install the dependencies using [Poetry](https://python-poetry.org/):

```bash
cd lanco-discord-bot
poetry install
```

After installing the dependencies, you can run the bot using the following command:

```bash
poetry run python app/main.py
```

### 🐳 Docker

Alternatively, you can use [Docker](https://www.docker.com/) to run the bot via `docker-compose`.

Cogs are generally disabled by default. Please refer to the [cogs](app/cogs) directory for more information on how to use them.

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

All features are implemented as cogs in the [cogs](app/cogs) directory.

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
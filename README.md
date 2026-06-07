# 🌹 LancoBot

General-purpose Discord bot with some tailored features for Lancaster County, PA.

## 🎉 Features

The bot is built around a modular cog system. Each cog is self-contained and can be enabled or disabled independently. The following cogs are available:

|  |  |  |
|---|---|---|
| [TipCalc](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/tipcalc)<br>Tip calculator | [Magic8Ball](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/magic8ball)<br>Magic 8 Ball | [Twitter/X Embed Fix](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/twitterembed)<br>Fix Twitter/X embeds |
| [TruthSocial](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/TruthSocial)<br>TruthSocial embed support | [RedditEmbed](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/redditembed)<br>Reddit embed fix | [BarHopper](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/barhopper)<br>Bar hopper commands |
| [OneWordStory](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/onewordstory)<br>One word story game | [RoleStats](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/rolestats)<br>Server role statistics | [PeeCheck](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/peecheck)<br>PeeCheck cog |
| [AIDetection](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/AIDetection)<br>Detect AI-generated content | [Fishbowl](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/fishbowl)<br>Fishbowl cog | [Conversions](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/conversions)<br>Unit conversions |
| [AutoResponse](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/autoresponse)<br>Keyword auto-responses | [ChatBot](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/chatbot)<br>User-specific chatbot with agent memory | [RedditFeed](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/redditfeed)<br>Reddit feed polling |
| [NewsHeadlines](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/newsheadlines)<br>News headlines | [Everbridge](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/everbridge)<br>Everbridge alerts | [RandomNsfwReddit](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/randomnsfwreddit)<br>Random NSFW Reddit posts |
| [Google](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/google)<br>Google search | [SleepCheck](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/sleepcheck)<br>Sleep check commands | [ReactTrack](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/reacttrack)<br>Track reactions |
| [WolframAlpha](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/wolframalpha)<br>Wolfram Alpha queries | [GameStats](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/gamestats)<br>Server game stats | [Admin](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/admin)<br>Admin commands |
| [Summarize](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/summarize)<br>Summarize messages | [Fun](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/fun)<br>Fun commands | [AnimeToday](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/animetoday)<br>Daily anime announcements |
| [Pinboard](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/pinboard)<br>Pin messages | [Birthday](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/birthday)<br>Birthday announcements | [Youtube](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/youtube)<br>YouTube feed polling |
| [GeoGuesser](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/geoguesser)<br>Lancaster-themed GeoGuesser | [InstaEmbed](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/instaembed)<br>Instagram embed fix | [Describe](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/describe)<br>Describe images via context menu |
| [Database Backupper](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/databasebackupper)<br>Scheduled DB backups | [NutCheck](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/nutcheck)<br>NutCheck cog | [SpyDotKick](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/spydotpet)<br>Detect loser bots |
| [HotDog](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/hotdog)<br>Profile glizzies | [MarkSafe](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/marksafe)<br>Mark yourself safe | [EmoteTools](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/emotetools)<br>Emote and sticker tools |
| [Verification](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/verification)<br>Member verification | [WebPreview](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/webpreview)<br>Web link previews | [TraceMoe](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/tracemoe)<br>Identify anime from screenshots |
| [FixIt](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/fixit)<br>FixIt issue tracking | [UserProfiles](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/profile)<br>Custom user profiles | [PDFPreview](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/pdfpreview)<br>PDF preview generation |
| [FortuneCookie](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/fortunecookie)<br>Fortune cookies | [Spotify Embed Fix](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/spotifyembed)<br>Fix Spotify embeds | [AutoReact](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/autoreact)<br>Keyword auto-reactions |
| [TextGen](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/textgen)<br>Text generator | [Bot](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/bot)<br>Bot configuration | [FileFixer](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/filefixer)<br>Attempt to fix files |
| [Weather](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/weather)<br>Weather lookup | [Commands](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/commands)<br>Custom guild commands | [Paywall Bypass](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/paywallbypass)<br>Bypass paywalls |
| [Genshin](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/genshin)<br>Genshin Impact commands | [Anime](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/anime)<br>Anime commands | [CoinFlip](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/CoinFlip)<br>Flip a coin |
| [Facts](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/facts)<br>Random facts | [dadjoke](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/dadjoke)<br>Dad jokes | [Transcribe](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/transcribe)<br>Transcribe audio files |
| [ADHDChannel](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/adhdchannel)<br>Dynamic channel topic updates | [Incidents](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/incidents)<br>LCWC incident feed | [TikTok Embed Fix](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/tiktokembed)<br>Fix TikTok embeds |
| [OpenAIPrompts](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/aiprompts)<br>AI-powered prompts | [Astrology](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/astrology)<br>Astrology commands | [Whisper](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/whisper)<br>Whisper transcription |
| [RSSFeed](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/rssfeed)<br>RSS feed polling | [RemindMe](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/remindme)<br>Set reminders | [Counter](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/counter)<br>Counting channel |
| [ScheduledPost](https://github.com/NateShoffner/lanco-discord-bot/tree/master/app/cogs/ScheduledPost)<br>Schedule recurring posts | | |

## 🚀 Installation

Clone the repository:

```bash
git clone https://github.com/NateShoffner/lanco-discord-bot
cd lanco-discord-bot
```

Go to the [Discord Developer Portal](https://discord.com/developers/applications), create a new application and bot, and copy the token.

Copy `.env.default` to `.env` and fill in your bot token and any API keys for the cogs you want to use:

```bash
cp .env.default .env
```

Install dependencies:

```bash
poetry install
```

Run in dev mode (hot-reload enabled):

```bash
poetry run dev
```

### 🐳 Docker

```bash
docker-compose up --build
```

## 🛠️ Contribute

Feel free to fork and submit pull requests for any features or fixes you think should be included.

## 👉 Support

Join the [Lancaster County Discord](https://discord.gg/yfFp4VaZFt) or [open an issue](https://github.com/NateShoffner/lanco-discord-bot/issues/new).

## 📝 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## 📂 Project Structure

```
.
├── app/
│   ├── cogs/        # Discord cogs
│   └── utils/       # Utility functions
├── data/            # Runtime data (SQLite DB, cog-specific files)
├── logs/            # Log files
├── migrations/      # Database migrations
├── tests/           # Test suite
└── tools/           # Dev tooling and cog scaffolding
```

## ⚙️ Cog Development

### Scaffold a new cog

```bash
poetry run cog create --name MyCog --description "My description"
```

### Manual setup

```bash
mkdir app/cogs/yourcog
touch app/cogs/yourcog/__init__.py
touch app/cogs/yourcog/yourcog.py
```

Each cog directory must have an `__init__.py` that re-exports `setup`:

```python
# app/cogs/yourcog/__init__.py
from .yourcog import setup
```

All cogs inherit from `LancoCog`:

```python
from cogs.lancocog import LancoCog
from discord.ext import commands

class YourCog(LancoCog, name="YourCog", description="Your cog description."):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    async def cog_load(self):
        await super().cog_load()
        # initialize tables, start tasks, etc.

async def setup(bot):
    await bot.add_cog(YourCog(bot))
```

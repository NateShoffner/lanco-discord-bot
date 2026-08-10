# 🌹 LancoBot

General-purpose Discord bot with some tailored features for Lancaster County, PA.

## 🎉 Features

The bot is built around a modular cog system. Each cog is self-contained and can be enabled or disabled independently.

| Cog | Cog |
|---|---|
| [ADHDChannel](app/cogs/adhdchannel) - Dynamic channel topic updates | [AIDetection](app/cogs/AIDetection) - Detect AI-generated content |
| [Admin](app/cogs/admin) - Admin commands | [Anime](app/cogs/anime) - Anime info lookup |
| [AnimeToday](app/cogs/animetoday) - Daily anime announcements | [Astrology](app/cogs/astrology) - Horoscope readings |
| [AutoReact](app/cogs/autoreact) - Keyword auto-reactions | [AutoResponse](app/cogs/autoresponse) - Keyword auto-responses |
| [BarHopper](app/cogs/barhopper) - Bar hopper commands | [Birthday](app/cogs/birthday) - Birthday announcements |
| [Bot](app/cogs/bot) - Bot configuration | [Captcha](app/cogs/captcha) - Captcha guessing game |
| [ChatBot](app/cogs/chatbot) - AI chatbot with per-user memory | [CoinFlip](app/cogs/CoinFlip) - Flip a coin |
| [Commands](app/cogs/commands) - Custom guild commands | [Conversions](app/cogs/conversions) - Unit conversions |
| [Counter](app/cogs/counter) - Counting channel game | [DadJoke](app/cogs/dadjoke) - Dad jokes |
| [Describe](app/cogs/describe) - Describe images via context menu | [EmoteTools](app/cogs/emotetools) - Emote and sticker tools |
| [Everbridge](app/cogs/everbridge) - Everbridge alerts | [FacebookEmbed](app/cogs/facebookembed) - Facebook embed fix (posts, events, pages, reels) |
| [Facts](app/cogs/facts) - Random facts | [FileFixer](app/cogs/filefixer) - Convert unsupported file types |
| [Fishbowl](app/cogs/fishbowl) - Auto-expiring message channels | [FixIt](app/cogs/fixit) - SeeClickFix issue feed |
| [FortuneCookie](app/cogs/fortunecookie) - Fortune cookies | [Fun](app/cogs/fun) - Fun commands |
| [GameStats](app/cogs/gamestats) - Server game statistics | [GeoGuesser](app/cogs/geoguesser) - Lancaster-themed GeoGuesser |
| [Genshin](app/cogs/genshin) - Genshin Impact commands | [Google](app/cogs/google) - Google search links |
| [HotDog](app/cogs/hotdog) - Profile glizzies | [Incidents](app/cogs/incidents) - LCWC incident feed |
| [InstaEmbed](app/cogs/instaembed) - Instagram embed fix | [JeffVacation](app/cogs/JeffVacation) - Countdown to Jeff's vacation |
| [JiraHate](app/cogs/JiraHate) - Random IFuckingHateJira quotes | [Magic8Ball](app/cogs/magic8ball) - Magic 8 Ball |
| [NewsHeadlines](app/cogs/newsheadlines) - News headlines | [NutCheck](app/cogs/nutcheck) - No Nut November tracker |
| [OneWordStory](app/cogs/onewordstory) - Collaborative one-word story | [OpenAIPrompts](app/cogs/aiprompts) - AI-powered prompts |
| [PasswordGenerator](app/cogs/PasswordGenerator) - Generate random passwords | [PaywallBypass](app/cogs/paywallbypass) - Bypass Lancaster Online paywall |
| [PDFPreview](app/cogs/pdfpreview) - PDF preview generation | [PeeCheck](app/cogs/peecheck) - Hydration tracker |
| [Pinboard](app/cogs/pinboard) - Personal message pinboard | [Profile](app/cogs/profile) - Custom user profiles |
| [R9K](app/cogs/r9k) - Unique-message-only channel mode | [ReactTrack](app/cogs/reacttrack) - Reaction analytics |
| [RedditEmbed](app/cogs/redditembed) - Reddit embed fix | [RedditFeed](app/cogs/redditfeed) - Subreddit feed polling |
| [RemindMe](app/cogs/remindme) - Set reminders | [RoleStats](app/cogs/rolestats) - Server role statistics |
| [RSSFeed](app/cogs/rssfeed) - RSS feed polling | [ScheduledPost](app/cogs/ScheduledPost) - Schedule recurring posts |
| [SleepCheck](app/cogs/sleepcheck) - Sleep hour leaderboard | [SpotifyEmbed](app/cogs/spotifyembed) - Spotify embed fix |
| [SpyDotPet](app/cogs/spydotpet) - Detect suspicious bots | [Summarize](app/cogs/summarize) - Channel topic and vibe summaries |
| [System](app/cogs/system) - Bot status and admin info | [TechLanc](app/cogs/TechLanc) - Tech Lancaster meetup announcements |
| [TikTokEmbed](app/cogs/tiktokembed) - TikTok embed fix | [TipCalc](app/cogs/tipcalc) - Tip calculator |
| [TraceMoe](app/cogs/tracemoe) - Identify anime from screenshots | [Transcribe](app/cogs/transcribe) - Transcribe audio files |
| [TruthSocial](app/cogs/TruthSocial) - TruthSocial embed support | [Twitter/X Embed](app/cogs/twitterembed) - Twitter/X embed fix |
| [User](app/cogs/user) - User opt-in/opt-out | [Verification](app/cogs/verification) - Vote-based member verification |
| [Weather](app/cogs/weather) - Weather lookup | [WebPreview](app/cogs/webpreview) - Web link previews |
| [WebServer](app/cogs/webserver) - Embedded status web server | [WolframAlpha](app/cogs/wolframalpha) - Wolfram Alpha queries |
| [YouTube](app/cogs/youtube) - YouTube channel feed polling |  |

## 🚀 Installation

```bash
git clone https://github.com/NateShoffner/lanco-discord-bot
cd lanco-discord-bot
cp .env.default .env   # fill in your bot token and any cog API keys
poetry install
poetry run dev          # hot-reload dev mode
```

Get a bot token from the [Discord Developer Portal](https://discord.com/developers/applications).

### 🐳 Docker

```bash
docker-compose up --build
```

## 📊 Monitoring (optional)

The bot can report uncaught exceptions to [Elastic APM](https://www.elastic.co/observability/application-performance-monitoring), with stack traces and labels (command/cog/guild/user). It's enabled only when `ELASTIC_APM_SERVER_URL` is set:

```bash
ELASTIC_APM_SERVER_URL=https://<id>.apm.<region>.cloud.es.io:443
ELASTIC_APM_SECRET_TOKEN=<token>   # or ELASTIC_APM_API_KEY
ELASTIC_APM_SERVICE_NAME=lanco-bot # optional
```

## 🛠️ Contribute

Feel free to fork and submit pull requests for any features or fixes you think should be included.

## 📝 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

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

Scaffold a new cog:

```bash
poetry run cog create --name MyCog --description "My description"
```

Each cog directory needs an `__init__.py` that re-exports `setup`, and inherits from `LancoCog`:

```python
# app/cogs/yourcog/__init__.py
from .yourcog import setup
```

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

# 🌹 LancoBot

General-purpose Discord bot with some tailored features for Lancaster County, PA.

## 🎉 Features

The bot is built around a modular cog system. Each cog is self-contained and can be enabled or disabled independently.

- [ADHDChannel](app/cogs/adhdchannel) — Dynamic channel topic updates
- [AIDetection](app/cogs/AIDetection) — Detect AI-generated content
- [Admin](app/cogs/admin) — Admin commands
- [Anime](app/cogs/anime) — Anime info lookup
- [AnimeToday](app/cogs/animetoday) — Daily anime announcements
- [Astrology](app/cogs/astrology) — Horoscope readings
- [AutoReact](app/cogs/autoreact) — Keyword auto-reactions
- [AutoResponse](app/cogs/autoresponse) — Keyword auto-responses
- [BarHopper](app/cogs/barhopper) — Bar hopper commands
- [Birthday](app/cogs/birthday) — Birthday announcements
- [Bot](app/cogs/bot) — Bot configuration
- [ChatBot](app/cogs/chatbot) — AI chatbot with per-user memory
- [ChatRelay](app/cogs/chatrelay) — Cross-server message relay
- [CoinFlip](app/cogs/CoinFlip) — Flip a coin
- [Commands](app/cogs/commands) — Custom guild commands
- [Conversions](app/cogs/conversions) — Unit conversions
- [Counter](app/cogs/counter) — Counting channel game
- [DadJoke](app/cogs/dadjoke) — Dad jokes
- [DatabaseBackupper](app/cogs/databasebackupper) — Scheduled DB backups
- [Describe](app/cogs/describe) — Describe images via context menu
- [EmoteTools](app/cogs/emotetools) — Emote and sticker tools
- [Everbridge](app/cogs/everbridge) — Everbridge alerts
- [Facts](app/cogs/facts) — Random facts
- [FileFixer](app/cogs/filefixer) — Convert unsupported file types
- [Fishbowl](app/cogs/fishbowl) — Auto-expiring message channels
- [FixIt](app/cogs/fixit) — SeeClickFix issue feed
- [FortuneCookie](app/cogs/fortunecookie) — Fortune cookies
- [Fun](app/cogs/fun) — Fun commands
- [GameStats](app/cogs/gamestats) — Server game statistics
- [GeoGuesser](app/cogs/geoguesser) — Lancaster-themed GeoGuesser
- [Genshin](app/cogs/genshin) — Genshin Impact commands
- [Google](app/cogs/google) — Google search links
- [HotDog](app/cogs/hotdog) — Profile glizzies
- [Incidents](app/cogs/incidents) — LCWC incident feed
- [InstaEmbed](app/cogs/instaembed) — Instagram embed fix
- [Magic8Ball](app/cogs/magic8ball) — Magic 8 Ball
- [MarkSafe](app/cogs/marksafe) — Mark yourself safe/unsafe
- [NewsHeadlines](app/cogs/newsheadlines) — News headlines
- [NutCheck](app/cogs/nutcheck) — No Nut November tracker
- [OneWordStory](app/cogs/onewordstory) — Collaborative one-word story
- [OpenAIPrompts](app/cogs/aiprompts) — AI-powered prompts
- [PaywallBypass](app/cogs/paywallbypass) — Bypass Lancaster Online paywall
- [PDFPreview](app/cogs/pdfpreview) — PDF preview generation
- [PeeCheck](app/cogs/peecheck) — Hydration tracker
- [PetTax](app/cogs/pettax) — Pet tax enforcement
- [Pinboard](app/cogs/pinboard) — Personal message pinboard
- [Profile](app/cogs/profile) — Custom user profiles
- [RandomNSFWReddit](app/cogs/randomnsfwreddit) — Random NSFW subreddits
- [ReactTrack](app/cogs/reacttrack) — Reaction analytics
- [RedditEmbed](app/cogs/redditembed) — Reddit embed fix
- [RedditFeed](app/cogs/redditfeed) — Subreddit feed polling
- [RemindMe](app/cogs/remindme) — Set reminders
- [RoleStats](app/cogs/rolestats) — Server role statistics
- [RSSFeed](app/cogs/rssfeed) — RSS feed polling
- [ScheduledPost](app/cogs/ScheduledPost) — Schedule recurring posts
- [SleepCheck](app/cogs/sleepcheck) — Sleep hour leaderboard
- [SpotifyDaylist](app/cogs/spotifydaylist) — Spotify daylist tracking
- [SpotifyEmbed](app/cogs/spotifyembed) — Spotify embed fix
- [SpyDotPet](app/cogs/spydotpet) — Detect suspicious bots
- [Summarize](app/cogs/summarize) — Channel topic and vibe summaries
- [System](app/cogs/system) — Bot status and admin info
- [TextGen](app/cogs/textgen) — Text effects (zalgo, etc.)
- [TikTokEmbed](app/cogs/tiktokembed) — TikTok embed fix
- [TipCalc](app/cogs/tipcalc) — Tip calculator
- [TraceMoe](app/cogs/tracemoe) — Identify anime from screenshots
- [Transcribe](app/cogs/transcribe) — Transcribe audio files
- [TruthSocial](app/cogs/TruthSocial) — TruthSocial embed support
- [Twitter/X Embed](app/cogs/twitterembed) — Twitter/X embed fix
- [User](app/cogs/user) — User opt-in/opt-out
- [Verification](app/cogs/verification) — Vote-based member verification
- [Weather](app/cogs/weather) — Weather lookup
- [WebPreview](app/cogs/webpreview) — Web link previews
- [WebServer](app/cogs/webserver) — Embedded status web server
- [Whisper](app/cogs/whisper) — Send private messages
- [WolframAlpha](app/cogs/wolframalpha) — Wolfram Alpha queries
- [YouTube](app/cogs/youtube) — YouTube channel feed polling

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

"""Tortoise model registry (issue #149 cutover).

This module is the single entry in db.TORTOISE_MODEL_MODULES. Every ported
model is re-exported here, and Tortoise discovers models re-exported into a
module's namespace just as it does ones defined there.

Why an aggregator instead of listing "cogs.<name>.models" directly: a dotted
import of a cog's models.py executes that cog package's __init__.py first,
which pulls in the entire cog (discord, aiohttp, and any optional native deps
like cairosvg). DB init would then depend on every cog importing cleanly, so
one cog with a missing optional dependency would take the whole bot's database
down instead of just failing that cog's load. Loading each models.py by file
path sidesteps the package __init__ entirely -- the same technique
tests/test_db_baseline.py already uses, for the same reason.

To port a cog: convert its models.py to Tortoise, then add a _load() line here.
"""

import datetime
import importlib.util
import os
import sys

from tortoise import fields
from tortoise.models import Model

_COGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cogs")


def _load(cog: str, filename: str = "models.py"):
    """Import a cog's model module by file path, bypassing its __init__.py.

    Registered in sys.modules under its REAL dotted name ("cogs.<cog>.models"),
    which is load-bearing in both directions:

    - Executing the file directly means the cog package's __init__.py never
      runs, so DB init doesn't depend on every cog (and its optional native
      dependencies) importing cleanly.
    - Caching it under the real name means the cog's own `from .models import
      X` resolves to *this* module object instead of importing the file a
      second time. Without that there are two distinct copies of every model
      class: the one registered with Tortoise, and the one the cog actually
      queries through, which has no connection bound and fails at runtime with
      "default_connection ... cannot be None".
    """
    module_name = f"cogs.{cog}.{filename[:-3]}"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached
    path = os.path.join(_COGS_DIR, cog, filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class BlacklistedUser(Model):
    # generated=False is required: this PK is an application-supplied Discord
    # snowflake, not a generated sequence. Without it Tortoise emits
    # "INTEGER PRIMARY KEY AUTOINCREMENT", which silently downgrades BIGINT to
    # INTEGER and makes create() with no user_id succeed with user_id=1 rather
    # than raising. Applies to every snowflake-keyed model in this codebase.
    user_id = fields.BigIntField(primary_key=True, generated=False)
    reason = fields.TextField(null=True)
    created_at = fields.DatetimeField(default=datetime.datetime.now)

    class Meta:
        table = "blacklisted_users"


# --- Ported cog models -----------------------------------------------------
# Embed-fix family. See cogs/common/embedfixcog.py for why two PK shapes exist.

_facebookembed = _load("facebookembed")
FacebookEmbedConfig = _facebookembed.FacebookEmbedConfig

_redditembed = _load("redditembed")
RedditEmbedConfig = _redditembed.RedditEmbedConfig

_paywallbypass = _load("paywallbypass")
PaywallBypassConfig = _paywallbypass.PaywallBypassConfig
PaywallPattern = _paywallbypass.PaywallPattern

_instaembed = _load("instaembed")
InstaEmbedConfig = _instaembed.InstaEmbedConfig

_tiktokembed = _load("tiktokembed")
TikTokEmbedConfig = _tiktokembed.TikTokEmbedConfig

_twitterembed = _load("twitterembed")
TwitterEmbedConfig = _twitterembed.TwitterEmbedConfig

_truthsocial = _load("TruthSocial")
TruthSocialEmbedConfig = _truthsocial.TruthSocialEmbedConfig

_filefixer = _load("filefixer")
FileFixerConfig = _filefixer.FileFixerConfig

_fixit = _load("fixit")
FixItConfig = _fixit.FixItConfig

_transcribe = _load("transcribe")
TranscribeConfig = _transcribe.TranscribeConfig

# Simple per-guild config cogs.

_autoreact = _load("autoreact")
AutoReactConfig = _autoreact.AutoReactConfig

_autoresponse = _load("autoresponse")
AutoResponseConfig = _autoresponse.AutoResponseConfig

_animetoday = _load("animetoday")
AnimeTodayConfig = _animetoday.AnimeTodayConfig

_counter = _load("counter")
CounterConfig = _counter.CounterConfig

_counting = _load("counting")
CountingConfig = _counting.CountingConfig

_webpreview = _load("webpreview")
WebPreviewConfig = _webpreview.WebPreviewConfig

_spotifyembed = _load("spotifyembed")
SpotifyEmbedConfig = _spotifyembed.SpotifyEmbedConfig

_spotifydaylist = _load("spotifydaylist")
SpotifyDaylistConfig = _spotifydaylist.SpotifyDaylistConfig

# Feed pollers, scheduling, and moderation.

_incidents = _load("incidents")
IncidentsGlobalConfig = _incidents.IncidentsGlobalConfig
IncidentConfig = _incidents.IncidentConfig

_r9k = _load("r9k")
R9KConfig = _r9k.R9KConfig
R9KMessage = _r9k.R9KMessage

_techlanc = _load("TechLanc")
TechLancConfig = _techlanc.TechLancConfig
TechLancGuildConfig = _techlanc.TechLancGuildConfig
TechLancAllowedPoster = _techlanc.TechLancAllowedPoster

_scheduledpost = _load("ScheduledPost")
ScheduledPost = _scheduledpost.ScheduledPost

_remindme = _load("remindme")
Reminder = _remindme.Reminder

# Content, feeds, and misc utilities.

_dadjoke = _load("dadjoke")
DadJokeConfig = _dadjoke.DadJokeConfig
NameChange = _dadjoke.NameChange

_everbridge = _load("everbridge")
EverbridgeConfig = _everbridge.EverbridgeConfig

_facts = _load("facts")
Fact = _facts.Fact

_fishbowl = _load("fishbowl")
FishbowlConfig = _fishbowl.FishbowlConfig

_barhopper = _load("barhopper")
Bar = _barhopper.Bar

_reacttrack = _load("reacttrack")
ReactEvent = _reacttrack.ReactEvent

_youtube = _load("youtube")
YoutubeSubscription = _youtube.YoutubeSubscription

_verification = _load("verification")
VerificationConfig = _verification.VerificationConfig
VerificationRequest = _verification.VerificationRequest

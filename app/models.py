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
    """Import a cog's model module by file path, bypassing its __init__.py."""
    path = os.path.join(_COGS_DIR, cog, filename)
    module_name = f"_lanco_models_{cog}_{filename[:-3]}"
    if module_name in sys.modules:
        return sys.modules[module_name]
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

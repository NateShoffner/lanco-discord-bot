import collections
import os
import re
import sys
import time
from functools import wraps
from urllib.parse import urlencode

import requests
from flask import Flask, redirect, render_template, request, session, url_for
from peewee import MySQLDatabase, SqliteDatabase

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from cogs.metrics.models import BotGuild, BotMetrics
from db import database_proxy
from utils.config import GuildConfig

app = Flask(__name__)
app.secret_key = os.environ.get("DASHBOARD_SECRET_KEY", "change-me")

DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.environ.get(
    "DISCORD_REDIRECT_URI", "http://localhost:5000/callback"
)

DISCORD_API = "https://discord.com/api/v10"
OAUTH2_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
OAUTH2_TOKEN_URL = "https://discord.com/api/oauth2/token"

MANAGE_GUILD = 0x20


def _init_db():
    db_type = os.environ.get("DB_TYPE", "sqlite").lower()
    if db_type == "mysql":
        db = MySQLDatabase(
            os.environ.get("MYSQL_DB"),
            host=os.environ.get("MYSQL_HOST", "localhost"),
            port=int(os.environ.get("MYSQL_PORT", 3306)),
            user=os.environ.get("MYSQL_USER"),
            password=os.environ.get("MYSQL_PASSWORD"),
        )
    else:
        db = SqliteDatabase(
            os.environ.get("SQLITE_DB", "../data/lancobot.db"),
            pragmas={"journal_mode": "wal"},
        )
    database_proxy.initialize(db)
    db.connect(reuse_if_open=True)
    db.create_tables([GuildConfig, BotMetrics, BotGuild], safe=True)


_init_db()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "access_token" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


def _discord_get(endpoint, token):
    resp = requests.get(
        f"{DISCORD_API}{endpoint}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _manageable_guilds(token):
    cached = session.get("guilds_cache")
    if cached and time.time() - cached["ts"] < 300:
        return cached["guilds"]

    guilds = _discord_get("/users/@me/guilds", token)

    # Only guilds where the user has MANAGE_GUILD AND the bot is present
    bot_guild_ids = {row.guild_id for row in BotGuild.select(BotGuild.guild_id)}
    manageable = [
        g
        for g in guilds
        if (int(g["permissions"]) & MANAGE_GUILD) == MANAGE_GUILD
        and int(g["id"]) in bot_guild_ids
    ]

    session["guilds_cache"] = {"guilds": manageable, "ts": time.time()}
    return manageable


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------


@app.route("/login")
def login():
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds",
    }
    return redirect(f"{OAUTH2_AUTHORIZE_URL}?{urlencode(params)}")


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Missing OAuth2 code", 400

    resp = requests.post(
        OAUTH2_TOKEN_URL,
        data={
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": DISCORD_REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    resp.raise_for_status()
    token_data = resp.json()
    access_token = token_data["access_token"]

    user = _discord_get("/users/@me", access_token)
    session["access_token"] = access_token
    session["user"] = {
        "id": user["id"],
        "username": user["username"],
        "avatar": user.get("avatar"),
    }
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Dashboard routes
# ---------------------------------------------------------------------------


@app.route("/")
@login_required
def index():
    guilds = _manageable_guilds(session["access_token"])
    return render_template("index.html", guilds=guilds, user=session.get("user"))


@app.route("/guild/<int:guild_id>", methods=["GET", "POST"])
@login_required
def guild_dashboard(guild_id):
    guilds = _manageable_guilds(session["access_token"])
    if not any(int(g["id"]) == guild_id for g in guilds):
        return "Forbidden", 403

    guild = next(g for g in guilds if int(g["id"]) == guild_id)
    config, _ = GuildConfig.get_or_create(guild_id=guild_id)

    if request.method == "POST":
        prefix = (request.form.get("prefix", ".").strip() or ".")[:10]
        timezone = request.form.get("timezone", "UTC").strip() or "UTC"
        config.prefix = prefix
        config.timezone = timezone
        config.save()
        return redirect(url_for("guild_dashboard", guild_id=guild_id, saved=1))

    saved = request.args.get("saved") == "1"
    return render_template(
        "dashboard.html",
        guild=guild,
        config=config,
        saved=saved,
        user=session.get("user"),
    )


# ---------------------------------------------------------------------------
# Status routes
# ---------------------------------------------------------------------------


def _latest_metrics():
    return BotMetrics.select().order_by(BotMetrics.id.desc()).first()


def _format_uptime(seconds):
    if seconds is None:
        return "N/A"
    seconds = int(seconds)
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


@app.route("/status")
@login_required
def status():
    metrics = _latest_metrics()
    return render_template(
        "status.html",
        user=session.get("user"),
        metrics=metrics,
        uptime=_format_uptime(metrics.uptime_seconds if metrics else None),
    )


@app.route("/status/partial")
@login_required
def status_partial():
    """HTMX endpoint — returns just the metrics cards fragment."""
    metrics = _latest_metrics()
    return render_template(
        "partials/metrics_cards.html",
        metrics=metrics,
        uptime=_format_uptime(metrics.uptime_seconds if metrics else None),
    )


# ---------------------------------------------------------------------------
# Logs routes
# ---------------------------------------------------------------------------

LOG_FILE = os.environ.get(
    "LOG_FILE", os.path.join(os.path.dirname(__file__), "..", "logs", "logfile.log")
)
LOG_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+)\s+"
    r"(?P<logger>\S+)\s+"
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+"
    r"(?P<message>.*)$"
)
VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
DEFAULT_LINES = 200


def _read_log_lines(n=DEFAULT_LINES):
    """Return the last n lines from the log file cheaply."""
    path = os.path.abspath(LOG_FILE)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return list(collections.deque(f, maxlen=n))


def _parse_log_lines(raw_lines, level_filter=None):
    parsed = []
    for line in raw_lines:
        line = line.rstrip("\n")
        m = LOG_LINE_RE.match(line)
        if m:
            entry = m.groupdict()
        else:
            # continuation line — attach to last entry or show as-is
            if parsed:
                parsed[-1]["message"] += " " + line
            continue

        if level_filter and level_filter != "ALL" and entry["level"] != level_filter:
            continue
        parsed.append(entry)

    parsed.reverse()
    return parsed


@app.route("/logs")
@login_required
def logs():
    level = request.args.get("level", "ALL").upper()
    if level not in VALID_LEVELS and level != "ALL":
        level = "ALL"
    raw = _read_log_lines()
    entries = _parse_log_lines(raw, level)
    return render_template(
        "logs.html", user=session.get("user"), entries=entries, level=level
    )


@app.route("/logs/partial")
@login_required
def logs_partial():
    """HTMX endpoint — returns just the log rows fragment."""
    level = request.args.get("level", "ALL").upper()
    if level not in VALID_LEVELS and level != "ALL":
        level = "ALL"
    raw = _read_log_lines()
    entries = _parse_log_lines(raw, level)
    return render_template("partials/log_rows.html", entries=entries, level=level)


if __name__ == "__main__":
    app.run(debug=True, port=5000)

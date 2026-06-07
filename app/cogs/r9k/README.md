# R9K

Designates a channel as an **R9K mode** channel where every message must be
unique. Duplicate messages (anything already said in that channel) are
deleted, in the spirit of [Randall Munroe's Robot9000](https://en.wikipedia.org/wiki/Randall_Munroe#Other_projects)
and 4chan's [/r9k/](https://en.wikipedia.org/wiki/4chan#/r9k/).

## How it works

- Matching is **per-channel**: a phrase is a duplicate only if it was
  previously said in that same channel.
- Content is **normalized before hashing** (lowercased, trimmed, and internal
  whitespace collapsed), so `Hello`, `hello`, and `hello   ` all collide.
- The first time a phrase is seen it is recorded; any later repeat is deleted
  and the author is DMed an explanation.
- Optionally, a repeat offender can also be **timed out** for a configurable
  duration (see `/r9k timeout`). Off by default.
- Optionally, recorded phrases can **expire** after a configurable lifetime
  (see `/r9k ttl`), after which they may be reused. Off by default (phrases are
  remembered forever). Expired records are purged lazily as new messages arrive.
- Attachment-only / empty messages are ignored.
- Bot commands are ignored: slash commands never reach the handler, and prefix
  commands (this bot's prefix, or other bots' like `!` / `T!`) are skipped so
  running the same command twice isn't punished.

## Commands

| Command | Description |
| --- | --- |
| `/r9k set <channel>` | Designate the R9K channel and enable enforcement. |
| `/r9k enable` | Re-enable enforcement on the configured channel. |
| `/r9k disable` | Pause enforcement without losing recorded history. |
| `/r9k timeout <seconds>` | Time out a user for this many seconds on a duplicate. `0` disables (delete only). Max 28 days. |
| `/r9k ttl <seconds>` | Expire recorded phrases after this many seconds so they can be reused. `0` means never expire. |
| `/r9k reset` | Clear the recorded message history for the channel. |

All commands require bot owner or server admin.

## Permissions

The bot needs **Manage Messages** in the R9K channel to delete duplicates, and
**Moderate Members** (Timeout Members) if a timeout duration is configured.

## Future work (see issue #83)

- "Hardcore" semantic mode using embeddings instead of hashing.

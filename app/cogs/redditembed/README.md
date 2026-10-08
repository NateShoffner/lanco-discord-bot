# Reddit Embed Fixer

Fixes Reddit embeds by rewriting links to a third-party fixer service that enables media playback in Discord.

## Commands

| Command | Permission | Description |
|---|---|---|
| `/redditembed toggle` | Admin | Enable or disable the embed fix for this guild |
| `/redditembed handler` | Admin | Switch the fixer service for this guild |

## Handlers

| ID | Name | Replacement |
|---|---|---|
| `vxreddit` *(default)* | VxReddit | `vxreddit.com` |
| `redditez` | RedditEZ | `redditez.com` (EmbedEZ) |

`rxddit.com` was the default until Reddit began blocking it; every request now
returns an error card instead of a preview. Guilds still holding that handler id
fall back to the default.

## Behavior

- Matches all `reddit.com` URLs.
- Disabled by default; enable per guild with `/redditembed toggle`.
- URLs wrapped in `<angle brackets>` or `||spoilers||` are ignored.

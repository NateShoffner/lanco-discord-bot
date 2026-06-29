# Reddit Embed Fixer

Fixes Reddit embeds by rewriting links to a third-party fixer service that enables media playback in Discord.

## Commands

| Command | Permission | Description |
|---|---|---|
| `/redditembed toggle` | Admin | Enable or disable the embed fix for this guild |
| `/redditembed handler` | Admin | View the active fixer service |

## Handlers

| ID | Name | Replacement |
|---|---|---|
| `rxddit` *(default)* | Rxddit | `rxddit.com` |

## Behavior

- Matches all `reddit.com` URLs.
- Disabled by default; enable per guild with `/redditembed toggle`.
- URLs wrapped in `<angle brackets>` or `||spoilers||` are ignored.

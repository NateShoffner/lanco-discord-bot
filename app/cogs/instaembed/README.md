# InstaEmbed

Fixes Instagram embeds by rewriting links to a third-party fixer service that enables media playback in Discord.

## Commands

| Command | Permission | Description |
|---|---|---|
| `/instaembed toggle` | Admin | Enable or disable the embed fix for this guild |
| `/instaembed handler` | Admin | Switch the fixer service via dropdown |

## Handlers

| ID | Name | Replacement |
|---|---|---|
| `zzinstagram` *(default)* | ZZInstagram | `zzinstagram.com` |
| `ddinstagram` | DDInstagram | `ddinstagram.com` |

Run `/instaembed handler` to get a dropdown of available handlers. The selection is saved per guild and takes effect immediately for new links.

## Behavior

- Matches `instagram.com/p/…`, `/reel/…`, and `/reels/…` URLs.
- Disabled by default; enable per guild with `/instaembed toggle`.
- URLs wrapped in `<angle brackets>` or `||spoilers||` are ignored.

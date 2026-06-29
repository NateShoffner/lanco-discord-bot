# TikTok Embed Fixer

Fixes TikTok embeds by rewriting links to a third-party fixer service that enables media playback in Discord.

## Commands

| Command | Permission | Description |
|---|---|---|
| `/tiktokembed toggle` | Admin | Enable or disable the embed fix for this guild |
| `/tiktokembed handler` | Admin | Switch the fixer service via dropdown |

## Handlers

| ID | Name | Replacement |
|---|---|---|
| `vxtiktok` *(default)* | VxTikTok | `vxtiktok.com` |
| `tnktok` | TnkTok | `tnktok.com` |

Run `/tiktokembed handler` to get a dropdown of available handlers. The selection is saved per guild and takes effect immediately for new links.

## Behavior

- Shop and product URLs (`/shop/…`, `/product/…`) are excluded.
- Disabled by default; enable per guild with `/tiktokembed toggle`.
- URLs wrapped in `<angle brackets>` or `||spoilers||` are ignored.

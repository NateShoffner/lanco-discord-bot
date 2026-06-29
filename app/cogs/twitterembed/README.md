# Twitter/X Embed Fixer

Fixes Twitter/X embeds by rewriting links to a third-party fixer service that enables media playback in Discord.

## Commands

| Command | Permission | Description |
|---|---|---|
| `/twitterembed toggle` | Admin | Enable or disable the embed fix for this guild |
| `/twitterembed handler` | Admin | Switch the fixer service via dropdown |

## Handlers

| ID | Name | Replacement |
|---|---|---|
| `fxtwitter` *(default)* | FxTwitter | `fxtwitter.com` |
| `vxtwitter` | VxTwitter | `vxtwitter.com` / `fixvx.com` for x.com links |
| `fixupx` | FixupX | `fixupx.com` |

Run `/twitterembed handler` to get a dropdown of available handlers. The selection is saved per guild.

## Behavior

- Handles both `twitter.com` and `x.com` status URLs.
- Disabled by default; enable per guild with `/twitterembed toggle`.
- URLs wrapped in `<angle brackets>` or `||spoilers||` are ignored.

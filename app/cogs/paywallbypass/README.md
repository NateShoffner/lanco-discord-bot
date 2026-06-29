# Paywall Bypass

When a paywalled link is detected, the bot replies with a button that opens the article through a configured third-party bypass service. The original Discord embed is preserved.

## Commands

| Command | Permission | Description |
|---|---|---|
| `/paywallbypass toggle` | Admin | Enable or disable paywall bypass for this guild |
| `/paywallbypass service` | Admin | Switch the active bypass service for this guild |

## Services

| ID | Name | Via |
|---|---|---|
| `removepaywall` *(default)* | Remove Paywall | `removepaywall.com` |
| `archiveph` | Archive.ph | `archive.ph` |
| `wayback` | Wayback Machine | `web.archive.org` |

## Behavior

- Matches all `lancasteronline.com` URLs.
- Disabled by default; enable per guild with `/paywallbypass toggle`.
- Replies with a "Read via \<Service\>" link button and a short disclosure that the bot does not host or cache any content.
- URLs wrapped in `<angle brackets>` or `||spoilers||` are ignored.

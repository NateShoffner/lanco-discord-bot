# Facebook Embed Fixer

Replaces broken Facebook embeds with rich previews. URLs are routed by type: reels and videos are rewritten to the [facebed](https://github.com/facebed/facebed) service for playable media, while posts, events, and pages are embedded natively from Facebook's OpenGraph data.

## Commands

| Command | Permission | Description |
|---|---|---|
| `/facebookembed toggle` | Admin | Enable or disable the embed fix for this guild |

## Behavior

| URL type | Handling |
|---|---|
| Reels, videos, `fb.watch` | Rewritten to `facebed.seria.moe` (playable media) |
| Posts (`/<page>/posts/...`) | Native multi-image gallery embed |
| Events (`/events/...`) | Native embed with title, image, and details |
| Pages (`/<page>`) | Native embed with name, bio, and profile image |
| Stories (`/stories/...`) | Skipped (cannot be embedded) |

- Disabled by default; enable per guild with `/facebookembed toggle`.
- URLs wrapped in `<angle brackets>` or `||spoilers||` are ignored.

## Notes

- Reels and videos can't be embedded natively. The media lives on signed, short-lived `fbcdn.net` URLs that only a scraping service like facebed can resolve.
- Stories are login-walled to everyone unauthenticated, so no service or API can embed them; they are left untouched rather than posting a useless "Log in to view" card.
- Posts and pages are scraped from Facebook's OpenGraph tags, which Facebook serves inconsistently. Fetches retry across user-agents, and posts fall back to the facebed link if no data is returned.

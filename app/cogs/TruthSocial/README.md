# TruthSocial Cog

TruthSocial embed support. When a truthsocial.com post or profile URL is posted
in a server with embeds enabled, the bot replaces it with a richer embed
carrying the author, content, engagement counts, avatar, and any media.

## Setup

```
/truthsocial toggle
```

Admins and bot owners only. Enables or disables embeds for the server.

## Credentials

The TruthSocial API is login-walled, so the cog needs an account. Set either:

- `TRUTH_SOCIAL_TOKEN` — an existing auth token, or
- `TRUTH_SOCIAL_USERNAME` and `TRUTH_SOCIAL_PASSWORD`

With neither set, the cog logs a warning at load and stays quiet. It still
loads and `/truthsocial toggle` still works, but no URL is ever rewritten.

## Notes

- truthbrush is a synchronous HTTP client, so its calls run on a worker thread
  to keep them off the event loop.
- API failures (auth trouble, rate limits, a deleted post) are logged and the
  message is left alone, so Discord's own unfurl is what remains.
- Avatars and media are cached under the cog's data directory and downloaded
  once. A download that fails drops that attachment rather than the embed.

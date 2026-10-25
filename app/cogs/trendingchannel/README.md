# TrendingChannel

Posts a running summary of what a channel is talking about. Every minute the cog checks each enabled channel; when enough new messages have arrived it reads the recent history, asks the model what the channel is about right now, and posts a short summary in the channel.

As an optional extra, turned on per channel with `/trending rename`, it also renames the channel and updates its topic to match the discussion. The summary is still posted first; if the rename cannot happen (the bot lacks Manage Channels, Discord's edit bucket is exhausted, or the edit is rejected) the summary stands on its own.

## Commands

| Command | Description | Permissions |
|---|---|---|
| `/trending toggle` | Enable or disable conversation summaries for the current channel | Admin only |
| `/trending rename` | Also rename the current channel and update its topic to match the discussion | Admin only |
| `/trending status` | List the channels with summaries enabled, when each was last analyzed, and whether renaming is on | Admin only |
| `/trending refresh` | Analyze the current channel now instead of waiting for new messages | Admin only |

## Behaviour

- Enabled channels are stored in `trending_channel_config` and survive restarts. Deleting a channel removes its row.
- A channel is analyzed at most once every 5 minutes, which keeps summaries from piling up. Discord allows two name or topic edits per channel per ten minutes, so the same floor keeps the optional rename inside that limit.
- Between analyses at least 5 new user messages must arrive. An idle channel costs no API call and no model call, and a channel the bot can neither post in nor edit is not analyzed at all.
- The bot's own summary does not count as new activity.
- Suggested names are sanitized to Discord's rules (lowercase, hyphens, 100 characters) and an unchanged name or topic is not re-sent. An edit that stalls on a rate limit is abandoned after 15 seconds rather than holding up the other channels.
- One unavailable channel does not stop updates for the others.

## Configuration

Requires `OPENAI_API_KEY`; the cog does not load without it. The bot needs Send Messages in the channel to post summaries, and Manage Channels as well if renaming is turned on.

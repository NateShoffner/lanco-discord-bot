# TrendingChannel

Renames a channel and updates its topic to follow the conversation. Every minute the cog checks each enabled channel; when enough new messages have arrived it reads the recent history, asks the model what the channel is about right now, and edits the channel name and topic to match.

When the channel cannot be edited (the bot lacks Manage Channels, Discord's edit bucket is exhausted, or the edit is rejected) the cog posts the model's summary as a message in the channel instead.

## Commands

| Command | Description | Permissions |
|---|---|---|
| `/trending toggle` | Enable or disable trending updates for the current channel | Admin only |
| `/trending status` | List the channels with trending updates enabled and when each was last updated | Admin only |
| `/trending refresh` | Analyze the current channel now instead of waiting for new messages | Admin only |

## Behaviour

- Enabled channels are stored in `trending_channel_config` and survive restarts. Deleting a channel removes its row.
- A channel is analyzed at most once every 5 minutes. Discord allows two name or topic edits per channel per ten minutes, so this keeps the cog inside that limit on its own.
- Between analyses at least 5 new user messages must arrive. An idle channel costs no API call and no model call.
- Suggested names are sanitized to Discord's rules (lowercase, hyphens, 100 characters) and an unchanged name or topic is not re-sent.
- One unavailable channel does not stop updates for the others.

## Configuration

Requires `OPENAI_API_KEY`; the cog does not load without it. The bot needs Manage Channels in the channel to edit it, or Send Messages to post the fallback summary.

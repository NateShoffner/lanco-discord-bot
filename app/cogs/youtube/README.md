# YouTube

Polls YouTube channels for new videos and posts them to subscribed Discord channels.

## Commands

| Command | Description | Permissions |
|---|---|---|
| `/youtube subscribe <channel_id>` | Subscribe to a YouTube channel | Admin only |
| `/youtube unsubscribe <channel_id>` | Unsubscribe from a YouTube channel | Admin only |

## Configuration

Requires `YOUTUBE_API_KEY`.

## Database

| Table | Purpose |
|---|---|
| `youtube_subscriptions` | Per-guild YouTube channel subscriptions |

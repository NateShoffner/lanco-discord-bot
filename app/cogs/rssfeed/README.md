# RSSFeed

Polls RSS feeds for new items and posts them to subscribed channels.

## Commands

| Command | Description |
|---|---|
| `/rssfeed subscribe <url>` | Subscribe a channel to an RSS feed |
| `/rssfeed unsubscribe <url>` | Unsubscribe from an RSS feed |

## Database

| Table | Purpose |
|---|---|
| `rss_feed_configs` | Per-channel RSS subscriptions |

# ReactTrack

Tracks emoji reactions across the server for analytics.

## Commands

| Command | Description |
|---|---|
| `/reacttrack today <user>` | Show a user's reactions in the last 24 hours |

## Database

| Table | Purpose |
|---|---|
| `react_events` | Logs reaction add/remove events with emoji, user, channel, and timestamp |

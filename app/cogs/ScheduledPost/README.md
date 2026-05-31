# ScheduledPost

Allows admins and bot owners to schedule one-time or recurring posts in any channel, with optional embeds and role pings.

## Commands

All commands require **admin** or **bot owner** permissions.

### `/scheduledpost add`

Schedule a new post.

| Option | Required | Description |
|---|---|---|
| `channel` | ✅ | Channel to post in |
| `schedule` | ✅ | Cron expression or natural language (see below) |
| `message` | — | Text content of the post |
| `recurring` | — | Whether to repeat on the schedule (default: true) |
| `embed_title` | — | Embed title |
| `embed_description` | — | Embed description |
| `embed_color` | — | Embed color as hex (e.g. `ff0000`) |
| `role_ping` | — | Role to ping when posting |

At least one of `message`, `embed_title`, or `embed_description` is required.

### `/scheduledpost list`

List all active scheduled posts in the server, including their ID, channel, next run time, and a preview.

### `/scheduledpost delete <post_id>`

Permanently delete a scheduled post. Use the 8-character ID shown in `/scheduledpost list`.

### `/scheduledpost pause <post_id>`

Pause a scheduled post without deleting it.

### `/scheduledpost resume <post_id>`

Resume a previously paused post.

---

## Schedule Format

Accepts either a **cron expression** or **natural language**:

**Cron expressions:**
```
0 9 * * 1        → Every Monday at 9:00am
30 17 * * 1-5    → Weekdays at 5:30pm
0 12 1 * *       → 1st of every month at noon
```

**Natural language:**
```
every Monday at 9am
tomorrow at 3pm
every Friday at 5:30pm
```

For recurring posts using natural language, the recurrence defaults to weekly on the same day/time.
For one-time posts, the exact date and time is used.

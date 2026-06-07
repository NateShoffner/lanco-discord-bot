# Facts

Store and retrieve server-specific facts.

## Commands

| Command | Description | Permissions |
|---|---|---|
| `/fact add [fact_id]` | Add or edit a fact (omit ID to create new) | Admin only |
| `!fact` | Get a random fact from this server | — |

## Database

| Table | Purpose |
|---|---|
| `facts` | Stores fact text, author, guild, and last modified timestamp |

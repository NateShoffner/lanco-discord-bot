# System

System and admin commands for monitoring bot status, usage, and database info.

## Commands

| Command | Description | Permissions |
|---|---|---|
| `/ping` | Ping the bot | — |
| `/info` | Show bot info and version | — |
| `/contribute` | Learn how to contribute to LancoBot | — |
| `/diag` | Show bot diagnostics | Owner only |
| `/dbinfo` | Show database info | Owner only |
| `/block <user> <reason>` | Block a user from using the bot | Owner only |
| `/unblock <user>` | Unblock a blocked user | Owner only |
| `/token-usage [days]` | Show OpenAI token usage | Owner only |
| `/token-water [days]` | Estimate water consumed by OpenAI token usage | Owner only |

`/token-usage` and `/token-water` need `OPENAI_ADMIN_KEY`, and optionally
`OPENAI_PROJECT_ID` to scope usage to this project rather than the whole account.

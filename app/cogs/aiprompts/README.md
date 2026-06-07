# AI Prompts

Manage custom AI prompts that server members can trigger via prefix commands. Each prompt is stored per-guild and executed against OpenAI.

## Commands

| Command | Description | Permissions |
|---|---|---|
| `/aiprompt add` | Add a new AI prompt | Admin only |
| `/aiprompt edit <name>` | Edit an existing prompt | Admin only |
| `/aiprompt remove <name>` | Remove a prompt | Admin only |
| `/aiprompt list` | List all prompts for this server | — |
| `!<prompt_name> <text>` | Execute a custom prompt | — |

## Configuration

Requires `OPENAI_API_KEY`.

## Database

| Table | Purpose |
|---|---|
| `ai_prompt_configs` | Stores prompt name, text, and guild association |

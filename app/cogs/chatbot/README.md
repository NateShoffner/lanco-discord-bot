# Chatbot

A conversational AI cog powered by OpenAI via pydantic-ai. The bot responds when @mentioned or when a user replies directly to one of its messages.

## Features

- **Channel context awareness** — fetches the last 20 messages before each interaction so the bot can weigh in on ongoing conversations without being explicitly caught up
- **Multi-turn history** — accumulates a rolling window of conversation history (~20 turns) per channel so the bot remembers earlier exchanges
- **Sender context** — each message includes the sender's display name, username, user ID, roles, account age, and server join date so the bot can answer identity questions accurately
- **Attachment support** — images are passed directly to the model for vision analysis; text files (plain text, JSON, XML, YAML) are read and included as content
- **Attachment caching** — images and text files are processed once per channel session; subsequent references reuse the cached result rather than re-fetching

## Triggers

| Trigger | Behavior |
|---|---|
| `@mention` | Bot responds; mention is stripped from the message content |
| Reply to a bot message | Bot responds in the same thread of conversation |
| Reply to a bot embed | Ignored |

## Attachment Limits

| Type | Max size |
|---|---|
| Images (`image/*`) | 4 MB |
| Text files (`text/*`, JSON, XML, YAML) | 32 KB |

Unsupported or oversized attachments are noted in the message to the model so it can acknowledge them.

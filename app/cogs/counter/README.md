# Counter

A counting channel where users must count up from 1 together. Mess up the count and it resets for everyone.

## Setup

Admins and bot owners only:

```
/counter #channel
```

Designates a channel as the counting channel. Resets the count to 0.

## Rules

- Send the next number in sequence (1, 2, 3, ...)
- You **cannot** count twice in a row — let someone else go next
- Sending the wrong number resets the count back to 1
- The bot tracks the all-time high score for the server

## Behavior

- ✅ reaction = correct number
- ❌ reaction + reset message = wrong number
- Wrong-turn messages (same user twice) are deleted and the user gets a DM

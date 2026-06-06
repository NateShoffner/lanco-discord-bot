# GeoGuesser

A Lancaster-themed GeoGuesser game playable in Discord. Each round shows a Google Street View image and players guess the location by typing it in chat. Closer guesses earn more points.

## Commands

| Command | Description |
|---|---|
| `/geoguesser start` | Start a new session. Prompts for mode selection. |
| `/geoguesser stop` | Stop the current session (host only). |
| `/geoguesser skip` | Skip the current round (host only). |
| `/geoguesser populate` | Populate the database with locations (bot owner only). |

## Modes

- **Lancaster City** — guesses are snapped to Lancaster City, PA
- **Lancaster County** — guesses are snapped to Lancaster County, PA

## Gameplay

1. Host starts a session and selects a mode
2. Each round posts a Street View image with a countdown
3. Players type their guess in chat — one guess per round
4. After time expires, results are posted showing top guessers, standings, and a Google Maps link to the actual location
5. After all rounds, final standings are shown

## Configuration

| Constant | Default | Description |
|---|---|---|
| `GUESS_TIME` | 20s | Time allowed per round |
| `WARNING_TIME` | 10s | When the half-time warning fires |
| `TIME_BETWEEN_ROUNDS` | 10s | Delay between rounds |
| Default rounds | 10 | Locations loaded per session |

## Scoring

Score per round is `max(0, 1 - distance / 0.02) * 100`, giving a max of 100 points. Distance is computed via the Google Maps Distance Matrix API.

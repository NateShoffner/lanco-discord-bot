# GeoGuesser

A Lancaster-themed GeoGuesser game playable in Discord. Each round shows a Google Street View image and players guess the location by typing in chat. Closer guesses earn more points.

## Commands

| Command | Description |
|---|---|
| `/geoguesser start` | Start a new session. Prompts for mode selection. |
| `/geoguesser stop` | Stop the current session (host only). |
| `/geoguesser skip` | Skip the current round (host only). |
| `/geoguesser leaderboard [period]` | Show the guild leaderboard. Period: `all` (default), `today`, `week`. |
| `/geoguesser stats` | Show location counts and games recorded (bot owner only). |
| `/geoguesser populate` | Populate the database with locations (bot owner only). |
| `/geoguesser wipe` | Wipe all locations for a mode (bot owner only). |
| `/geoguesser clearsessions` | Clear all active and starting sessions (bot owner only). |

## Modes

- **Lancaster City** — guesses are snapped to Lancaster City, PA
- **Lancaster County** — guesses are snapped to Lancaster County, PA

## Game Flow

```mermaid
flowchart TD
    A([geoguesser start]) --> B[Mode select dropdown]
    B --> C["initialize_session
    Load 10 locations
    Cache street view images"]
    C --> D["Post round embed
    Street view image
    Guessing countdown"]
    D --> E{Players guess in chat}
    E -->|Valid guess| F["React ✅
    Record score"]
    E -->|Already guessed| G[Ignore]
    E -->|Invalid| H[Ignore]
    F --> E
    D --> I{GUESS_TIME elapses or skip}

    I -->|Skip| J[geoguesser skip]
    J --> K["Cancel round task
    Cancel warning task
    Freeze round embed"]
    K --> L{More rounds?}

    I -->|Time up| M["post_round_results
    Freeze round embed
    Post answer map
    Closest / Furthest
    Standings"]
    M --> L

    L -->|Yes| N["Wait TIME_BETWEEN_ROUNDS
    Post next round embed"]
    N --> D
    L -->|No| O["post_final_results
    Post final standings
    Record scores to DB"]
    O --> P([Game over])

    A2([geoguesser stop]) --> Q["Cancel session
    Freeze round embed
    Cleanup warning message"]
    Q --> P
```

## Scoring

Score per round: `max(0, 1 - distance_meters / 1000) * 100`

- 100 points at 0m
- 0 points at 1km or more
- Distance is straight-line (haversine), not driving distance

Per-player scores accumulate across all rounds. At game end, if 2+ players participated, scores are recorded to the `geoguesser_game_results` table for persistent leaderboards.

## Configuration

| Constant | Default | Description |
|---|---|---|
| `GUESS_TIME` | 20s | Time allowed per round |
| `WARNING_TIME` | 10s | When the half-time warning fires |
| `TIME_BETWEEN_ROUNDS` | 10s | Delay between rounds |
| Default rounds | 10 | Locations loaded per session |

## Database

| Table | Purpose |
|---|---|
| `geoguesser_locations` | Pre-populated Street View locations with coordinates and reverse-geocoded labels |
| `geoguesser_game_results` | Per-player per-game scores for persistent leaderboards |

## Development Notes

- Locations must be pre-populated via `/geoguesser populate` before games can start
- Street view images are cached to disk under `data/GeoGuesser/streetview_cache/`
- Session state (`_active_sessions`, `_sessions_starting`) is stored at module level and survives hot-reloads but not full bot restarts
- All Google Maps API calls (geocoding, snap-to-roads, street view) are run via `asyncio.to_thread` to avoid blocking the event loop

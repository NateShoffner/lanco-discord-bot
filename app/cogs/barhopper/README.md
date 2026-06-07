# BarHopper

Search and discover bars using Google Maps. Supports browsing by name or getting random suggestions, with cached map images and ratings.

## Commands

| Command | Description | Permissions |
|---|---|---|
| `/barhopper populate` | Populate the database with bars from Google Maps | Owner only |
| `/barhopper search <term>` | Search bars by name | — |
| `/barhopper random [count]` | Get random bar suggestions (max 5) | — |

## Configuration

Requires `GMAPS_API_KEY`.

## Database

| Table | Purpose |
|---|---|
| `bars` | Bar details including name, address, coordinates, rating, price level, and place ID |

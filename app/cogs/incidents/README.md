# Incidents

Monitors and announces active Lancaster County emergency incidents sourced from [LCWC](https://github.com/NateShoffner/python-lcwc) (Lancaster County-Wide Communications).

## Features

- Polls for active incidents every 5 seconds and posts new ones as embeds to a configured channel
- Embeds include incident category (fire/medical/traffic), location, description, assigned units, and a Google Maps static map image
- ArcGIS mode also includes agency name, incident number, and priority
- Map images are cached locally to avoid redundant API calls
- Supports three data sources (configurable via `/incidents setclient`):
  - **ArcGIS** (default) — real-time data with incident numbers, coordinates, and priority
  - **RSS Feed** — LCWC RSS feed, deduped by timestamp
  - **Web** — scraped from the LCWC website, deduped by timestamp

## Commands

| Command | Permission | Description |
|---|---|---|
| `/incidents enable` | Admin | Enable the feed in the current channel |
| `/incidents disable` | Admin | Disable the feed for this guild |
| `/incidents status` | Everyone | Show sync status, active incident count, client, and package version |
| `/incidents view <number>` | Everyone | View embed for a currently active incident by number (ArcGIS only) |
| `/incidents setclient` | Bot owner | Switch the data source client |

## Configuration

Requires a `GMAPS_API_KEY` environment variable for geocoding and static map generation. Non-ArcGIS clients use Google Maps geocoding to resolve intersection-based addresses to coordinates.

## Notes

- Feed state (last known incident number or timestamp) is persisted per channel so restarts don't re-announce old incidents.
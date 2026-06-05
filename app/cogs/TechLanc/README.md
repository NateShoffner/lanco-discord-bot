# TechLanc Cog

Posts upcoming Tech Lancaster meetups and monthly meetup details sourced from the Tech Lancaster Google Calendar and Meetup.com RSS feed.

## Commands

### Prefix commands

| Command | Description |
|---|---|
| `!tl` | Post this week's upcoming meetups in the current channel |
| `!tlm` | Post the next Tech Lancaster Meetup details including speakers |

`!tlm` is restricted to admins, bot owners, and any users/roles added via `/techlanc addposter`.

### Slash commands

#### Weekly schedule
| Command | Description |
|---|---|
| `/techlanc setchannel #channel day hour minute` | Enable automatic weekly posts in a channel at the specified day/time (UTC). Re-running updates the schedule. |
| `/techlanc unsetchannel #channel` | Disable weekly posts in a channel |
| `/techlanc list` | List all configured channels and their schedules |
| `/techlanc post` | Manually post this week's meetups in the current channel |

#### Monthly meetup (TLM) settings
| Command | Description |
|---|---|
| `/techlanc seteventurl <url>` | Set the Discord event URL to append to `!tlm` posts |
| `/techlanc cleareventurl` | Clear the Discord event URL |
| `/techlanc eventurl` | Show the currently configured Discord event URL |
| `/techlanc setpingrole @role` | Set the role to ping at the start of `!tlm` posts |
| `/techlanc clearpingrole` | Clear the ping role |
| `/techlanc setlocation <name> <url>` | Set the location name and URL for `!tlm` posts |
| `/techlanc resetlocation` | Reset location back to the default (West Art) |

#### Allowed posters
| Command | Description |
|---|---|
| `/techlanc addposter` | Allow a user and/or role to use `!tlm` |
| `/techlanc removeposter` | Remove a user and/or role from the allowed list |
| `/techlanc listposters` | List all allowed posters |

All slash commands require admin or bot owner permissions.

## Configuration

Set `GOOGLE_CAL_API_KEY` in your `.env` file. Without it the cog will load but calendar fetches will fail.

## Behavior

- **No announcements are made by default** — channels must be explicitly configured via `/techlanc setchannel`.
- Multiple channels per guild are supported for weekly schedule posts.
- Calendar results are cached for 1 hour to avoid redundant API calls.
- `!tlm` fetches the Meetup.com RSS feed for `tech-lancaster-meetups` and finds the next Tech Lancaster Meetup entry.
- The `!tlm` intro line uses relative language: **tonight**, **tomorrow**, or the full date (e.g. *Thursday, June 26th*) depending on when the command is run.
- The default location is [West Art](https://www.westartlanc.com/) with a Google Maps link. This can be changed per guild via `/techlanc setlocation`.

## Migrations

- `012_tech_lanc_config_schedule.py` — adds `day_of_week`, `post_hour`, and `post_minute` columns to the existing `tech_lanc_config` table.

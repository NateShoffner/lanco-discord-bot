# TechLanc Cog

Posts upcoming Tech Lancaster meetups, monthly meetup details, and Pub Standards announcements. Sourced from the Tech Lancaster Google Calendar and Meetup.com RSS feed.

## Commands

### Prefix commands

| Command | Description |
|---|---|
| `!tl` | Post this week's upcoming meetups in the current channel |
| `!tlm` | Post the next Tech Lancaster Meetup details including speakers |
| `!ps` | Post the next Pub Standards meetup announcement |

`!tlm` and `!ps` are restricted to admins, bot owners, and any users/roles added via `/techlanc addposter`.

### Slash commands

#### Weekly schedule
| Command | Description |
|---|---|
| `/techlanc setchannel #channel day hour minute` | Enable automatic weekly posts in a channel at the specified day/time (UTC). Re-running updates the schedule. |
| `/techlanc unsetchannel #channel` | Disable weekly posts in a channel |
| `/techlanc list` | List all configured channels and their schedules |
| `/techlanc post` | Manually post this week's meetups in the current channel |

#### Tech Lancaster Meetup (TLM) settings
| Command | Description |
|---|---|
| `/techlanc seteventurl <url>` | Set the Discord event URL to append to `!tlm` posts |
| `/techlanc cleareventurl` | Clear the Discord event URL |
| `/techlanc eventurl` | Show the currently configured Discord event URL |
| `/techlanc setpingrole @role` | Set the role to ping in `!tlm` and `!ps` posts |
| `/techlanc clearpingrole` | Clear the ping role |
| `/techlanc setlocation <name> <url>` | Set the TLM location name and URL |
| `/techlanc resetlocation` | Reset TLM location back to the default (West Art) |

#### Allowed posters
| Command | Description |
|---|---|
| `/techlanc addposter` | Allow a user and/or role to use `!tlm` and `!ps` |
| `/techlanc removeposter` | Remove a user and/or role from the allowed list |
| `/techlanc listposters` | List all allowed posters |

All slash commands require admin or bot owner permissions.

## Configuration

Set `GOOGLE_CAL_API_KEY` in your `.env` file. Without it the cog will load but calendar fetches will fail.

## Behavior

- **No announcements are made by default** — channels must be explicitly configured via `/techlanc setchannel`.
- Multiple channels per guild are supported for weekly schedule posts.
- Google Calendar results and the Meetup.com RSS feed are each cached for 1 hour.
- `!tlm` fetches the Meetup.com RSS feed and finds the next Tech Lancaster Meetup entry (4th Thursday of the month).
- `!ps` posts a static Pub Standards announcement for the next 2nd Thursday of the month.
- Both `!tlm` and `!ps` use relative date language: **tonight**, **tomorrow**, or the full date (e.g. *Thursday, June 26th*).
- The ping role configured via `/techlanc setpingrole` is shared between `!tlm` and `!ps`.
- Default TLM location is [West Art](https://www.westartlanc.com/), configurable per guild.
- Pub Standards location is hardcoded to Tellus and is not currently configurable.

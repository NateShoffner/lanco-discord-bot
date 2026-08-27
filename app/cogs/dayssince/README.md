# DaysSince

Generic "X days since &lt;thing&gt;" counters. An admin defines a tracker, gives it
the command name it should answer to, and anyone in the server can run that
command to see the current streak, the running total, and the record.

## Creating a tracker

Admins and bot owners only:

```
/dayssince create
```

Opens a modal with four fields:

| Field | Purpose | Example |
|---|---|---|
| Command Name | The prefix command that displays it | `coffeespill` |
| Title | Embed heading | `Office Coffee Machine` |
| Event | The thing being counted, as a noun phrase | `coffee spill` |
| Restrict to Channel | Optional; limits the command to one channel | `#general` |

The Event field is dropped into the sentence "**12 days** since the last
&lt;event&gt;", so phrase it to fit: `coffee spill`, not `the last coffee spill`.

## Viewing

Anyone can run the tracker's own command with the guild prefix:

```
!coffeespill
```

```
/dayssince list
```

Shows every tracker in the server with its current numbers.

## Managing

Admins and bot owners only. All of these autocomplete the tracker name.

```
/dayssince incident <name>
```

Records an occurrence: bumps the total, resets the streak to 0, and promotes
the streak to the record if it beat the old one. Announces publicly.

```
/dayssince set <name> [days] [total] [record]
```

Corrects any of the three numbers; at least one must be given. Setting `days`
backdates the last occurrence by that many days.

```
/dayssince edit <name>
/dayssince delete <name>
```

`edit` reopens the modal prefilled, including renaming the command. `delete`
removes the tracker and its history.

## Notes

- Trackers are per-guild, and command names are unique within a guild.
- The record shown includes a streak that is still running, so a tracker on day
  50 with an old record of 47 reports 50.
- Command names are matched against the guild prefix in `on_message`, the same
  way the Commands cog dispatches custom commands. A name that collides with a
  custom command will fire both.

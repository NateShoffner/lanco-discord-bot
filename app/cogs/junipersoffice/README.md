# JunipersOffice

Tracks the fish tank in Juniper's office, where the fish have a habit of not
surviving. Keeps a "days since the last fish death" counter, the total body
count, and the longest streak the tank has ever managed.

## Commands

```
/junicide status
```

Available to everyone. Shows the current streak, total deaths, the record, and
when the last death was.

```
/junicide death
```

Admins and bot owners only. Records a death: bumps the total, resets the streak
to 0, and promotes the streak to the record if it beat the old one.

```
/junicide set [days] [total] [record]
```

Admins and bot owners only. Corrects any of the three numbers. At least one
must be given; the rest are left alone. Setting `days` backdates the last death
to that many days ago.

## Notes

- State is per-guild.
- The record shown by `/junicide status` includes a streak that is still
  running, so a tank on day 50 with an old record of 47 reports 50.

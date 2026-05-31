# RemindMe

Reminds users of something after a specified duration.

## Commands

### `!remindme <duration> <message>`

Sets a reminder. The bot will ping you in the same channel when the time is up.

**Examples:**
```
!remindme 2h take out the trash
!remindme 30m check the oven
!remindme tomorrow call the dentist
!remindme 3 days renew parking permit
```

## Notes

- Reminders persist across bot restarts
- Duration is parsed using [dateparser](https://dateparser.readthedocs.io/), so natural language like `tomorrow` or `next Friday` works

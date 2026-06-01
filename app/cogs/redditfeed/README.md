# RedditFeed

Polls subreddits for new posts and shares them to configured Discord channels. Tracks edits and moderator removals and updates the original Discord message when they occur.

## Commands

All commands require **admin** or **bot owner** permissions.

### `/reddit subscribe <subreddit>`

Start watching a subreddit and posting new posts to the current channel.

```
/reddit subscribe lancaster
```

### `/reddit unsubscribe <subreddit>`

Stop watching a subreddit in the current channel.

## Behavior

- New posts are polled every **10 seconds**
- Post state (edited, removed) is checked every **2 minutes** for posts made within the last **30 minutes**
- NSFW posts have their images automatically blurred before being shared
- If a post is edited or removed by a moderator, the original Discord message is updated with a **Status** field

## Embed Fields

| Field | Description |
|---|---|
| Post Author | Reddit username with link |
| Content Warning | NSFW or None |
| Flair | Post flair with link to filtered subreddit view |
| Score | Current upvote score |
| Comments | Current comment count |
| Status | Only shown if edited or removed after posting |

## Notes

- **Author deletions** are detected via `reddit.info()` and reflected near-instantly
- **Moderator removals** are detected reliably and reflected within the state check interval
- **Edits** are best-effort — the Reddit API caches post data aggressively and edited state can take many minutes to propagate or may not propagate at all, particularly on low-traffic subreddits or new accounts. This is a known Reddit API limitation with no reliable workaround without streaming
- The bot uses ID-based deduplication so posts held in a moderation queue will still be shared when they become visible
- State changes are only tracked for posts within the last **30 minutes** of being created

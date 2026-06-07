# Verification

Vote-based user verification system with configurable role and approval threshold.

## Commands

| Command | Description | Permissions |
|---|---|---|
| `/verification verify <user>` | Request verification for a user | — |
| `/verification unverify <user>` | Remove a user's verification | Admin only |
| `/verification threshold <n>` | Set vote threshold required for verification | Admin only |
| `/verification role <role>` | Set the role granted on verification | Admin only |
| `/verification modchannel <channel>` | Set the mod notification channel | Admin only |

## Database

| Table | Purpose |
|---|---|
| `verification_configs` | Per-guild settings (role, threshold, mod channel) |
| `verification_requests` | Pending and resolved verification requests |

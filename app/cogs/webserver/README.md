# WebServer

Runs an embedded aiohttp web server exposing bot health and status endpoints.

The server starts automatically when the cog loads and stops when it unloads. To
disable it, add `webserver` to `COG_BLACKLIST`.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `WEBSERVER_PORT` | `8080` | Port to bind on. Bound on `0.0.0.0` and published by `docker-compose.yml`. |
| `WEBSERVER_TOKEN` | unset | Bearer token guarding `/status`. While unset, `/status` stays disabled. |

## Endpoints

### `GET /health`

Unauthenticated liveness probe for uptime monitors. Makes no Discord API calls,
so it cannot be used to burn the bot's REST rate limit. The status code is the
signal: `200` once the gateway is connected, `503` before that.

```json
{ "status": "ok", "uptime_seconds": 84213, "latency_ms": 42 }
```

### `GET /status`

Detailed status. Requires `Authorization: Bearer $WEBSERVER_TOKEN` and returns
`401` without it, or `503` when no token is configured.

```bash
curl -H "Authorization: Bearer $WEBSERVER_TOKEN" http://host:8080/status
```

```json
{
  "status": "ok",
  "ready": true,
  "uptime_seconds": 84213,
  "latency_ms": 42,
  "guilds": 7,
  "cached_users": 1243,
  "commands": 33,
  "slash_commands": 47,
  "cogs_loaded": 58,
  "cogs_failed": ["transcribe"],
  "message_cache": 1000,
  "url_handlers": 6,
  "dev_mode": false,
  "version": "0.1.0",
  "commit": "68826df",
  "python_version": "3.10.11",
  "discordpy_version": "2.7.1"
}
```

`cogs_failed` lists cogs that raised during load, which is otherwise only
visible in the logs at startup.

## Commands

| Command | Description | Permissions |
|---|---|---|
| `/web start` | Start the web server | Admin only |
| `/web stop` | Stop the web server | Admin only |
| `/web restart` | Restart the web server | Admin only |

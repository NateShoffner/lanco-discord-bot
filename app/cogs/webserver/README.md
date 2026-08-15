# WebServer

Runs an embedded aiohttp web server exposing a bot status endpoint.

The server starts automatically when the cog loads and stops when it unloads. To
disable it, add `webserver` to `COG_BLACKLIST`.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `WEBSERVER_PORT` | `8080` | Port to bind on. Bound on `0.0.0.0` so it is reachable from outside the container. |

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /status` | Bot status as JSON. Returns 503 until the gateway connection is ready. |

Nothing publishes the port to the host by default. Add a `ports:` mapping in
`docker-compose.yml` if the endpoint needs to be reachable from outside the
container, keeping in mind `/status` is unauthenticated.

## Commands

| Command | Description | Permissions |
|---|---|---|
| `/web start` | Start the web server | Admin only |
| `/web stop` | Stop the web server | Admin only |
| `/web restart` | Restart the web server | Admin only |

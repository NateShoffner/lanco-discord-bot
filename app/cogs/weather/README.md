# Weather

Get the current weather and forecast for any location.

## Commands

| Command | Description |
|---|---|
| `weather [location]` | Current conditions, plus air quality |
| `forecast [location]` | Multi-day outlook, same as `forecast daily` |
| `forecast daily [location]` | Up to 7 days, with each day's high and low |
| `forecast hourly [location]` | The next 12 hours |

All of them are available as slash commands too, and all default to
Lancaster, PA when no location is given. A location can be a place name or a
US zip code.

Forecast times are rendered in the timezone of the place being forecast, not
the bot's, so asking for somewhere in another timezone gives the hours a
person standing there would read.

## Configuration

Needs both `OPENCAGE_API_KEY` (geocoding) and `OPENWEATHERMAP_API_KEY`. The cog
logs a warning and disables its commands when either is missing.

The forecast uses OpenWeatherMap's One Call 3.0 API, which is a paid
subscription with a free daily allowance, billed per request. Current
conditions use the free 2.5 endpoints. One request returns both the hourly and
daily data, so a location is fetched once and cached for 10 minutes to serve
both views.

Note that the older `2.5/forecast/daily` endpoint is not part of the free tier
and returns 401 without a subscription, which is why the forecast is built on
One Call rather than that.

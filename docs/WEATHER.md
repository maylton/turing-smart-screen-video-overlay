# Weather support

Themes can display current weather through `STATS / WEATHER` text components.
The GTK theme editor can create this structure from **Theme elements → Add → Information — Weather**.

Weather is a compound element. Adding it creates all editable weather sections hidden by default so the preview does not become cluttered. Enable only the fields you want, or apply a Weather preset to turn on a complete layout.

## Provider

Weather now defaults to Open-Meteo, which works with latitude and longitude and does not require an API key for the normal app use case.

```yaml
config:
  WEATHER_PROVIDER: open-meteo
  WEATHER_LOCATION: 'João Pessoa, Paraíba, Brasil'
  WEATHER_LATITUDE: '-7.1195'
  WEATHER_LONGITUDE: '-34.8450'
  WEATHER_UNITS: metric
  WEATHER_LANGUAGE: pt_br
  WEATHER_TIMEOUT_SECONDS: 10
  WEATHER_CACHE_SECONDS: 600
```

`WEATHER_PROVIDER` values:

- `open-meteo`: default provider, no API key required.
- `openweathermap`: compatibility provider, requires `WEATHER_API_KEY`.

## Location search

After adding Weather, select `STATS / WEATHER` in the tree. The Properties panel shows **Weather location**.

Type a city or place name, then choose **Use city**. The editor searches Open-Meteo Geocoding, uses the first matching result, and updates `config.yaml` with:

- `WEATHER_PROVIDER: open-meteo`
- `WEATHER_LOCATION`
- `WEATHER_LATITUDE`
- `WEATHER_LONGITUDE`

The weather cache is cleared after changing location so the next runtime fetch uses the new coordinates.

## Hidden-first creation

When Weather is added from the Theme elements catalog, the editor creates the complete structure but keeps each `TEXT` node hidden:

```yaml
STATS:
  WEATHER:
    INTERVAL: 600
    TEMPERATURE:
      TEXT:
        SHOW: false
    TEMPERATURE_FELT:
      TEXT:
        SHOW: false
    WEATHER_DESCRIPTION:
      TEXT:
        SHOW: false
    HUMIDITY:
      TEXT:
        SHOW: false
    UPDATE_TIME:
      TEXT:
        SHOW: false
```

This follows the editor rule for compound elements: create the editable structure first, then let the user enable only the pieces needed for that theme.

## Editor presets

After adding Weather, select `STATS / WEATHER` in the tree. The Properties panel shows **Weather preset** with starter layouts:

- Bottom weather card
- Top compact weather strip
- Centered glass weather card
- Minimal warm corner

Applying a preset intentionally enables and positions a complete weather layout. These presets replace the `STATS / WEATHER` layout only. They do not change other CPU, GPU, RAM, image, or video elements.

## Runtime behavior

- `STATIC` and `STUB` sensor modes use deterministic fake weather so previews do not require network access.
- Real weather requests use `WEATHER_TIMEOUT_SECONDS`.
- Successful responses are cached for `WEATHER_CACHE_SECONDS`.
- If a later request fails, the last successful weather snapshot is reused when available.

## Notes

Open-Meteo weather codes are mapped to short English and Portuguese descriptions. `pt_br`, `pt-BR`, and `pt_BR` are normalized to Portuguese descriptions.

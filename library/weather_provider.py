# SPDX-License-Identifier: GPL-3.0-or-later
"""Weather provider helpers for themed smart screen widgets.

The app historically talked directly to OpenWeatherMap from ``stats.py``.
This module keeps that provider working, but adds Open-Meteo as the default
provider so weather can work without requiring an API key.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from library.log import logger


WEATHER_UNITS = {
    "metric": "°C",
    "imperial": "°F",
    "standard": "°K",
}

OPEN_METEO_UNITS = {
    "metric": "celsius",
    "imperial": "fahrenheit",
    "standard": "celsius",
}

LANGUAGE_ALIASES = {
    "pt_br": "pt",
    "pt-br": "pt",
    "pt_BR": "pt",
    "en_us": "en",
    "en-us": "en",
    "en_US": "en",
}

OPEN_METEO_WEATHER_CODES = {
    "en": {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    },
    "pt": {
        0: "Céu limpo",
        1: "Predominantemente limpo",
        2: "Parcialmente nublado",
        3: "Nublado",
        45: "Nevoeiro",
        48: "Nevoeiro com geada",
        51: "Garoa fraca",
        53: "Garoa moderada",
        55: "Garoa intensa",
        56: "Garoa congelante fraca",
        57: "Garoa congelante intensa",
        61: "Chuva fraca",
        63: "Chuva moderada",
        65: "Chuva forte",
        66: "Chuva congelante fraca",
        67: "Chuva congelante forte",
        71: "Neve fraca",
        73: "Neve moderada",
        75: "Neve forte",
        77: "Grãos de neve",
        80: "Pancadas fracas de chuva",
        81: "Pancadas moderadas de chuva",
        82: "Pancadas fortes de chuva",
        85: "Pancadas fracas de neve",
        86: "Pancadas fortes de neve",
        95: "Tempestade",
        96: "Tempestade com granizo fraco",
        99: "Tempestade com granizo forte",
    },
}


@dataclass
class WeatherSnapshot:
    temperature: Optional[str] = None
    feels_like: Optional[str] = None
    update_time: Optional[str] = None
    description: Optional[str] = None
    humidity: Optional[str] = None
    provider: str = ""
    error: Optional[str] = None

    def as_theme_values(self) -> Dict[str, Optional[str]]:
        return {
            "temp": self.temperature,
            "feel": self.feels_like,
            "time": self.update_time,
            "desc": self.description or self.error,
            "humidity": self.humidity,
        }


class WeatherProvider:
    """Fetch and cache weather data for the stats renderer."""

    _last_snapshot: Optional[WeatherSnapshot] = None
    _last_fetch_at: Optional[datetime.datetime] = None

    @classmethod
    def fetch(cls, settings: Dict[str, Any], hw_sensors: str = "AUTO") -> WeatherSnapshot:
        if hw_sensors in {"STATIC", "STUB"}:
            return WeatherSnapshot(
                temperature="17.5°C",
                feels_like="(17.2°C)",
                update_time="@15:33",
                description="Cloudy",
                humidity="45%",
                provider="stub",
            )

        cache_seconds = cls._int_setting(settings, "WEATHER_CACHE_SECONDS", 600)
        now = datetime.datetime.now()
        if (
            cls._last_snapshot is not None
            and cls._last_fetch_at is not None
            and cache_seconds > 0
            and (now - cls._last_fetch_at).total_seconds() < cache_seconds
        ):
            return cls._last_snapshot

        provider = str(settings.get("WEATHER_PROVIDER", "open-meteo") or "open-meteo").strip().lower()
        if provider in {"openweathermap", "open-weather-map", "owm"}:
            snapshot = cls._fetch_openweathermap(settings)
        else:
            snapshot = cls._fetch_open_meteo(settings)

        if snapshot.error and cls._last_snapshot is not None:
            logger.warning(
                "Weather fetch failed using %s; reusing cached weather: %s",
                snapshot.provider or provider,
                snapshot.error,
            )
            return cls._last_snapshot

        if not snapshot.error:
            cls._last_snapshot = snapshot
            cls._last_fetch_at = now
        return snapshot

    @staticmethod
    def _language(settings: Dict[str, Any]) -> str:
        raw = str(settings.get("WEATHER_LANGUAGE", "en") or "en").strip()
        return LANGUAGE_ALIASES.get(raw, raw.split("_")[0].split("-")[0].lower() or "en")

    @staticmethod
    def _coords(settings: Dict[str, Any]) -> tuple[Optional[float], Optional[float], Optional[str]]:
        lat = settings.get("WEATHER_LATITUDE", "")
        lon = settings.get("WEATHER_LONGITUDE", "")
        try:
            latitude = float(lat)
            longitude = float(lon)
        except (TypeError, ValueError):
            return None, None, "Invalid WEATHER_LATITUDE or WEATHER_LONGITUDE"
        return latitude, longitude, None

    @staticmethod
    def _int_setting(settings: Dict[str, Any], key: str, default: int) -> int:
        try:
            return int(settings.get(key, default))
        except (TypeError, ValueError):
            return default

    @classmethod
    def _fetch_open_meteo(cls, settings: Dict[str, Any]) -> WeatherSnapshot:
        lat, lon, error = cls._coords(settings)
        if error:
            return WeatherSnapshot(provider="open-meteo", error=error)

        units = str(settings.get("WEATHER_UNITS", "metric") or "metric").strip().lower()
        deg = WEATHER_UNITS.get(units, "°C")
        timeout = cls._int_setting(settings, "WEATHER_TIMEOUT_SECONDS", 10)
        language = cls._language(settings)

        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code",
            "temperature_unit": OPEN_METEO_UNITS.get(units, "celsius"),
            "timezone": "auto",
        }

        try:
            response = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params=params,
                timeout=max(1, timeout),
            )
            response.raise_for_status()
            data = response.json()
            current = data.get("current", {})
            temperature = float(current["temperature_2m"])
            feels_like = float(current["apparent_temperature"])
            humidity = float(current["relative_humidity_2m"])
            code = int(current.get("weather_code", -1))
            desc = OPEN_METEO_WEATHER_CODES.get(language, OPEN_METEO_WEATHER_CODES["en"]).get(
                code,
                OPEN_METEO_WEATHER_CODES["en"].get(code, "Weather unavailable"),
            )
            return WeatherSnapshot(
                temperature=f"{temperature:.1f}{deg}",
                feels_like=f"({feels_like:.1f}{deg})",
                update_time=datetime.datetime.now().strftime("@%H:%M"),
                description=desc,
                humidity=f"{humidity:.0f}%",
                provider="open-meteo",
            )
        except Exception as exc:
            logger.error("Error fetching Open-Meteo weather: %s", exc)
            return WeatherSnapshot(provider="open-meteo", error=f"Open-Meteo error: {exc}")

    @classmethod
    def _fetch_openweathermap(cls, settings: Dict[str, Any]) -> WeatherSnapshot:
        lat, lon, error = cls._coords(settings)
        if error:
            return WeatherSnapshot(provider="openweathermap", error=error)

        api_key = str(settings.get("WEATHER_API_KEY", "") or "").strip()
        if not api_key:
            return WeatherSnapshot(provider="openweathermap", error="No OpenWeatherMap API key")

        units = str(settings.get("WEATHER_UNITS", "metric") or "metric").strip().lower()
        language = cls._language(settings)
        timeout = cls._int_setting(settings, "WEATHER_TIMEOUT_SECONDS", 10)
        deg = WEATHER_UNITS.get(units, "°?")
        params = {
            "lat": lat,
            "lon": lon,
            "exclude": "minutely,hourly,daily,alerts",
            "appid": api_key,
            "units": units,
            "lang": language,
        }

        try:
            response = requests.get(
                "https://api.openweathermap.org/data/3.0/onecall",
                params=params,
                timeout=max(1, timeout),
            )
            response.raise_for_status()
            data = response.json()
            current = data["current"]
            return WeatherSnapshot(
                temperature=f"{current['temp']:.1f}{deg}",
                feels_like=f"({current['feels_like']:.1f}{deg})",
                update_time=datetime.datetime.now().strftime("@%H:%M"),
                description=current["weather"][0]["description"].capitalize(),
                humidity=f"{current['humidity']:.0f}%",
                provider="openweathermap",
            )
        except Exception as exc:
            logger.error("Error fetching OpenWeatherMap weather: %s", exc)
            return WeatherSnapshot(provider="openweathermap", error=f"OpenWeatherMap error: {exc}")

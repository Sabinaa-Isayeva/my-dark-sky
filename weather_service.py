from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from threading import Lock
from time import time
from typing import Any

import requests


class WeatherServiceError(Exception):
    pass


@dataclass
class CacheEntry:
    expires_at: float
    payload: Any


class SimpleTTLCache:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, CacheEntry] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            if entry.expires_at <= time():
                self._cache.pop(key, None)
                return None
            return entry.payload

    def set(self, key: str, payload: Any) -> None:
        with self._lock:
            self._cache[key] = CacheEntry(
                expires_at=time() + self.ttl_seconds,
                payload=payload,
            )


class WeatherService:
    GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
    ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

    def __init__(self) -> None:
        self.cache = SimpleTTLCache(ttl_seconds=300)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "my-dark-sky-flask-app/1.0"})

    def search_locations(self, query: str) -> list[dict[str, Any]]:
        cache_key = f"search:{query.lower()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        response = self.session.get(
            self.GEOCODE_URL,
            params={
                "name": query,
                "count": 6,
                "language": "en",
                "format": "json",
            },
            timeout=15,
        )
        self._raise_for_status(response, "Could not search locations.")
        data = response.json()

        results = []
        for item in data.get("results", []):
            results.append(
                {
                    "name": item.get("name"),
                    "country": item.get("country"),
                    "admin1": item.get("admin1"),
                    "latitude": item.get("latitude"),
                    "longitude": item.get("longitude"),
                    "timezone": item.get("timezone"),
                    "label": self._build_location_label(item),
                }
            )

        self.cache.set(cache_key, results)
        return results

    def get_weather_for_date(
        self,
        *,
        latitude: float,
        longitude: float,
        selected_date: str,
        label: str,
    ) -> dict[str, Any]:
        target_date = self._parse_date(selected_date)
        cache_key = f"weather:{latitude:.4f}:{longitude:.4f}:{target_date.isoformat()}:{label}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        if target_date < date.today():
            raw_data = self._fetch_archive(latitude, longitude, target_date)
            timeline = "past"
        else:
            raw_data = self._fetch_forecast(latitude, longitude, target_date)
            timeline = "future" if target_date > date.today() else "today"

        payload = self._shape_weather_payload(
            raw_data=raw_data,
            selected_date=target_date,
            label=label,
            timeline=timeline,
            latitude=latitude,
            longitude=longitude,
        )
        self.cache.set(cache_key, payload)
        return payload

    def _fetch_forecast(self, latitude: float, longitude: float, target_date: date) -> dict[str, Any]:
        response = self.session.get(
            self.FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "timezone": "auto",
                "current": ",".join(
                    [
                        "temperature_2m",
                        "apparent_temperature",
                        "relative_humidity_2m",
                        "wind_speed_10m",
                        "weather_code",
                    ]
                ),
                "daily": ",".join(
                    [
                        "weather_code",
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "apparent_temperature_max",
                        "apparent_temperature_min",
                        "sunrise",
                        "sunset",
                        "precipitation_sum",
                        "precipitation_probability_max",
                        "wind_speed_10m_max",
                    ]
                ),
                "hourly": ",".join(
                    [
                        "temperature_2m",
                        "apparent_temperature",
                        "relative_humidity_2m",
                        "precipitation_probability",
                        "weather_code",
                        "wind_speed_10m",
                    ]
                ),
                "start_date": target_date.isoformat(),
                "end_date": target_date.isoformat(),
            },
            timeout=20,
        )
        self._raise_for_status(response, "Could not fetch forecast data.")
        return response.json()

    def _fetch_archive(self, latitude: float, longitude: float, target_date: date) -> dict[str, Any]:
        response = self.session.get(
            self.ARCHIVE_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "timezone": "auto",
                "daily": ",".join(
                    [
                        "weather_code",
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "apparent_temperature_max",
                        "apparent_temperature_min",
                        "sunrise",
                        "sunset",
                        "precipitation_sum",
                        "wind_speed_10m_max",
                    ]
                ),
                "hourly": ",".join(
                    [
                        "temperature_2m",
                        "apparent_temperature",
                        "relative_humidity_2m",
                        "weather_code",
                        "wind_speed_10m",
                    ]
                ),
                "start_date": target_date.isoformat(),
                "end_date": target_date.isoformat(),
            },
            timeout=20,
        )
        self._raise_for_status(response, "Could not fetch historical weather data.")
        return response.json()

    def _shape_weather_payload(
        self,
        *,
        raw_data: dict[str, Any],
        selected_date: date,
        label: str,
        timeline: str,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any]:
        daily = raw_data.get("daily", {})
        hourly = raw_data.get("hourly", {})
        current = raw_data.get("current", {})
        daily_index = 0

        if not daily.get("time"):
            raise WeatherServiceError("Weather data was unavailable for the selected date.")

        hourly_points = self._build_hourly_points(hourly)
        summary = {
            "weather_code": daily["weather_code"][daily_index],
            "weather_label": self._weather_code_to_text(daily["weather_code"][daily_index]),
            "temperature_max": daily["temperature_2m_max"][daily_index],
            "temperature_min": daily["temperature_2m_min"][daily_index],
            "apparent_max": daily["apparent_temperature_max"][daily_index],
            "apparent_min": daily["apparent_temperature_min"][daily_index],
            "sunrise": daily["sunrise"][daily_index],
            "sunset": daily["sunset"][daily_index],
            "precipitation_sum": daily.get("precipitation_sum", [0])[daily_index],
            "precipitation_probability_max": daily.get("precipitation_probability_max", [None])[daily_index],
            "wind_speed_max": daily["wind_speed_10m_max"][daily_index],
        }

        current_weather = None
        if timeline == "today" and current:
            current_weather = {
                "temperature": current.get("temperature_2m"),
                "apparent_temperature": current.get("apparent_temperature"),
                "humidity": current.get("relative_humidity_2m"),
                "wind_speed": current.get("wind_speed_10m"),
                "weather_code": current.get("weather_code"),
                "weather_label": self._weather_code_to_text(current.get("weather_code")),
                "time": current.get("time"),
            }

        return {
            "location": {
                "label": label,
                "latitude": latitude,
                "longitude": longitude,
                "timezone": raw_data.get("timezone"),
            },
            "selected_date": selected_date.isoformat(),
            "timeline": timeline,
            "current_weather": current_weather,
            "summary": summary,
            "hourly": hourly_points,
        }

    def _build_hourly_points(self, hourly: dict[str, Any]) -> list[dict[str, Any]]:
        timeline = hourly.get("time", [])
        points = []
        for index, timestamp in enumerate(timeline):
            point = {
                "time": timestamp,
                "temperature": hourly.get("temperature_2m", [None])[index],
                "apparent_temperature": hourly.get("apparent_temperature", [None])[index],
                "humidity": hourly.get("relative_humidity_2m", [None])[index],
                "weather_code": hourly.get("weather_code", [None])[index],
                "weather_label": self._weather_code_to_text(hourly.get("weather_code", [None])[index]),
                "wind_speed": hourly.get("wind_speed_10m", [None])[index],
            }
            precipitation_probability = hourly.get("precipitation_probability")
            if precipitation_probability:
                point["precipitation_probability"] = precipitation_probability[index]
            points.append(point)
        return points

    @staticmethod
    def _build_location_label(item: dict[str, Any]) -> str:
        parts = [item.get("name"), item.get("admin1"), item.get("country")]
        return ", ".join([part for part in parts if part])

    @staticmethod
    def _parse_date(selected_date: str) -> date:
        try:
            return datetime.strptime(selected_date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("date must be in YYYY-MM-DD format.") from exc

    @staticmethod
    def _raise_for_status(response: requests.Response, message: str) -> None:
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise WeatherServiceError(message) from exc

    @staticmethod
    def _weather_code_to_text(code: int | None) -> str:
        weather_codes = {
            0: "Clear sky",
            1: "Mostly clear",
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
            71: "Slight snow",
            73: "Moderate snow",
            75: "Heavy snow",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with light hail",
            99: "Thunderstorm with heavy hail",
        }
        return weather_codes.get(code, "Unknown conditions")

# scentia-backend/app/services/open_meteo.py
import httpx

async def get_coordinates(location_name: str):
    async with httpx.AsyncClient() as client:
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        
        # 1. Primer intento: Término tal como lo devuelve el LLM
        response = await client.get(geo_url, params={
            "name": location_name.strip(),
            "count": 1,
            "language": "es",
            "format": "json"
        })
        data = response.json()

        # 2. Segundo intento (Fallback): Si falla, probar tomando únicamente la primera palabra (Ciudad)
        if not data.get("results") and " " in location_name:
            first_word = location_name.strip().split()[0]
            response = await client.get(geo_url, params={
                "name": first_word,
                "count": 1,
                "language": "es",
                "format": "json"
            })
            data = response.json()

        if not data.get("results"):
            raise ValueError(f"No se encontraron coordenadas para: {location_name}")

        result = data["results"][0]
        return {
            "latitude": result["latitude"],
            "longitude": result["longitude"],
            "formatted_name": f"{result.get('name', '')}, {result.get('admin1', '')}, {result.get('country', '')}".strip(", ")
        }

async def get_weather_forecast(lat: float, lon: float, target_date: str):
    async with httpx.AsyncClient() as client:
        forecast_url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": ["weathercode", "temperature_2m_max", "temperature_2m_min", "precipitation_sum", "windspeed_10m_max"],
            "timezone": "auto",
            "forecast_days": 16
        }
        response = await client.get(forecast_url, params=params)
        data = response.json()

        daily = data.get("daily", {})
        times = daily.get("time", [])
        
        target_day_data = None
        if target_date in times:
            idx = times.index(target_date)
            target_day_data = {
                "date": times[idx],
                "temp_max": daily["temperature_2m_max"][idx],
                "temp_min": daily["temperature_2m_min"][idx],
                "precipitation_sum": daily["precipitation_sum"][idx],
                "wind_speed_max": daily["windspeed_10m_max"][idx],
                "weather_code": daily["weathercode"][idx]
            }

        return {
            "raw_series_for_clustering": daily,  # Serie temporal completa para el modelo futuro
            "target_day_forecast": target_day_data
        }